import math
from typing import List

from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCC.Core.gp import gp_Pnt, gp_Dir

from bim2sim.filter import TypeFilter
from bim2sim.kernel.element import RelationBased
from bim2sim.task.base import ITask
from bim2sim.kernel.elements.bps import SpaceBoundary, ExtSpatialSpaceBoundary
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from bim2sim.utilities.common_functions import filter_instances


class CreateSpaceBoundaries(ITask):
    """Create space boundary elements from ifc."""

    reads = ('ifc', 'instances', 'finder')
    touches = ('space_boundaries', 'instances')

    def __init__(self):
        super().__init__()
        self.non_sb_elements = []

    def run(self, workflow, ifc, instances, finder):
        bldg_instances = filter_instances(instances, 'Building')
        self.logger.info("Creates elements for IfcRelSpaceBoundarys")
        type_filter = TypeFilter(('IfcRelSpaceBoundary',))
        entity_type_dict, unknown_entities = type_filter.run(ifc)
        instance_lst = self.instantiate_space_boundaries(
            entity_type_dict, instances, finder,
            workflow.create_external_elements, workflow.ifc_units)
        bound_instances = self._get_parents_and_children(instance_lst,
                                                         instances)
        instance_lst = list(bound_instances.values())
        self.logger.info("Created %d elements", len(bound_instances))

        space_boundaries = {inst.guid: inst for inst in instance_lst}
        return space_boundaries, instances,

    def _get_parents_and_children(self, boundaries, instances):
        """get parent-children relationships between IfcElements (e.g. Windows,
        Walls) and the corresponding relationships of their space boundaries"""
        self.logger.info("Compute relationships between space boundaries")
        self.logger.info("Compute relationships between openings and their "
                         "base surfaces")
        drop_list = {}  # HACK: dictionary for bounds which have to be removed
        bound_dict = {bound.guid: bound for bound in boundaries}
        temp_instances = instances.copy()
        temp_instances.update(bound_dict)
        # from instances (due to duplications)
        for inst_obj in boundaries:
            if inst_obj.level_description == "2b":
                continue
            inst_obj_space = inst_obj.ifc.RelatingSpace
            b_inst = inst_obj.bound_instance
            if b_inst is None:
                continue
            # assign opening elems (Windows, Doors) to parents and vice versa
            related_opening_elems = \
                self._get_related_of_opening_elems(b_inst, temp_instances)
            if not related_opening_elems:
                continue
            # assign space boundaries of opening elems (Windows, Doors)
            # to parents and vice versa
            for opening in related_opening_elems:
                op_bound = self._get_opening_boundary(inst_obj, inst_obj_space,
                                                      opening)
                if not op_bound:
                    continue
                # HACK:
                # find cases where opening area matches area of corresponding
                # wall (within inner loop) and reassign the current opening
                # boundary to the surrounding boundary (which is the true
                # parent boundary)
                if (inst_obj.bound_area - op_bound.bound_area).m < 0.01:
                    rel_bound, drop_list = self._reassign_opening_bounds(
                        inst_obj, op_bound, b_inst, drop_list)
                    if not rel_bound:
                        continue
                    rel_bound.opening_bounds.append(op_bound)
                    op_bound.parent_bound = rel_bound
                else:
                    inst_obj.opening_bounds.append(op_bound)
                    op_bound.parent_bound = inst_obj
        # remove boundaries from dictionary if they are false duplicates of
        # windows in shape of walls
        bound_dict = {k: v for k, v in bound_dict.items() if k not in drop_list}
        return bound_dict

    @staticmethod
    def _get_related_of_opening_elems(bound_instance, instances):
        """This function returns all opening elements of the current related
        building element which is related to the current space boundary."""
        related_opening_elems = []
        if not hasattr(bound_instance.ifc, 'HasOpenings'):
            return related_opening_elems
        if len(bound_instance.ifc.HasOpenings) == 0:
            return related_opening_elems

        for opening in bound_instance.ifc.HasOpenings:
            if hasattr(opening.RelatedOpeningElement, 'HasFillings'):
                for fill in opening.RelatedOpeningElement.HasFillings:
                    opening_obj = instances[
                        fill.RelatedBuildingElement.GlobalId]
                    related_opening_elems.append(opening_obj)
        return related_opening_elems

    @staticmethod
    def _get_opening_boundary(this_boundary, this_space, opening_elem):
        """ This function returns the related opening boundary of another
        space boundary."""
        opening_boundary = None
        distances = {}
        for op_bound in opening_elem.space_boundaries:
            if not op_bound.ifc.RelatingSpace == this_space:
                continue
            if op_bound in this_boundary.opening_bounds:
                continue
            center_shape = BRepBuilderAPI_MakeVertex(
                gp_Pnt(op_bound.bound_center)).Shape()
            center_dist = BRepExtrema_DistShapeShape(
                this_boundary.bound_shape,
                center_shape,
                Extrema_ExtFlag_MIN
            ).Value()
            if center_dist > 0.3:
                continue
            distances[center_dist] = op_bound
        sorted_distances = dict(sorted(distances.items()))
        if sorted_distances:
            opening_boundary = next(iter(sorted_distances.values()))
        return opening_boundary

    @staticmethod
    def _reassign_opening_bounds(this_boundary, opening_boundary,
                                 bound_instance,
                                 drop_list):
        """
        This function reassigns the current opening bound as an opening
        boundary of its surrounding boundary. This function only applies if
        the opening boundary has the same surface area as the assigned parent
        surface.
        HACK:
        some space boundaries have inner loops which are removed for vertical
        bounds in calc_bound_shape (elements.py). Those inner loops contain
        an additional vertical bound (wall) which is "parent" of an
        opening. EnergyPlus does not accept openings having a parent
        surface of same size as the opening. Thus, since inner loops are
        removed from shapes beforehand, those boundaries are removed from
        "instances" and the openings are assigned to have the larger
        boundary as a parent.
        """
        rel_bound = None
        drop_list[this_boundary.guid] = this_boundary
        ib = [b for b in bound_instance.space_boundaries if
              b.ifc.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries
              if
              b.bound_thermal_zone == opening_boundary.bound_thermal_zone]
        if len(ib) == 1:
            rel_bound = ib[0]
        elif len(ib) > 1:
            for b in ib:
                # check if orientation of possibly related bound is the same
                # as opening
                angle = math.degrees(
                    gp_Dir(b.bound_normal).Angle(gp_Dir(opening_boundary.bound_normal)))
                if not (angle < 0.1 or angle > 179.9):
                    continue
                distance = BRepExtrema_DistShapeShape(
                    b.bound_shape,
                    opening_boundary.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                if distance > 0.4:
                    continue
                else:
                    rel_bound = b
        else:
            tzb = [b for b in
                   opening_boundary.bound_thermal_zone.space_boundaries if
                   b.ifc.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries]
            for b in tzb:
                # check if orientation of possibly related bound is the same
                # as opening
                try:
                    angle = math.degrees(
                        gp_Dir(b.bound_normal).Angle(
                            gp_Dir(opening_boundary.bound_normal)))
                except:
                    pass
                if not (angle < 0.1 or angle > 179.9):
                    continue
                distance = BRepExtrema_DistShapeShape(
                    b.bound_shape,
                    opening_boundary.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                if distance > 0.4:
                    continue
                else:
                    rel_bound = b
        return rel_bound, drop_list

    def instantiate_space_boundaries(
            self, entities_dict, instances, finder,
            create_external_elements, ifc_units) -> List[RelationBased]:
        """Instantiate space boundary ifc_entities using given element class.
        Result is a list with the resulting valid elements"""
        instance_lst = {}
        for entity in entities_dict:
            if entity.is_a() == 'IfcRelSpaceBoundary1stLevel' or \
                    entity.Name == '1stLevel':
                continue
            if entity.RelatingSpace.is_a('IfcSpace'):
                element = SpaceBoundary.from_ifc(
                    entity, instances=instance_lst, finder=finder,
                    ifc_units=ifc_units)
            elif create_external_elements and entity.RelatingSpace.is_a(
                    'IfcExternalSpatialElement'):
                element = ExtSpatialSpaceBoundary.from_ifc(
                    entity, instances=instance_lst, finder=finder,
                    ifc_units=ifc_units)
            else:
                continue
            # for RelatingSpaces both IfcSpace and IfcExternalSpatialElement are
            # considered
            relating_space = instances.get(
                element.ifc.RelatingSpace.GlobalId, None)
            if relating_space is not None:
                self.connect_space_boundaries(element, relating_space, instances)
                instance_lst[element.guid] = element

        return list(instance_lst.values())

    def connect_space_boundaries(
            self, space_boundary, relating_space, instances):
        """Connects resultant space boundary with the corresponding relating
        space and related building element (if given)"""
        relating_space.space_boundaries.append(space_boundary)
        space_boundary.bound_thermal_zone = relating_space

        if space_boundary.ifc.RelatedBuildingElement:
            related_building_element = instances.get(
                space_boundary.ifc.RelatedBuildingElement.GlobalId, None)
            if related_building_element:
                related_building_element.space_boundaries.append(space_boundary)
                space_boundary.bound_instance = related_building_element
                self.connect_instance_to_zone(relating_space,
                                              related_building_element)

    @staticmethod
    def connect_instance_to_zone(thermal_zone, bound_instance):
        """Connects related building element and corresponding thermal zone"""
        if bound_instance not in thermal_zone.bound_elements:
            thermal_zone.bound_elements.append(bound_instance)
        if thermal_zone not in bound_instance.thermal_zones:
            bound_instance.thermal_zones.append(thermal_zone)

    def find_instances_openings(self, instances, space_boundaries):
        """find instances openings and corresponding space boundaries to that
        opening (if given)"""
        no_element_sbs = self.get_no_element_space_boundaries(
            space_boundaries)
        # todo: supposed to return all possibly virtual
        #  boundaries (due to missing bound_instances), but in fact contains
        #  all sbs of elements that are not implemented yet, such as beams,
        #  columns, curtain walls (in addition to virtual bounds)
        no_element_openings = self.get_corresponding_opening(space_boundaries,
                                                             no_element_sbs)
        # todo: no_element_sbs are supposed to be possibly virtual boundaries,
        #  why should virtual boundaries contain openings (
        #  no_element_openings)?
        # todo: add general ifcProduct class for not implemented bound_instances
        for inst in instances.values():
            matched_sb = self.get_instance_openings(inst, instances,
                                                    no_element_sbs,
                                                    no_element_openings)
            if matched_sb:
                self.add_opening_bound(matched_sb)

    def get_instance_openings(self, instance, instances, no_element_sbs,
                              no_element_openings):
        """get openings for a given instance as space boundary and opening
        instance (if given).
        An opening can have a related instance (windows, doors for example) or
        not (staircase for example)"""
        if hasattr(instance.ifc, 'HasOpenings'):
            matched_list = []
            has_no_element_openings = False
            for opening in instance.ifc.HasOpenings:
                related_building_element = opening.RelatedOpeningElement. \
                    HasFillings[0].RelatedBuildingElement if \
                    len(opening.RelatedOpeningElement.HasFillings) > 0 else None
                if related_building_element:
                    # opening with element (windows for example)
                    opening_instance = instances.get(
                        related_building_element.GlobalId, None)
                    matched_sb = self.find_opening_bound(instance,
                                                         opening_instance)
                    if matched_sb:
                        matched_list.append(matched_sb)
                    else:
                        self.non_sb_elements.append(opening_instance)
                else:
                    has_no_element_openings = True
            if has_no_element_openings:
                matched_sbs = self.find_no_element_opening_bound(
                    no_element_openings, instance, no_element_sbs)
                if matched_sbs:
                    matched_list.extend(matched_sbs)
            return matched_list
        return None

    @staticmethod
    def get_corresponding_opening(space_boundaries, selected_sb):
        """get corresponding opening space boundary for openings that doesn't
        have a related instance"""
        # todo: remove this very inefficient loop. Applied for boundaries
        #  that are supposed to be virtual boundaries, which are not supposed
        #  to have openings.
        corresponding = {}
        for sb_opening in selected_sb.values():
            if isinstance(sb_opening, ExtSpatialSpaceBoundary):
                continue
            distances = {}
            for sb in space_boundaries:
                if isinstance(sb, ExtSpatialSpaceBoundary):
                    continue
                if sb != sb_opening:
                    if (sb.bound_thermal_zone ==
                        sb_opening.bound_thermal_zone) and \
                            (sb.top_bottom == sb_opening.top_bottom):
                        shape_dist = BRepExtrema_DistShapeShape(
                            BRepBuilderAPI_MakeVertex(
                                gp_Pnt(sb_opening.bound_center)).Shape(),
                            sb.bound_shape,
                            Extrema_ExtFlag_MIN
                        ).Value()
                        distances[shape_dist] = sb
                        #todo: exclude neighboring boundaries (e.g. from beams)
            sorted_distances = dict(sorted(distances.items()))
            if len(sorted_distances) > 0:
                corresponding[sb_opening.guid] = next(
                    iter(sorted_distances.values()))
        return corresponding

    @staticmethod
    def get_no_element_space_boundaries(space_boundaries):
        """get a dictionary with all space boundaries that doesn't have a
        related building element, represents all space boundaries that could
        be a virtual opening"""
        selected_sb = {}
        for sb in space_boundaries:
            if not sb.bound_instance:
                if isinstance(sb, ExtSpatialSpaceBoundary):
                    continue
                selected_sb[sb.guid] = sb
        return selected_sb

    @staticmethod
    def find_no_element_opening_bound(no_element_openings, instance,
                                      no_element_sb):
        """for a given instance finds corresponding no element opening bounds"""
        matched = []
        for guid, sb in no_element_openings.items():
            if sb.bound_instance == instance:
                sb_opening = no_element_sb[guid]
                matched.append([sb, sb_opening])
        return matched

    @staticmethod
    def find_opening_bound(instance, opening_instance):
        """for a given instance get corresponding opening space boundary,
         applies openings that do have a related instance, physical space
         boundary"""
        distances = {}
        for sb in instance.space_boundaries:
            for sb_opening in opening_instance.space_boundaries:
                if (sb.bound_thermal_zone == sb_opening.bound_thermal_zone) \
                        and (sb.top_bottom == sb_opening.top_bottom):
                    if sb.bound_area < sb_opening.bound_area:
                        continue
                    shape_dist = BRepExtrema_DistShapeShape(
                        sb_opening.bound_shape,
                        sb.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    distances[shape_dist] = (sb, sb_opening)
        sorted_distances = dict(sorted(distances.items()))
        if len(sorted_distances) > 0:
            return next(iter(sorted_distances.values()))
        else:
            return None

    @staticmethod
    def add_opening_bound(matched_sb):
        """adds opening corresponding space boundary to the instance
        space boundary where the opening locates"""
        for normal_sb, opening_sb in matched_sb:
            opening_sb.is_opening = True
            if not normal_sb.opening_bounds:
                normal_sb.opening_bounds = []
            if opening_sb not in normal_sb.opening_bounds:
                normal_sb.opening_bounds.append(opening_sb)
            if normal_sb.related_bound:
                if not normal_sb.related_bound.opening_bounds:
                    normal_sb.related_bound.opening_bounds = []
                if opening_sb.related_bound:
                    if opening_sb.related_bound not in \
                            normal_sb.related_bound.opening_bounds:
                        normal_sb.related_bound.opening_bounds.append(
                            opening_sb.related_bound)
                else:
                    normal_sb.related_bound.opening_bounds.append(opening_sb)
