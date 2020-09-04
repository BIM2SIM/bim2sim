from bim2sim.task.base import Task
from bim2sim.decision import BoolDecision
from bim2sim.kernel.element import Element, SubElement
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
        tz_groups = self.group_thermal_zones()
        # new_aggregations = ThermalZone.based_on_groups(tz_groups, self.instances)
        # for inst in new_aggregations:
        #     self.instances[inst.guid] = inst
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