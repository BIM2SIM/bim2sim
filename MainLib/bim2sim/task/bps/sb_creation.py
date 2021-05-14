from typing import List
from bim2sim.filter import TypeFilter
from bim2sim.kernel.element import RelationBased
from bim2sim.task.base import ITask, Task
from bim2sim.kernel.elements.bps import SpaceBoundary
from bim2sim.kernel.finder import TemplateFinder


class CreateSpaceBoundaries(ITask):
    """Create internal elements from ifc."""

    reads = ('ifc', 'instances',)
    touches = ('space_boundaries', )

    def run(self, workflow, ifc, instances):
        self.logger.info("Creates elements of relevant ifc types")
        type_filter = TypeFilter(('IfcRelSpaceBoundary',))
        entity_type_dict, unknown_entities = type_filter.run(ifc)
        instance_lst = self.instantiate_space_boundaries(entity_type_dict, instances)
        self.logger.info("Created %d elements", len(instance_lst))

        space_boundaries = {inst.guid: inst for inst in instance_lst}
        return space_boundaries,

    @Task.log
    def instantiate_space_boundaries(self, entities_dict, instances) -> List[RelationBased]:
        """Instantiate ifc_entities using given element class.
        Resulting instances are validated (if not force).
        Results are two lists, one with valid elements and one with
        remaining entities."""

        instance_lst = []
        for entity in entities_dict:
            element = SpaceBoundary.from_ifc(entity, finder=TemplateFinder())
            self.connect_space_boundaries(element, instances)
            instance_lst.append(element)

        return instance_lst

    def connect_space_boundaries(self, space_boundary, instances):
        relating_space = instances.get(space_boundary.ifc.RelatingSpace.GlobalId, None)
        relating_space.space_boundaries.append(space_boundary)
        space_boundary.bound_thermal_zone = relating_space
        # space_boundary.thermal_zones.append(relating_space)  # ToDo: Delete?

        if space_boundary.ifc.RelatedBuildingElement:
            related_building_element = instances.get(space_boundary.ifc.RelatedBuildingElement.GlobalId, None)
            if related_building_element:
                related_building_element.space_boundaries.append(space_boundary)
                space_boundary.bound_instance = related_building_element
                self.connect_instance_to_zone(relating_space, related_building_element)

    @staticmethod
    def connect_instance_to_zone(thermal_zone, bound_instance):
        if bound_instance not in thermal_zone.bound_elements:
            thermal_zone.bound_elements.append(bound_instance)
        if thermal_zone not in bound_instance.thermal_zones:
            bound_instance.thermal_zones.append(thermal_zone)
