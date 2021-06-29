from typing import List
from bim2sim.filter import TypeFilter
from bim2sim.kernel.element import RelationBased
from bim2sim.task.base import ITask
from bim2sim.kernel.elements.bps import SpaceBoundary, ExtSpatialSpaceBoundary
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.Extrema import Extrema_ExtFlag_MIN


class CreateSpaceBoundaries(ITask):
    """Create space boundary elements from ifc."""

    reads = ('ifc', 'instances', 'finder')
    touches = ('space_boundaries',)

    def __init__(self):
        super().__init__()
        self.non_sb_elements = []

    def run(self, workflow, ifc, instances, finder):
        self.logger.info("Creates elements of relevant ifc types")
        type_filter = TypeFilter(('IfcRelSpaceBoundary',))
        entity_type_dict, unknown_entities = type_filter.run(ifc)
        instance_lst = self.instantiate_space_boundaries(entity_type_dict,
                                                         instances, finder, workflow.create_external_elements)
        self.find_instances_openings(instances, instance_lst)
        self.logger.info("Created %d elements", len(instance_lst))

        space_boundaries = {inst.guid: inst for inst in instance_lst}
        return space_boundaries,

    def instantiate_space_boundaries(self, entities_dict, instances,
                                     finder, create_external_elements) -> List[RelationBased]:
        """Instantiate space boundary ifc_entities using given element class.
        Result is a list with the resulting valid elements"""

        instance_lst = {}
        for entity in entities_dict:
            element = None
            if entity.RelatingSpace.is_a('IfcSpace'):
                element = SpaceBoundary.from_ifc(entity, instances=instance_lst,
                                               finder=finder)
            elif create_external_elements and entity.RelatingSpace.is_a('IfcExternalSpatialElement'):
                element = ExtSpatialSpaceBoundary.from_ifc(entity, instances=instance_lst,
                                               finder=finder)
            if not element:
                continue
            # for RelatingSpaces both IfcSpace and IfcExternalSpatialElement are considered
            self.connect_space_boundaries(element, instances)
            instance_lst[element.guid] = element

        return list(instance_lst.values())

    def connect_space_boundaries(self, space_boundary, instances):
        """Connects resultant space boundary with the corresponding relating
        space and related building element (if given)"""
        relating_space = instances.get(
            space_boundary.ifc.RelatingSpace.GlobalId, None)  # todo: @Diego: what if None?
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
        no_element_sbs = self.get_no_element_space_boundaries(space_boundaries)
        no_element_openings = self.get_corresponding_opening(space_boundaries,
                                                             no_element_sbs)
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
                        return [matched_sb]
                    else:
                        self.non_sb_elements.append(opening_instance)
                else:
                    # opening with no element (stairs for example)
                    matched_sb = self.find_no_element_opening_bound(
                        no_element_openings, instance, no_element_sbs)
                    if matched_sb:
                        return matched_sb
        return None

    @staticmethod
    def get_corresponding_opening(space_boundaries, selected_sb):
        """get corresponding opening space boundary for openings that doesn't
        have a related instance"""
        corresponding = {}
        for sb_opening in selected_sb.values():
            distances = {}
            for sb in space_boundaries:
                if sb != sb_opening:
                    if (sb.bound_thermal_zone ==
                        sb_opening.bound_thermal_zone) and \
                            (sb.top_bottom == sb_opening.top_bottom):
                        shape_dist = BRepExtrema_DistShapeShape(
                            sb_opening.bound_shape,
                            sb.bound_shape,
                            Extrema_ExtFlag_MIN
                        ).Value()
                        distances[shape_dist] = sb
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
            if not normal_sb.opening_bounds:
                normal_sb.opening_bounds = []
            normal_sb.opening_bounds.append(opening_sb)
            if normal_sb.related_bound:
                if not normal_sb.related_bound.opening_bounds:
                    normal_sb.related_bound.opening_bounds = []
                normal_sb.related_bound.opening_bounds.append(opening_sb)
