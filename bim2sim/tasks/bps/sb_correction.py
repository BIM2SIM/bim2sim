"""Geometric Correction of Space Boundaries.

This module contains all functions for geometric preprocessing of the BIM2SIM
Elements that are relevant for exporting EnergyPlus Input Files and other BPS
applications. Geometric preprocessing mainly relies on shape
manipulations with OpenCascade (OCC). This module is prerequisite for the
BIM2SIM PluginEnergyPlus. This module must be executed before exporting the
EnergyPlus Input file.
"""
import copy
import logging
from typing import Union

from ifcopenshell import guid
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform, \
    BRepBuilderAPI_Sewing
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepGProp import brepgprop_VolumeProperties, \
    brepgprop_SurfaceProperties
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.GProp import GProp_GProps
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods_Face, TopoDS_Shape
from OCC.Core.gp import gp_Pnt, gp_Trsf, gp_XYZ, gp_Vec

from bim2sim.elements.bps_elements import ExternalSpatialElement, SpaceBoundary, \
    SpaceBoundary2B
from bim2sim.tasks.base import ITask
from bim2sim.tasks.common.inner_loop_remover import convex_decomposition, \
    is_convex_no_holes, is_convex_slow
from bim2sim.utilities.common_functions import filter_elements, \
    get_spaces_with_bounds
from bim2sim.utilities.pyocc_tools import PyOCCTools

logger = logging.getLogger(__name__)


class CorrectSpaceBoundaries(ITask):
    """Advanced geometric preprocessing for Space Boundaries.

    This class includes all functions for advanced geometric preprocessing
    required for high level space boundary handling, e.g., required by
    EnergyPlus export.
    """
    reads = ('elements', 'space_boundaries')

    def __init__(self, playground):
        super().__init__(playground)

    def run(self, elements: dict, space_boundaries: dict[str, SpaceBoundary]):
        if not self.playground.sim_settings.correct_space_boundaries:
            return
        logger.info("Geometric correction of space boundaries started...")
        # todo: refactor elements to initial_elements.
        # todo: space_boundaries should be already included in elements
        self.add_bounds_to_elements(elements, space_boundaries)
        self.move_children_to_parents(elements)
        self.fix_surface_orientation(elements)
        self.split_non_convex_bounds(
            elements, self.playground.sim_settings.split_bounds)
        self.add_and_split_bounds_for_shadings(
            elements, self.playground.sim_settings.add_shadings,
            self.playground.sim_settings.split_shadings)
        logger.info("Geometric correction of space boundaries finished!")

    @staticmethod
    def add_bounds_to_elements(elements: dict,
                                space_boundaries: dict[str, SpaceBoundary]):
        """Add space boundaries to elements.

        This function adds those space boundaries from space_boundaries to
        elements. This includes all space boundaries included in
        space_boundaries, which bound an IfcSpace. The space boundaries which
        have been excluded during the preprocessing in the kernel are skipped
        by only considering boundaries from the space_boundaries dictionary.

        Args:
            elements: dict[guid: element]
            space_boundaries: dict[guid: SpaceBoundary]
        """
        logger.info("Creates python representation of relevant ifc types")
        instance_dict = {}
        spaces = get_spaces_with_bounds(elements)
        for space in spaces:
            for bound in space.space_boundaries:
                if not bound.guid in space_boundaries.keys():
                    continue
                instance_dict[bound.guid] = bound
        elements.update(instance_dict)

    def add_and_split_bounds_for_shadings(self, elements: dict,
                                          add_shadings: bool,
                                          split_shadings: bool):
        """Add and split shading boundaries.

        Enrich elements by space boundaries related to an
        ExternalSpatialElement if shadings are to be added in the energyplus
        workflow.

        Args:
            elements: dict[guid: element]
            add_shadings: True if shadings shall be added
            split_shadings: True if shading boundaries should be split in
                non-convex boundaries
        """
        if add_shadings:
            spatials = []
            ext_spatial_elems = filter_elements(elements,
                                                ExternalSpatialElement)
            for elem in ext_spatial_elems:
                for sb in elem.space_boundaries:
                    spatials.append(sb)
            if spatials and split_shadings:
                self.split_non_convex_shadings(elements, spatials)

    @staticmethod
    def move_children_to_parents(elements: dict):
        """Move child space boundaries to parent boundaries.

        In some IFC, the opening boundaries of external wall
        boundaries are not coplanar. This function moves external opening
        boundaries to related parent boundary (e.g. wall).

        Args:
             elements: dict[guid: element]
        """
        logger.info("Move openings to base surface, if needed")
        boundaries = filter_elements(elements, SpaceBoundary)
        for bound in boundaries:
            if bound.parent_bound:
                opening_obj = bound
                # only external openings need to be moved
                # all other are properly placed within parent boundary
                if opening_obj.is_external:
                    distance = BRepExtrema_DistShapeShape(
                        opening_obj.bound_shape,
                        opening_obj.parent_bound.bound_shape,
                        Extrema_ExtFlag_MIN).Value()
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
                        Extrema_ExtFlag_MIN).Value()
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
                    opening_obj.bound_center = SpaceBoundary.get_bound_center(
                        opening_obj)

    @staticmethod
    def fix_surface_orientation(elements: dict):
        """Fix orientation of space boundaries.

        Fix orientation of all surfaces but openings by sewing followed
        by disaggregation. Fix orientation of openings afterwards according
        to orientation of parent bounds.

        Args:
            elements: dict[guid: element]
        """
        logger.info("Fix surface orientation")
        spaces = get_spaces_with_bounds(elements)
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
                    if (gp_Pnt(bound.bound_center).Distance(
                            gp_Pnt(face_center)) > 1e-3):
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
                    if gp_Pnt(bound.bound_center).Distance(
                            gp_Pnt(face_center)) < 1e-6:
                        bound.bound_shape = fc
                        if hasattr(bound, 'bound_normal'):
                            del bound.__dict__['bound_normal']
                        break

    def split_non_convex_bounds(self, elements: dict, split_bounds: bool):
        """Split non-convex space boundaries.

        This function splits non-convex shapes of space boundaries into
        convex shapes. Convex shapes may be required for shading calculations
        in Energyplus.

        Args:
            elements: dict[guid: element]
            split_bounds: True if non-convex space boundaries should be split up
                into convex shapes.
        """
        if not split_bounds:
            return
        logger.info("Split non-convex surfaces")
        # filter elements for type SpaceBoundary
        bounds = filter_elements(elements, SpaceBoundary)
        if not bounds:
            # if no elements of type SpaceBoundary are found, this function
            # is applied on SpaceBoundary2B
            bounds = filter_elements(elements, SpaceBoundary2B)
        # filter for boundaries, that are not opening boundaries
        bounds_except_openings = [b for b in bounds if not b.parent_bound]
        conv = []  # list of new convex shapes (for debugging)
        non_conv = []  # list of old non-convex shapes (for debugging
        for bound in bounds_except_openings:
            try:
                # check if bound has already been processed
                if hasattr(bound, 'convex_processed'):
                    continue
                # check if bound is convex
                if is_convex_no_holes(bound.bound_shape):
                    continue
                # check all space boundaries that
                # are not parent to an opening bound
                if bound.opening_bounds:
                    if is_convex_slow(bound.bound_shape):
                        continue
                    # handle shapes that contain opening bounds
                    # the surface area of an opening should not be split up
                    # in the parent face, so for splitting up parent faces,
                    # the opening boundary must be considered as a non-split
                    # area
                    convex_shapes = convex_decomposition(bound.bound_shape,
                                                         [op.bound_shape for op
                                                          in
                                                          bound.opening_bounds])
                else:
                    # if bound does not have openings, simply compute its
                    # convex decomposition and returns a list of convex_shapes
                    convex_shapes = convex_decomposition(bound.bound_shape)
                non_conv.append(bound)
                if hasattr(bound, 'bound_normal'):
                    del bound.__dict__['bound_normal']
                # create new space boundaries from list of convex shapes,
                # for both the bound itself and its corresponding bound (if it
                # has
                # one)
                new_space_boundaries = self.create_new_convex_bounds(
                    convex_shapes, bound, bound.related_bound)
                bound.convex_processed = True
                # process related bounds of the processed bounds. For heat
                # transfer the corresponding boundaries need to have same
                # surface area and same number of vertices, so corresponding
                # boundaries must be split up the same way. The split up has
                # been taking care of when creating new convex bounds,
                # so they only need to be removed here.
                if (bound.related_bound and
                    bound.related_bound.ifc.RelatingSpace.is_a('IfcSpace')) \
                        and not bound.ifc.Description == '2b':
                    non_conv.append(bound.related_bound)
                    # delete the related bound from elements
                    del elements[bound.related_bound.guid]
                    bounds_except_openings.remove(bound.related_bound)
                    bound.related_bound.convex_processed = True
                # delete the current bound from elements
                del elements[bound.guid]
                # add all new created convex bounds to elements
                for new_bound in new_space_boundaries:
                    elements[new_bound.guid] = new_bound
                    conv.append(new_bound)
            except Exception as ex:
                logger.warning(f"Unexpected {ex}. Converting bound "
                               f"{bound.guid} to convex shape failed. "
                               f"{type(ex)}")

    @staticmethod
    def create_copy_of_space_boundary(bound: SpaceBoundary) -> SpaceBoundary:
        """Create a copy of a SpaceBoundary instance.

        This function creates a copy of a space boundary and deletes the
        cached properties bound_center and bound_normal. These properties are
        recomputed at the next usage of this attribute. This function can be
        used when the original geometry of the space boundary is modified.
        The new SpaceBoundary has its own unique guid.

        Args:
            bound: SpaceBoundary
        """
        new_bound = copy.copy(bound)
        new_bound.guid = guid.new()
        if hasattr(new_bound, 'bound_center'):
            del new_bound.__dict__['bound_center']
        if hasattr(new_bound, 'bound_normal'):
            del new_bound.__dict__['bound_normal']
        return new_bound

    def create_new_convex_bounds(self, convex_shapes: list[TopoDS_Shape],
                                 bound: Union[SpaceBoundary, SpaceBoundary2B],
                                 related_bound: SpaceBoundary = None):
        """Create new convex space boundaries.

        This function creates new convex space boundaries from non-convex
        space boundary shapes. As for heat transfer the corresponding boundaries
        need to have same surface area and same number of vertices,
        corresponding boundaries must be split up the same way. Thus,
        the bound itself and the corresponding boundary (related_bound) are
        treated equally here.

        Args:
            convex_shapes: List[convex TopoDS_Shape]
            bound: either SpaceBoundary or SpaceBoundary2B
            related_bound: None or SpaceBoundary (as SpaceBoundary2B do not
            have a related_bound)
        """
        # keep the original guid as non_convex_guid
        bound.non_convex_guid = bound.guid
        new_space_boundaries = []
        openings = []
        if bound.opening_bounds:
            openings.extend(bound.opening_bounds)
        for shape in convex_shapes:
            # loop through all new created convex shapes (which are subshapes
            # of the original bound) and copy the original boundary to keep
            # their properties. This new_bound has its own unique guid.
            # bound_shape and bound_area are modified to the new_convex shape.
            new_bound = self.create_copy_of_space_boundary(bound)
            new_bound.bound_shape = shape
            new_bound.bound_area = SpaceBoundary.get_bound_area(new_bound)
            if openings:
                new_bound.opening_bounds = []
                for opening in openings:
                    # map the openings to the new parent surface
                    distance = BRepExtrema_DistShapeShape(
                        new_bound.bound_shape, opening.bound_shape,
                        Extrema_ExtFlag_MIN).Value()
                    if distance < 1e-3:
                        new_bound.opening_bounds.append(opening)
                        opening.parent_bound = new_bound
            # check and fix surface normal if needed
            if not all([abs(i) < 1e-3 for i in (
                    (new_bound.bound_normal - bound.bound_normal).Coord())]):
                new_bound.bound_shape = PyOCCTools.flip_orientation_of_face(
                    new_bound.bound_shape)
                new_bound.bound_normal = PyOCCTools.simple_face_normal(
                    new_bound.bound_shape)
            # handle corresponding boundary (related_bound)
            if (related_bound and bound.related_bound.ifc.RelatingSpace.is_a(
                    'IfcSpace')) and not bound.ifc.Description == '2b':
                distance = BRepExtrema_DistShapeShape(
                    bound.bound_shape, related_bound.bound_shape,
                    Extrema_ExtFlag_MIN).Value()
                # make copy of related bound
                new_rel_bound = self.create_copy_of_space_boundary(
                    related_bound)
                related_bound.non_convex_guid = related_bound.guid
                # move shape of the current bound to the position of the
                # related bound if they have not been at the same position
                # before.
                if distance > 1e-3:
                    new_rel_shape = \
                        PyOCCTools.move_bound_in_direction_of_normal(
                            new_bound, distance, reverse=False)
                else:
                    new_rel_shape = new_bound.bound_shape
                # assign bound_shape to related_bound, flip surface
                # orientation and recompute bound_normal and bound_area.
                new_rel_bound.bound_shape = new_rel_shape
                new_rel_bound.bound_shape = PyOCCTools.flip_orientation_of_face(
                    new_rel_bound.bound_shape)
                new_rel_bound.bound_normal = PyOCCTools.simple_face_normal(
                    new_rel_bound.bound_shape)
                new_rel_bound.bound_area = SpaceBoundary.get_bound_area(
                    new_rel_bound)
                # handle opening bounds of related bound
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

    def split_non_convex_shadings(self, elements: dict,
                                  spatial_bounds: list[SpaceBoundary]):
        """Split non_convex shadings to convex shapes.

        Args:
            elements: dict[guid: element]
            spatial_bounds: list of SpaceBoundary, that are connected to an
                ExternalSpatialElement
        """
        # only considers the first spatial element for now. Extend this if
        # needed.
        spatial_elem = filter_elements(elements, ExternalSpatialElement)[0]
        for spatial in spatial_bounds:
            if is_convex_no_holes(spatial.bound_shape):
                continue
            try:
                convex_shapes = convex_decomposition(spatial.bound_shape)
            except Exception as ex:
                logger.warning(f"Unexpected {ex}. Converting shading bound "
                               f"{spatial.guid} to convex shape failed. "
                               f"{type(ex)}")
            new_space_boundaries = self.create_new_convex_bounds(convex_shapes,
                                                                 spatial)
            spatial_bounds.remove(spatial)
            if spatial in spatial_elem.space_boundaries:
                spatial_elem.space_boundaries.remove(spatial)
            for new_bound in new_space_boundaries:
                spatial_bounds.append(new_bound)
                spatial_elem.space_boundaries.append(new_bound)
