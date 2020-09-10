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

        for k, tz in self.instances.items():
            tz.get_neighbors()

        # bind example
        # tz_bind = Bind(self, self.workflow)
        # tz_bind.run(self.instances)

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
            self.instances[space_boundary.guid] = space_boundary
            self.bind_space_to_space_boundaries(space_boundary)

    def bind_space_to_space_boundaries(self, spaceboundary):
        """Binds the different spaces to the belonging zones"""
        bound_space = spaceboundary.thermal_zones[0]
        bound_instance = spaceboundary.bound_instance
        bound_space.space_boundaries.append(spaceboundary)
        if bound_instance is not None:
            bound_instance.space_boundaries.append(spaceboundary)


class Bind(Task):
    """Analyses thermal zone instances, bind instances and connects them.
    based on various criteria
    elements are stored in .instances dict with guid as key"""

    def __init__(self, task, workflow):
        super().__init__()
        self.instances = {}
        self.task = task
        self.workflow = workflow

    @Task.log
    def run(self, instances):
        self.logger.info("Binds thermal zones based on criteria")
        self.instances = instances
        if len(self.instances) == 0:
            self.logger.warning("Found no spaces to bind")

        tz_groups = self.group_thermal_zones()
        new_aggregations = ThermalZone.based_on_groups(tz_groups, self.instances)
        for inst in new_aggregations:
            self.instances[inst.guid] = inst

    def group_thermal_zones(self):
        """groups together all the thermalzones based on three attributes:
        * is_external
        * usage
        * true_orientation
        * neighbors criterion"""

        external_binding = []
        internal_binding = []

        # external - internal criterion
        for tz in self.instances.values():
            if tz.is_external:
                external_binding.append(tz)
            else:
                internal_binding.append(tz)

        # usage criterion - internal and external
        external_binding = self.group_attribute(external_binding, 'usage')
        internal_binding = self.group_attribute(internal_binding, 'usage')
        # orientation and glass percentage criterion - external only
        for k, li in external_binding.items():
            external_binding[k] = {}
            #
            external_binding[k] = self.group_attribute(li, 'true_orientation')
            for nk, nli in external_binding[k].items():
                external_binding[k][nk] = {}
                external_binding[k][nk] = self.group_attribute(nli, 'glass_percentage')

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
        # no similarities criterion
        if len(temp3) > 1:
            temp['not_bind'] = temp3

        # neighbors - filter criterion
        self.filter_neighbors(temp)

        return temp

    @staticmethod
    def group_attribute(thermal_zones, attribute):
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
        return groups

    @staticmethod
    def filter_neighbors(tz_groups):
        """filters the thermal zones groups, based on the thermal zones that
        are neighbors"""
        for group, tz_group in tz_groups.items():
            for tz in list(tz_group):
                neighbor_statement = False
                for neighbor in tz.space_neighbors:
                    if neighbor in tz_group:
                        neighbor_statement = True
                        break
                if not neighbor_statement:
                    tz_groups[group].remove(tz)

        for group in list(tz_groups.keys()):
            if len(tz_groups[group]) <= 1:
                del tz_groups[group]




    # @staticmethod
    # def check_neighbors(thermal_zones, attribute):
    #     """groups together a set of thermal zones, that have an attribute in common """





