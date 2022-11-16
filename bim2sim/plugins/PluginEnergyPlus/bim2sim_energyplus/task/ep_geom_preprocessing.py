import copy
import logging
import math

import ifcopenshell
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform, \
    BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepGProp import brepgprop_VolumeProperties, \
    brepgprop_SurfaceProperties
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.GProp import GProp_GProps
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods_Face
from OCC.Core._Geom import Handle_Geom_Plane_DownCast
from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Trsf, gp_XYZ, gp_Vec

from bim2sim.decision import BoolDecision, DecisionBunch
from bim2sim.kernel.elements.bps import ExternalSpatialElement, SpaceBoundary, \
    ThermalZone
from bim2sim.task.base import ITask
from bim2sim.task.common.inner_loop_remover import convex_decomposition, \
    is_convex_no_holes, is_convex_slow
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.utilities.pyocc_tools import PyOCCTools

logger = logging.getLogger(__name__)


class EPGeomPreprocessing(ITask):
    """
    This class includes all functions for advanced geometric preprocessing
    required for EnergyPlus export.
    """
    reads = ('instances', 'space_boundaries')
    touches = ('ep_decisions', 'instances')

    def __init__(self):
        super().__init__()

    def run(self, workflow, instances, space_boundaries):
        self.logger.info("Geometric preprocessing for EnergyPlus Export started"
                         "...")
        decisions = []
        split_bounds = BoolDecision(
            question="Do you want to decompose non-convex space boundaries into"
                     " convex boundaries?",
            global_key='EnergyPlus.SplitConvexBounds')
        decisions.append(split_bounds)
        add_shadings = BoolDecision(
            question="Do you want to add shadings if available?",
            global_key='EnergyPlus.AddShadings')
        decisions.append(add_shadings)
        split_shadings = BoolDecision(
            question="Do you want to decompose non-convex shadings into convex "
                     "shadings?",
            global_key='EnergyPlus.SplitConvexShadings')
        decisions.append(split_shadings)
        yield DecisionBunch(decisions)
        ep_decisions = {item.global_key: item.value for item in decisions}
        self._add_bounds_to_instances(instances, space_boundaries)
        self._move_children_to_parents(instances)
        self._fix_surface_orientation(instances)
        self.split_non_convex_bounds(instances, split_bounds.value)
        self._add_and_split_bounds_for_shadings(instances, add_shadings.value,
                                                split_shadings.value)

        return ep_decisions, instances

    def _add_bounds_to_instances(
            self,
            instances: dict,
            space_boundaries: dict[str, SpaceBoundary]):
        """
        This function adds those space boundaries from space_boundaries to
        instances which are needed for the EnergyPlusPlugin. This includes
        all space boundaries included in space_boundaries, which bound an
        IfcSpace. The space boundaries which have been excluded during the
        preprocessing in the kernel are skipped by only considering
        boundaries from the space_boundaries dictionary.
        Args:
            instances: dict[guid: element]
            space_boundaries: dict[guid: SpaceBoundary]
        """
        self.logger.info("Creates python representation of relevant ifc types")
        instance_dict = {}
        spaces = filter_instances(instances, ThermalZone)
        for space in spaces:
            for bound in space.space_boundaries:
                if not bound.guid in space_boundaries.keys():
                    continue
                instance_dict[bound.guid] = bound
        instances.update(instance_dict)

    def _add_and_split_bounds_for_shadings(
            self, instances: dict, add_shadings: bool, split_shadings: bool):
        """
        Enrich instances by space boundaries related to an
        ExternalSpatialElement if shadings are to be added in the energyplus
        workflow.
        Args:
            instances: dict[guid: element]
            add_shadings: True if shadings shall be added
            split_shadings: True if shading boundaries should be split in
            non-convex boundaries
        """
        if add_shadings:
            spatials = []
            ext_spatial_elems = filter_instances(
                instances, ExternalSpatialElement)
            for elem in ext_spatial_elems:
                for sb in elem.space_boundaries:
                    spatials.append(sb)
            if spatials and split_shadings:
                self._split_non_convex_shadings(instances, spatials)

    def _move_children_to_parents(self, instances: dict):
        """
        In some IFC, the opening boundaries of external wall
        boundaries are not coplanar. This function moves external opening
        boundaries to related parent boundary (e.g. wall).
        """
        self.logger.info("Move openings to base surface, if needed")
        boundaries = filter_instances(instances, SpaceBoundary)
        for bound in boundaries:
            if bound.parent_bound:
                opening_obj = bound
                # only external openings need to be moved
                # all other are properly placed within parent boundary
                if opening_obj.is_external:
                    distance = BRepExtrema_DistShapeShape(
                        opening_obj.bound_shape,
                        opening_obj.parent_bound.bound_shape,
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
                    opening_obj.bound_shape = BRepBuilderAPI_Transform(
                        opening_obj.bound_shape, trsf).Shape()

                    # check if opening has been moved to boundary correctly
                    # and otherwise move again in reversed direction
                    new_distance = BRepExtrema_DistShapeShape(
                        opening_obj.bound_shape,
                        opening_obj.parent_bound.bound_shape,
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
                        opening_obj.bound_shape = BRepBuilderAPI_Transform(
                            opening_obj.bound_shape, trsf).Shape()
                    # update bound center attribute for new shape location
                    opening_obj.bound_center = \
                        SpaceBoundary.get_bound_center(opening_obj)

    def _fix_surface_orientation(self, instances: dict):
        """
        Fix orientation of space boundaries.
        Fix orientation of all surfaces but openings by sewing followed
        by disaggregation. Fix orientation of openings afterwards according
        to orientation of parent bounds.
        Args:
            instances: dict[guid: element]
        """
        self.logger.info("Fix surface orientation")
        spaces = filter_instances(instances, ThermalZone)
        for space in spaces:
            face_list = []
            for bound in space.space_boundaries:
                # get all bounds within a space except openings
                if bound.parent_bound:
                    continue
                # append all faces within the space to face_list
                face = PyOCCTools.get_face_from_shape(bound.bound_shape)
                face_list.append(face)
            if not face_list:
                continue
            # if the space has generated 2B space boundaries, add them to
            # face_list
            if hasattr(space, 'space_boundaries_2B'):
                for bound in space.space_boundaries_2B:
                    face = PyOCCTools.get_face_from_shape(bound.bound_shape)
                    face_list.append(face)
            # sew all faces within the face_list together
            sew = BRepBuilderAPI_Sewing(0.0001)
            for fc in face_list:
                sew.Add(fc)
            sew.Perform()
            sewed_shape = sew.SewedShape()
            fixed_shape = sewed_shape
            # check volume of the sewed shape. If negative, not all the
            # surfaces have the same orientation
            p = GProp_GProps()
            brepgprop_VolumeProperties(fixed_shape, p)
            if p.Mass() < 0:
                # complements the surface orientation within the fixed shape
                fixed_shape.Complement()
            # disaggregate the fixed_shape to a list of fixed_faces
            f_exp = TopExp_Explorer(fixed_shape, TopAbs_FACE)
            fixed_faces = []
            while f_exp.More():
                fixed_faces.append(topods_Face(f_exp.Current()))
                f_exp.Next()
            for fc in fixed_faces:
                # compute the surface normal for each face
                face_normal = PyOCCTools.simple_face_normal(
                   fc, check_orientation=False)
                # compute the center of mass for the current face
                p = GProp_GProps()
                brepgprop_SurfaceProperties(fc, p)
                face_center = p.CentreOfMass().XYZ()
                complemented = False
                for bound in space.space_boundaries:
                    # find the original bound by evaluating the distance of
                    # the face centers. Continue if the distance is greater
                    # than the tolerance.
                    if (gp_Pnt(bound.bound_center).Distance(gp_Pnt(face_center))
                            > 1e-3):
                        continue
                    # check if the surfaces have the same surface area
                    if (bound.bound_area.m - p.Mass()) ** 2 < 0.01:
                        # complement the surfaces if needed
                        if fc.Orientation() == 1:
                            bound.bound_shape.Complement()
                            complemented = True
                        elif face_normal.Dot(bound.bound_normal) < 0:
                            bound.bound_shape.Complement()
                            complemented = True
                        if not complemented:
                            continue
                        # complement openings if parent holds openings
                        if bound.opening_bounds:
                            op_bounds = bound.opening_bounds
                            for op in op_bounds:
                                op.bound_shape.Complement()
                        break
                if not hasattr(space, 'space_boundaries_2B'):
                    continue
                # if the current face is a generated 2b bound, just keep the
                # current face and delete the bound normal property, so it is
                # recomputed the next time it is accessed.
                for bound in space.space_boundaries_2B:
                    if gp_Pnt(bound.bound_center).Distance(gp_Pnt(face_center))\
                            < 1e-6:
                        bound.bound_shape = fc
                        if hasattr(bound, 'bound_normal'):
                            del bound.__dict__['bound_normal']
                        break

    def split_non_convex_bounds(self, instances: dict, split_bounds):
        if not split_bounds:
            return
        self.logger.info("Split non-convex surfaces")
        bounds = [instances[i] for i in instances
                  if instances[i].ifc.is_a('IfcRelSpaceBoundary')]
        bounds_except_openings = [b for b in bounds if not b.parent_bound]
        conv = []
        nconv = []
        for bound in bounds_except_openings:
            try:
                if hasattr(bound, 'convex_processed'):
                    continue
                if bound.opening_bounds:  # check all space boundaries that
                    # are not parent to an opening bound
                    if is_convex_slow(bound.bound_shape):
                        continue
                    # handle shapes that contain opening bounds
                    convex_shapes = convex_decomposition(
                        bound.bound_shape,
                        [op.bound_shape for op in bound.opening_bounds]
                    )
                else:
                    if is_convex_no_holes(bound.bound_shape):
                        continue
                    convex_shapes = convex_decomposition(bound.bound_shape)
                nconv.append(bound)
                if hasattr(bound, 'bound_normal'):
                    del bound.__dict__['bound_normal']
                new_space_boundaries = self._create_new_convex_bounds(
                    convex_shapes, bound, bound.related_bound)
                bound.convex_processed = True
                if (bound.related_bound and
                    bound.related_bound.ifc.RelatingSpace.is_a('IfcSpace'))\
                        and not bound.ifc.Description == '2b':
                    nconv.append(bound.related_bound)
                    del instances[bound.related_bound.guid]
                    bounds_except_openings.remove(bound.related_bound)
                    bound.related_bound.convex_processed = True
                del instances[bound.guid]
                for new_bound in new_space_boundaries:
                    instances[new_bound.guid] = new_bound
                    conv.append(new_bound)
            except Exception as ex:
                logger.exception("Something went wrong!")

    @staticmethod
    def _create_copy_of_space_boundary(bound: SpaceBoundary) -> SpaceBoundary:
        """
        This function creates a copy of a space boundary and deletes the
        cached properties bound_center and bound_normal. These properties are
        recomputed at the next usage of this attribute. This function can be
        used when the original geometry of the space boundary is modified.
        """
        new_bound = copy.copy(bound)
        new_bound.guid = ifcopenshell.guid.new()
        if hasattr(new_bound, 'bound_center'):
            del new_bound.__dict__['bound_center']
        if hasattr(new_bound, 'bound_normal'):
            del new_bound.__dict__['bound_normal']
        return new_bound

    def _create_new_convex_bounds(self, convex_shapes, bound,
                                  related_bound=None):
        bound.non_convex_guid = bound.guid
        new_space_boundaries = []
        openings = []
        if bound.opening_bounds:
            openings.extend(bound.opening_bounds)
        for shape in convex_shapes:
            new_bound = self._create_copy_of_space_boundary(bound)
            new_bound.bound_shape = shape
            new_bound.bound_area = SpaceBoundary.get_bound_area(new_bound)
            if openings:
                new_bound.opening_bounds = []
                for opening in openings:
                    distance = BRepExtrema_DistShapeShape(
                        new_bound.bound_shape,
                        opening.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    if distance < 1e-3:
                        new_bound.opening_bounds.append(opening)
                        opening.parent_bound = new_bound
            if not all([abs(i) < 1e-3
                        for i in ((new_bound.bound_normal
                                   - bound.bound_normal).Coord())]):
                new_bound.bound_shape = \
                    PyOCCTools.flip_orientation_of_face(new_bound.bound_shape)
                new_bound.bound_normal = \
                    PyOCCTools.simple_face_normal(new_bound.bound_shape)
            if (related_bound
                and bound.related_bound.ifc.RelatingSpace.is_a('IfcSpace')) \
                    and not bound.ifc.Description == '2b':
                distance = BRepExtrema_DistShapeShape(
                    bound.bound_shape,
                    related_bound.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                new_rel_bound = self._create_copy_of_space_boundary(
                    related_bound)
                related_bound.non_convex_guid = related_bound.guid
                if distance > 1e-3:
                    new_rel_shape = \
                        PyOCCTools.move_bound_in_direction_of_normal(
                            new_bound, distance, reverse=False)
                else:
                    new_rel_shape = new_bound.bound_shape
                new_rel_bound.bound_shape = new_rel_shape
                new_rel_bound.bound_shape = PyOCCTools.flip_orientation_of_face(
                    new_rel_bound.bound_shape)
                new_rel_bound.bound_normal = PyOCCTools.simple_face_normal(
                    new_rel_bound.bound_shape)
                new_rel_bound.bound_area = SpaceBoundary.get_bound_area(
                    new_rel_bound)
                if new_bound.opening_bounds:
                    for op in new_bound.opening_bounds:
                        if not op.related_bound:
                            continue
                        new_rel_bound.opening_bounds.append(op.related_bound)
                        op.related_bound.parent_bound = new_rel_bound
                new_bound.related_bound = new_rel_bound
                new_rel_bound.related_bound = new_bound
                new_space_boundaries.append(new_rel_bound)
            new_space_boundaries.append(new_bound)
        return new_space_boundaries

    def _split_non_convex_shadings(self, instances, spatial_bounds):
        # only considers the first spatial element for now. Extend this if
        # needed.
        spatial_elem = filter_instances(instances, ExternalSpatialElement)[0]
        for spatial in spatial_bounds:
            if is_convex_no_holes(spatial.bound_shape):
                continue
            try:
                convex_shapes = convex_decomposition(spatial.bound_shape)
            except:
                continue
            new_space_boundaries = self._create_new_convex_bounds(convex_shapes,
                                                                  spatial)
            spatial_bounds.remove(spatial)
            if spatial in spatial_elem.space_boundaries:
                spatial_elem.space_boundaries.remove(spatial)
            for new_bound in new_space_boundaries:
                spatial_bounds.append(new_bound)
                spatial_elem.space_boundaries.append(new_bound)

