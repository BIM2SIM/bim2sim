import copy
import math

import ifcopenshell
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex, BRepBuilderAPI_Transform, BRepBuilderAPI_MakeFace, \
    BRepBuilderAPI_Sewing
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepGProp import brepgprop_VolumeProperties, brepgprop_SurfaceProperties
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.GProp import GProp_GProps
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods_Face
from OCC.Core._Geom import Handle_Geom_Plane_DownCast
from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Trsf, gp_XYZ, gp_Vec

import bim2sim
from bim2sim.decision import BoolDecision, DecisionBunch
from bim2sim.kernel.elements.bps import ExternalSpatialElement, SpaceBoundary
from bim2sim.task.base import ITask
from bim2sim.task.common.inner_loop_remover import convex_decomposition, is_convex_no_holes
from bim2sim.utilities.pyocc_tools import PyOCCTools


class EPGeomPreprocessing(ITask):
    reads = ('instances',)
    touches = ('ep_decisions', 'instances',)

    def __init__(self):
        super().__init__()

    def run(self, workflow, instances):
        self.logger.info("Geometric preprocessing for EnergyPlus Export started ...")
        decisions = []
        split_bounds = BoolDecision(
            question="Do you want to decompose non-convex space boundaries into convex boundaries?",
            global_key='EnergyPlus.SplitConvexBounds')
        decisions.append(split_bounds)
        add_shadings = BoolDecision(
            question="Do you want to add shadings if available?",
            global_key='EnergyPlus.AddShadings')
        decisions.append(add_shadings)
        split_shadings = BoolDecision(
            question="Do you want to decompose non-convex shadings into convex shadings?",
            global_key='EnergyPlus.SplitConvexShadings')
        decisions.append(split_shadings)
        yield DecisionBunch(decisions)
        ep_decisions = {item.global_key: item.value for item in decisions}
        self._add_bounds_to_instances(instances)
        instances = self._get_parents_and_children(instances)
        self._move_children_to_parents(instances)
        self._fix_surface_orientation(instances)
        if split_bounds.value:
            self.logger.info("Split non-convex surfaces")
            self._split_non_convex_bounds(instances)

        if add_shadings.value:
            spatials = []
            for inst in instances:
                if isinstance(instances[inst], ExternalSpatialElement):
                    for sb in instances[inst].space_boundaries:
                        spatials.append(sb)
            if spatials and split_shadings.value:
                self._split_non_convex_shadings(instances, spatials)
        return ep_decisions, instances

    def _add_bounds_to_instances(self, instances):
        self.logger.info("Creates python representation of relevant ifc types")
        for inst in list(instances):
            if instances[inst].ifc.is_a("IfcSpace"):
                for bound in instances[inst].space_boundaries:
                    instances[bound.guid] = bound

    def _get_parents_and_children(self, instances):
        """get parent-children relationships between IfcElements (e.g. Windows, Walls)
        and the corresponding relationships of their space boundaries"""
        self.logger.info("Compute relationships between space boundaries")
        self.logger.info("Compute relationships between openings and their base surfaces")
        drop_list = {}  # HACK: dictionary for bounds which have to be removed from instances (due to duplications)
        for inst in instances:
            inst_obj = instances[inst]
            if not inst_obj.ifc.is_a('IfcRelSpaceBoundary'):
                continue
            if inst_obj.level_description == "2b":
                continue
            inst_obj_space = inst_obj.ifc.RelatingSpace
            b_inst = inst_obj.bound_instance
            if b_inst is None:
                continue
            # assign opening elems (Windows, Doors) to parents and vice versa
            if not hasattr(b_inst.ifc, 'HasOpenings'):
                continue
            if len(b_inst.ifc.HasOpenings) == 0:
                continue
            for opening in b_inst.ifc.HasOpenings:
                if hasattr(opening.RelatedOpeningElement, 'HasFillings'):
                    for fill in opening.RelatedOpeningElement.HasFillings:
                        opening_obj = instances[fill.RelatedBuildingElement.GlobalId]
                        if not hasattr(b_inst, 'related_openings'):
                            setattr(b_inst, 'related_openings', [])
                        if opening_obj in b_inst.related_openings:
                            continue
                        b_inst.related_openings.append(opening_obj)
                        if not hasattr(opening_obj, 'related_parent'):
                            setattr(opening_obj, 'related_parent', [])
                        opening_obj.related_parent = b_inst
            # assign space boundaries of opening elems (Windows, Doors) to parents and vice versa
            if not hasattr(b_inst, 'related_openings'):
                continue
            if not hasattr(inst_obj, 'related_opening_bounds'):
                setattr(inst_obj, 'related_opening_bounds', [])
            for opening in b_inst.related_openings:
                for op_bound in opening.space_boundaries:
                    if op_bound.ifc.RelatingSpace == inst_obj_space:
                        if op_bound in inst_obj.related_opening_bounds:
                            continue
                        distance = BRepExtrema_DistShapeShape(
                            op_bound.bound_shape,
                            inst_obj.bound_shape,
                            Extrema_ExtFlag_MIN
                        ).Value()
                        if distance > 0.3:
                            continue
                        center_shape = BRepBuilderAPI_MakeVertex(gp_Pnt(op_bound.bound_center)).Shape()
                        center_dist = BRepExtrema_DistShapeShape(
                            inst_obj.bound_shape,
                            center_shape,
                            Extrema_ExtFlag_MIN
                        ).Value()
                        if center_dist > 0.3:
                            continue
                        # HACK:
                        # some space boundaries have inner loops which are removed for vertical bounds in
                        # calc_bound_shape (elements.py). Those inner loops contain an additional vertical bound (wall)
                        # which is "parent" of an opening. EnergyPlus does not accept openings having a parent surface
                        # of same size as the opening. Thus, since inner loops are removed from shapes beforehand,
                        # those boundaries are removed from "instances" and the openings are assigned to have the larger
                        # boundary as a parent.
                        #
                        # find cases where opening area matches area of corresponding wall (within inner loop)
                        if (inst_obj.bound_area - op_bound.bound_area).m < 0.01:
                            rel_bound = None
                            drop_list[inst] = inst_obj
                            ib = [b for b in b_inst.space_boundaries if
                                  b.ifc.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries if
                                  b.bound_thermal_zone == op_bound.bound_thermal_zone]
                            if len(ib) == 1:
                                rel_bound = ib[0]
                            elif len(ib) > 1:
                                for b in ib:
                                    # check if orientation of possibly related bound is the same as opening
                                    angle = math.degrees(gp_Dir(b.bound_normal).Angle(gp_Dir(op_bound.bound_normal)))
                                    if not (angle < 0.1 or angle > 179.9):
                                        continue
                                    distance = BRepExtrema_DistShapeShape(
                                        b.bound_shape,
                                        op_bound.bound_shape,
                                        Extrema_ExtFlag_MIN
                                    ).Value()
                                    if distance > 0.4:
                                        continue
                                    else:
                                        rel_bound = b
                            elif not rel_bound:
                                tzb = [b for b in op_bound.bound_thermal_zone.space_boundaries if
                                       b.ifc.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries]
                                for b in tzb:
                                    # check if orientation of possibly related bound is the same as opening
                                    try:
                                        angle = math.degrees(
                                            gp_Dir(b.bound_normal).Angle(gp_Dir(op_bound.bound_normal)))
                                    except:
                                        pass
                                    if not (angle < 0.1 or angle > 179.9):
                                        continue
                                    distance = BRepExtrema_DistShapeShape(
                                        b.bound_shape,
                                        op_bound.bound_shape,
                                        Extrema_ExtFlag_MIN
                                    ).Value()
                                    if distance > 0.4:
                                        continue
                                    else:
                                        rel_bound = b
                                if not rel_bound:
                                    continue
                            else:
                                continue
                            if not rel_bound:
                                continue
                            if not hasattr(rel_bound, 'related_opening_bounds'):
                                setattr(rel_bound, 'related_opening_bounds', [])
                            rel_bound.related_opening_bounds.append(op_bound)
                            if not hasattr(op_bound, 'related_parent_bound'):
                                setattr(op_bound, 'related_parent_bound', [])
                            op_bound.related_parent_bound = rel_bound
                        else:
                            inst_obj.related_opening_bounds.append(op_bound)
                            if not hasattr(op_bound, 'related_parent_bound'):
                                setattr(op_bound, 'related_parent_bound', [])
                            op_bound.related_parent_bound = inst_obj
        # remove boundaries from instances if they are false duplicates of windows in shape of walls
        instances = {k: v for k, v in instances.items() if k not in drop_list}
        return instances

    def _move_children_to_parents(self, instances):
        """move external opening boundaries to related parent boundary (e.g. wall)"""
        self.logger.info("Move openings to base surface, if needed")
        for inst in instances:
            if hasattr(instances[inst], 'related_parent_bound'):
                opening_obj = instances[inst]
                # only external openings need to be moved
                # all other are properly placed within parent boundary
                if opening_obj.is_external:
                    distance = BRepExtrema_DistShapeShape(
                        opening_obj.bound_shape,
                        opening_obj.related_parent_bound.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    if distance < 0.001:
                        continue
                    prod_vec = []
                    for i in opening_obj.bound_normal.Coord():
                        prod_vec.append(distance * i)

                    # moves opening to parent boundary
                    trsf = gp_Trsf()
                    coord = gp_XYZ(*prod_vec)
                    vec = gp_Vec(coord)
                    trsf.SetTranslation(vec)

                    opening_obj.bound_shape_org = opening_obj.bound_shape
                    opening_obj.bound_shape = BRepBuilderAPI_Transform(opening_obj.bound_shape, trsf).Shape()

                    # check if opening has been moved to boundary correctly
                    # and otherwise move again in reversed direction
                    new_distance = BRepExtrema_DistShapeShape(
                        opening_obj.bound_shape,
                        opening_obj.related_parent_bound.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    if new_distance > 1e-3:
                        prod_vec = []
                        op_normal = opening_obj.bound_normal.Reversed()
                        for i in op_normal.Coord():
                            prod_vec.append(new_distance * i)
                        trsf = gp_Trsf()
                        coord = gp_XYZ(*prod_vec)
                        vec = gp_Vec(coord)
                        trsf.SetTranslation(vec)
                        opening_obj.bound_shape = BRepBuilderAPI_Transform(opening_obj.bound_shape, trsf).Shape()
                    # update bound center attribute for new shape location
                    opening_obj.bound_center = SpaceBoundary.get_bound_center(opening_obj, 'bound_center')

    def _fix_surface_orientation(self, instances):
        """
        Fix orientation of space boundaries.
        Fix orientation of all surfaces but openings by sewing followed by disaggregation.
        Fix orientation of openings afterwards according to orientation of parent bounds.
        """
        self.logger.info("Fix surface orientation")
        for inst in instances:
            if not instances[inst].ifc.is_a('IfcSpace'):
                continue
            space = instances[inst]
            face_list = []
            for bound in space.space_boundaries:
                if hasattr(bound, 'related_parent_bound'):
                    continue
                exp = TopExp_Explorer(bound.bound_shape, TopAbs_FACE)
                face = exp.Current()
                try:
                    face = topods_Face(face)
                    face_list.append(face)
                except:
                    exp1 = TopExp_Explorer(bound.bound_shape, TopAbs_WIRE)
                    wire = exp1.Current()
                    face = BRepBuilderAPI_MakeFace(wire).Face()
                    face_list.append(face)
            if not face_list:
                continue
            if hasattr(space, 'space_boundaries_2B'):
                for bound in space.space_boundaries_2B:
                    exp = TopExp_Explorer(bound.bound_shape, TopAbs_FACE)
                    face = exp.Current()
                    face = topods_Face(face)
                    face_list.append(face)
            sew = BRepBuilderAPI_Sewing(0.0001)
            for fc in face_list:
                sew.Add(fc)
            sew.Perform()
            sewed_shape = sew.SewedShape()
            fixed_shape = sewed_shape
            p = GProp_GProps()
            brepgprop_VolumeProperties(fixed_shape, p)
            if p.Mass() < 0:
                fixed_shape.Complement()
            f_exp = TopExp_Explorer(fixed_shape, TopAbs_FACE)
            fixed_faces = []
            while f_exp.More():
                fixed_faces.append(topods_Face(f_exp.Current()))
                f_exp.Next()
            for fc in fixed_faces:
                an_exp = TopExp_Explorer(fc, TopAbs_FACE)
                a_face = an_exp.Current()
                face = topods_Face(a_face)
                surf = BRep_Tool.Surface(face)
                obj = surf
                assert obj.DynamicType().Name() == "Geom_Plane"
                plane = Handle_Geom_Plane_DownCast(surf)
                face_normal = plane.Axis().Direction().XYZ()
                p = GProp_GProps()
                brepgprop_SurfaceProperties(face, p)
                face_center = p.CentreOfMass().XYZ()
                complemented = False
                for bound in space.space_boundaries:
                    if (gp_Pnt(bound.bound_center).Distance(gp_Pnt(face_center)) > 1e-3):
                        continue
                    if ((bound.bound_area.m - p.Mass()) ** 2 < 0.01):
                        if fc.Orientation() == 1:
                            bound.bound_shape.Complement()
                            complemented = True
                        elif face_normal.Dot(bound.bound_normal) < 0:
                            bound.bound_shape.Complement()
                            complemented = True
                        if not complemented:
                            continue
                        # if hasattr(bound, 'bound_normal'):
                        #     del bound.__dict__['bound_normal']
                        if hasattr(bound, 'related_opening_bounds'):
                            op_bounds = bound.related_opening_bounds
                            for op in op_bounds:
                                op.bound_shape.Complement()
                                # if hasattr(op, 'bound_normal'):
                                #     del op.__dict__['bound_normal']
                        break
                if not hasattr(space, 'space_boundaries_2B'):
                    continue
                for bound in space.space_boundaries_2B:
                    if gp_Pnt(bound.bound_center).Distance(gp_Pnt(face_center)) < 1e-6:
                        bound.bound_shape = face
                        if hasattr(bound, 'bound_normal'):
                            del bound.__dict__['bound_normal']
                        break

    def _split_non_convex_bounds(self, instances):
        bounds = [instances[i] for i in instances if instances[i].ifc.is_a('IfcRelSpaceBoundary')]
        bounds_except_openings = [b for b in bounds if not hasattr(b, 'related_parent_bound')]
        conv = []
        nconv = []
        others = []
        processed_id = []
        for bound in bounds_except_openings:
            if hasattr(bound, 'convex_processed'):
                continue
            if hasattr(bound,
                       'related_opening_bounds'):  # check all space boundaries that are not parent to an opening bound
                if bim2sim.task.common.inner_loop_remover.is_convex_slow(bound.bound_shape):
                    continue
                # handle shapes that contain opening bounds
                convex_shapes = convex_decomposition(bound.bound_shape,
                                                     [op.bound_shape for op in bound.related_opening_bounds])
            else:
                if is_convex_no_holes(bound.bound_shape):
                    continue
                convex_shapes = convex_decomposition(bound.bound_shape)
            nconv.append(bound)
            if hasattr(bound, 'bound_normal'):
                del bound.__dict__['bound_normal']
            new_space_boundaries = self._create_new_convex_bounds(convex_shapes, bound, bound.related_bound)
            bound.convex_processed = True
            if (bound.related_bound and bound.related_bound.ifc.RelatingSpace.is_a('IfcSpace')) \
                    and not bound.ifc.Description == '2b':
                nconv.append(bound.related_bound)
                del instances[bound.related_bound.guid]
                bounds_except_openings.remove(bound.related_bound)
                bound.related_bound.convex_processed = True
            del instances[bound.guid]
            for new_bound in new_space_boundaries:
                instances[new_bound.guid] = new_bound
                conv.append(new_bound)
        pass

    @staticmethod
    def _create_copy_of_space_boundary(bound):
        new_bound = copy.copy(bound)
        new_bound.guid = ifcopenshell.guid.new()
        if hasattr(new_bound, 'bound_center'):
            del new_bound.__dict__['bound_center']
        if hasattr(new_bound, 'bound_normal'):
            del new_bound.__dict__['bound_normal']
        return new_bound

    def _create_new_convex_bounds(self, convex_shapes, bound, related_bound=None):
        bound.non_convex_guid = bound.guid
        new_space_boundaries = []
        openings = []
        if hasattr(bound, 'related_opening_bounds'):
            openings.extend(bound.related_opening_bounds)
        for shape in convex_shapes:
            new_bound = self._create_copy_of_space_boundary(bound)
            new_bound.bound_shape = shape
            new_bound.bound_area = SpaceBoundary.get_bound_area(new_bound, 'name')
            if openings:
                delattr(new_bound, 'related_opening_bounds')
                for opening in openings:
                    distance = BRepExtrema_DistShapeShape(
                        new_bound.bound_shape,
                        opening.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    if distance < 1e-3:
                        if not hasattr(new_bound, 'related_opening_bounds'):
                            setattr(new_bound, 'related_opening_bounds', [])
                        new_bound.related_opening_bounds.append(opening)
                        opening.related_parent_bound = new_bound
            if not all([abs(i) < 1e-3 for i in ((new_bound.bound_normal - bound.bound_normal).Coord())]):
                new_bound.bound_shape = PyOCCTools.flip_orientation_of_face(new_bound.bound_shape)
                new_bound.bound_normal = PyOCCTools.simple_face_normal(new_bound.bound_shape)
            if (related_bound and bound.related_bound.ifc.RelatingSpace.is_a('IfcSpace')) \
                    and not bound.ifc.Description == '2b':
                distance = BRepExtrema_DistShapeShape(
                    bound.bound_shape,
                    related_bound.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                new_rel_bound = self._create_copy_of_space_boundary(related_bound)
                related_bound.non_convex_guid = related_bound.guid
                if distance > 1e-3:
                    new_rel_shape = PyOCCTools.move_bound_in_direction_of_normal(new_bound, distance, reverse=False)
                else:
                    new_rel_shape = new_bound.bound_shape
                new_rel_bound.bound_shape = new_rel_shape
                new_rel_bound.bound_shape = PyOCCTools.flip_orientation_of_face(new_rel_bound.bound_shape)
                new_rel_bound.bound_normal = PyOCCTools.simple_face_normal(new_rel_bound.bound_shape)
                new_rel_bound.bound_area = SpaceBoundary.get_bound_area(new_rel_bound, 'name')
                if hasattr(new_bound, 'related_opening_bounds'):
                    for op in new_bound.related_opening_bounds:
                        if not op.related_bound:
                            continue
                        new_rel_bound.related_opening_bounds.append(op.related_bound)
                        op.related_bound.related_parent_bound = new_rel_bound
                new_bound.related_bound = new_rel_bound
                new_rel_bound.related_bound = new_bound
                new_space_boundaries.append(new_rel_bound)
            new_space_boundaries.append(new_bound)
        return new_space_boundaries

    def _split_non_convex_shadings(self, instances, spatial_bounds):
        spatial_elem = instances[[inst for inst in instances if isinstance(instances[inst], ExternalSpatialElement)][
            0]]
        for spatial in spatial_bounds:
            if is_convex_no_holes(spatial.bound_shape):
                continue
            try:
                convex_shapes = convex_decomposition(spatial.bound_shape)
            except:
                continue
            new_space_boundaries = self._create_new_convex_bounds(convex_shapes, spatial)
            spatial_bounds.remove(spatial)
            if spatial in spatial_elem.space_boundaries:
                spatial_elem.space_boundaries.remove(spatial)
            for new_bound in new_space_boundaries:
                spatial_bounds.append(new_bound)
                spatial_elem.space_boundaries.append(new_bound)

