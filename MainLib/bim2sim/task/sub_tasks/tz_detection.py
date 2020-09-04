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

        # thermal_zone binding example
        tz_groups = self.group_thermal_zones_2()
        new_aggregations = ThermalZone.based_on_groups(tz_groups, self.instances)
        for inst in new_aggregations:
            self.instances[inst.guid] = inst
        print()

    def group_thermal_zones_2(self):
        """groups together all the thermalzones based on three attributes:
        * is_external
        * usage
        * true_orientation """
        external_binding = []
        internal_binding = []

        for tz in self.instances.values():
            if tz.is_external:
                external_binding.append(tz)
            else:
                internal_binding.append(tz)

        external_binding = self.group_attribute2(external_binding, 'usage')
        internal_binding = self.group_attribute2(internal_binding, 'usage')
        for k, li in external_binding.items():
            external_binding[k] = {}
            external_binding[k] = self.group_attribute2(li, 'true_orientation')
            for nk, nli in external_binding[k].items():
                external_binding[k][nk] = {}
                external_binding[k][nk] = self.group_attribute2(nli, 'glass_percentage')

        temp = {}
        for k, li in internal_binding.items():
            temp[str(['internal', k])] = li
        for k, li in external_binding.items():
            for k2, li2 in li.items():
                for k3, li3 in li2.items():
                    temp[str(['external', k, k2, k3])] = li3
        temp2 = []
        for i in temp:
            temp2 += temp[i]
        temp3 = []
        for tz in self.instances.values():
            if tz not in temp2:
                temp3.append(tz)
        if len(temp3) > 1:
            temp['not_bind'] = temp3
        return temp

    @staticmethod
    def group_attribute2(thermal_zones, attribute):
        """groups together a set of thermal zones, that have an attribute in common """
        groups = {}
        for ele in thermal_zones:
            value = getattr(ele, attribute)
            # name = str(p_name) + ' - ' + str(value) if p_name is not None else value
            if value not in groups:
                groups[value] = []
            groups[value].append(ele)
        # discard groups with one element
        for k in list(groups.keys()):
            if len(groups[k]) <= 1:
                del groups[k]

        print()
        return groups

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

        thermalzone.get_is_external()
        thermalzone.get_true_orientation()
        thermalzone.get_glass_area()

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





