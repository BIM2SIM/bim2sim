from bim2sim.task.base import Task
from bim2sim.decision import BoolDecision
from bim2sim.kernel.element import Element, SubElement
from bim2sim.kernel.ifc2python import getElementType
from bim2sim.kernel.disaggregation import Disaggregation
from bim2sim.kernel.aggregation import ThermalZone


class Inspect(Task):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""

    def __init__(self, task, workflow):
        super().__init__()
        self.instances = {}
        self.task = task
        self.workflow = workflow

    @Task.log
    def run(self, ifc):
        self.logger.info("Creates python representation for building spaces")
        self.recognize_zone_semantic(ifc)
        if len(self.instances) == 0:
            self.logger.warning("Found no spaces by semantic detection")
            decision = BoolDecision("Try to detect zones by geometrical?")
            use = decision.decide()
            if use:
                self.recognize_zone_geometrical()
            else:
                # todo abort program, because of missing zones/spaces
                raise NotImplementedError

        self.logger.info("Found %d space entities", len(self.instances))

        self.recognize_space_boundaries(ifc)
        self.logger.info("Found %d space boundaries entities", len(self.instances))

    def recognize_zone_semantic(self, ifc):
        """Recognizes zones/spaces in ifc file by semantic detection for
        IfcSpace entities"""
        self.logger.info("Create zones by semantic detection")
        ifc_type = 'IfcSpace'
        entities = ifc.by_type(ifc_type)
        for entity in entities:
            thermal_zone = Element.factory(entity, ifc_type)
            self.instances[thermal_zone.guid] = thermal_zone
            self.bind_elements_to_zone(thermal_zone)

            thermal_zone._get_is_external()
            thermal_zone._get_true_orientation()

        tz_groups = self.group_thermal_zones()
        new_aggregations = ThermalZone.based_on_groups(tz_groups, self.instances)
        for inst in new_aggregations:
            self.instances[inst.guid] = inst
        print()

    @staticmethod
    def group_attribute(thermal_zones, attribute, p_name):
        """groups together a set of thermal zones, that have an attribute in common """
        groups = {}

        for ele in thermal_zones:
            value = getattr(ele, attribute)
            name = str(p_name) + ' - ' + str(value) if p_name is not None else value
            if name not in groups:
                groups[name] = []
            groups[name].append(ele)
        return groups

    def group_thermal_zones(self):
        """groups together all the thermalzones based on three attributes:
        * is_external
        * usage
        * true_orientation """
        groups = self.group_attribute(self.instances.values(), 'is_external', None)
        final_groups = {}
        for group in groups:
            if len(groups[group]) > 1:
                groups1 = self.group_attribute(groups[group], 'usage', group)
                for s_group in groups1:
                    if len(groups1[s_group]) > 1:
                        groups2 = self.group_attribute(groups1[s_group], 'true_orientation', s_group)
                        for sub in groups2:
                            if len(groups2[sub]) > 1:
                                final_groups[sub] = groups2[sub]
        return final_groups

    def recognize_zone_geometrical(self):
        """Recognizes zones/spaces by geometric detection"""
        raise NotImplementedError

    def bind_elements_to_zone(self, thermalzone):
        """Binds the different elements to the belonging zones"""
        bound_instances = []
        for binding in thermalzone.ifc.BoundedBy:
            bound_element = binding.RelatedBuildingElement
            if bound_element is None:
                continue
            # if bound_element_type in relevant_ifc_types:
            bound_instance = thermalzone.get_object(bound_element.GlobalId)
            if bound_instance not in bound_instances and bound_instance is not None:
                bound_instances.append(bound_instance)
        for bound_instance in bound_instances:
            new_bound_instances = Disaggregation.based_on_thermal_zone(bound_instance, thermalzone)
            for inst in new_bound_instances:
                if inst not in thermalzone.bound_elements:
                    thermalzone.bound_elements.append(inst)
                if thermalzone not in inst.thermal_zones:
                    inst.thermal_zones.append(thermalzone)
            # disaggregation check:
            # if not Disaggregation.based_on_thermal_zone(bound_instance, thermalzone):
            #     if bound_instance not in thermalzone.bound_elements:
            #         thermalzone.bound_elements.append(bound_instance)
            #     if thermalzone not in bound_instance.thermal_zones:
            #         bound_instance.thermal_zones.append(thermalzone)

    def recognize_space_boundaries(self, ifc):
        """Recognizes space boundaries in ifc file by semantic detection for
        IfcRelSpaceBoundary entities"""
        self.logger.info("Create space boundaries by semantic detection")
        ifc_type = 'IfcRelSpaceBoundary'
        entities = ifc.by_type(ifc_type)
        for entity in entities:
            space_boundary = SubElement.factory(entity, ifc_type)
            # self.instances[space_boundary.guid] = space_boundary
            self.bind_space_to_space_boundaries(space_boundary)


    def bind_space_to_space_boundaries(self, spaceboundary):
        """Binds the different spaces to the belonging zones"""
        bound_space = spaceboundary.thermal_zones[0]
        bound_instance = spaceboundary.bound_instance
        bound_space.space_boundaries.append(spaceboundary)
        if bound_instance is not None:
            bound_instance.space_boundaries.append(spaceboundary)





