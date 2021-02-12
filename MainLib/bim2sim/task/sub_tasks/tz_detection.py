from bim2sim.task.base import Task
from bim2sim.decision import BoolDecision, ListDecision
from bim2sim.kernel.element import Element, SubElement
from bim2sim.kernel.ifc2python import getElementType
from bim2sim.kernel.disaggregation import Disaggregation
from bim2sim.kernel.aggregation import Aggregated_ThermalZone
from bim2sim.task.bps_f.bps_functions import filter_instances
from bim2sim.kernel.elements import SpaceBoundary
import inspect

class Inspect(Task):
    """Analyses IFC, creates Element instances and connects them.
    elements are stored in .instances dict with guid as key"""

    def __init__(self, task, workflow):
        super().__init__()
        self.instances = {}
        self.task = task
        self.workflow = workflow

    @Task.log
    def run(self, ifc, bound_instances, storeys):
        self.logger.info("Creates python representation for building spaces")
        self.recognize_zone_semantic(ifc, bound_instances, storeys)
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

        self.logger.info("Found %d space boundaries entities", len(self.instances))

    def recognize_zone_semantic(self, ifc, bound_instances, storeys):
        """Recognizes zones/spaces in ifc file by semantic detection for
        IfcSpace entities"""
        self.logger.info("Create zones by semantic detection")
        ifc_type = 'IfcSpace'
        entities = ifc.by_type(ifc_type)
        for entity in entities:
            thermal_zone = Element.factory(entity, ifc_type)
            self.instances[thermal_zone.guid] = thermal_zone

        for storey in storeys:
            storey.set_storey_instances()
        # space boundaries creation
        self.recognize_space_boundaries(ifc)

        cooling_decision = BoolDecision(question="Do you want for all the thermal zones to be cooled? - "
                                                 "with cooling",
                                        global_key='Thermal_Zones.Cooling',
                                        allow_skip=True, allow_load=True, allow_save=True,
                                        collect=False, quick_decide=not True)
        cooling_decision.decide()
        heating_decision = BoolDecision(question="Do you want for all the thermal zones to be heated? - "
                                                 "with heating",
                                        global_key='Thermal_Zones.Heating',
                                        allow_skip=True, allow_load=True, allow_save=True,
                                        collect=False, quick_decide=not True)
        heating_decision.decide()

        self.bind_elements_to_zone(bound_instances)
        for k, tz in self.instances.items():
            tz.set_neighbors()
            if cooling_decision.value is True:
                tz.with_cooling = True
            if heating_decision.value is True:
                tz.with_heating = True
            tz.set_neighbors()

    def recognize_zone_geometrical(self):
        """Recognizes zones/spaces by geometric detection"""
        raise NotImplementedError

    def bind_elements_to_zone(self, bound_instances):
        """Binds the different elements to the belonging zones"""

        for bound_instance in bound_instances.values():
            disaggregation = {}
            for sb in bound_instance.space_boundaries:
                thermalzone = sb.thermal_zones[0]
                if sb.related_bound is not None:
                    if sb.guid in disaggregation:
                        inst = disaggregation[sb.guid]
                    else:
                        inst = Disaggregation.based_on_thermal_zone(bound_instance, sb, thermalzone)
                        disaggregation[sb.related_bound.guid] = inst
                else:
                    inst = Disaggregation.based_on_thermal_zone(bound_instance, sb, thermalzone)
                if sb not in inst.space_boundaries:
                    inst.space_boundaries.append(sb)
                if inst not in thermalzone.bound_elements:
                    thermalzone.bound_elements.append(inst)
                if thermalzone not in inst.thermal_zones:
                    inst.thermal_zones.append(thermalzone)
        # print()
        # bound_instances = {}
        # for space_boundary in thermalzone.space_boundaries:
        #     bound_instance = space_boundary.bound_instance
        #     if bound_instance.guid not in bound_instances:
        #         bound_instances[bound_instance.guid] = [space_boundary]
        #     else:
        #         bound_instances[bound_instance.guid].append(space_boundary)
        # for bound_instance, space_boundaries in bound_instances.items():
        #     original_instance = Element.get_object(bound_instance)
        #     inst = Disaggregation.based_on_thermal_zone([original_instance, space_boundaries], thermalzone)
        #     if inst not in thermalzone.bound_elements:
        #         thermalzone.bound_elements.append(inst)
        #     if thermalzone not in inst.thermal_zones:
        #         inst.thermal_zones.append(thermalzone)

    def recognize_space_boundaries(self, ifc):
        """Recognizes space boundaries in ifc file by semantic detection for
        IfcRelSpaceBoundary entities"""
        check = []
        entities = ifc.by_type('IfcRelSpaceBoundary')

        # for entity in entities:
        #     if entity.RelatedBuildingElement is not None:
        #         if entity.RelatedBuildingElement.GlobalId == '2Og5$70yb1DxR1TY1w8bzN':
        #             if entity.RelatingSpace.GlobalId == '1_Evy7T$DCiwLgTMLHCRoe':
        #                 space_boundary = SubElement.factory(entity, 'IfcRelSpaceBoundary')
        #                 check.append(space_boundary)
        #             elif entity.RelatingSpace.GlobalId == '0uC7OD3$5F7v$zL3aaoEig':
        #                 space_boundary = SubElement.factory(entity, 'IfcRelSpaceBoundary')
        #                 check.append(space_boundary)

        space_boundaries = []
        ifc_type = 'IfcRelSpaceBoundary'
        for entity in entities:
            if entity.RelatedBuildingElement is not None:
                related_element = Element.get_object(entity.RelatedBuildingElement.GlobalId)
                if related_element is not None:
                    space_boundary = SubElement.factory(entity, ifc_type)
                    space_boundaries.append(space_boundary)

        # new_space_boundaries = {}
        # no_rel_bound = {}
        # for sb in space_boundaries:
        #     bi_guid = sb.bound_instance.guid
        #     bi_class = type(sb.bound_instance).__name__
        #     if sb.related_bound is not None:
        #         if bi_guid not in new_space_boundaries:
        #             new_space_boundaries[bi_guid] = [sb]
        #         else:
        #             new_space_boundaries[bi_guid].append(sb)
        #     else:
        #         new_name = bi_guid + '_' + bi_class
        #         if new_name not in no_rel_bound:
        #             no_rel_bound[new_name] = [sb]
        #         else:
        #             no_rel_bound[new_name].append(sb)

        # for tz in self.instances.values():
        #     entities = tz.ifc.BoundedBy
        #     for entity in entities:
        #         if entity.RelatedBuildingElement is not None:
        #             related_element = Element.get_object(entity.RelatedBuildingElement.GlobalId)
        #             if related_element is not None:
        #                 space_boundary = SubElement.factory(entity, 'IfcRelSpaceBoundary')
        #                 if related_element.guid not in space_boundaries:
        #                     space_boundaries[related_element.guid] = []
        #                 space_boundaries[related_element.guid].append(space_boundary)
            # print()

        self.logger.info("Create space boundaries by semantic detection")
        # ifc_type = 'IfcRelSpaceBoundary'
        # entities = ifc.by_type(ifc_type)
        # for entity in entities:
        #     if entity.RelatedBuildingElement is not None:
        #         related_element = Element.get_object(entity.RelatedBuildingElement.GlobalId)
        #         if related_element is not None:
        #             SubElement.factory(entity, 'IfcRelSpaceBoundary')


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
        else:
            self.bind_tz_criteria()

    def bind_tz_criteria(self):
        bind_decision = BoolDecision(question="Do you want for thermal zones to be bind? - this allows to bind the "
                                              "thermal zones into a thermal zone aggregation based on different "
                                              "criteria -> Simplified operations",
                                     global_key='Thermal_Zones.Bind',
                                     allow_load=True, allow_save=True,
                                     collect=False, quick_decide=not True)
        bind_decision.decide()
        if bind_decision.value:
            criteria_functions = {}
            # this finds all the criteria methods implemented
            for k, func in dict(inspect.getmembers(self, predicate=inspect.ismethod)).items():
                if k.startswith('group_thermal_zones_'):
                    criteria_functions[k.replace('group_thermal_zones_', '')] = func
            # it ask which criteria method do you want to use, if 1 given is automatic
            if len(criteria_functions) > 0:
                criteria_decision = ListDecision("the following methods were found for the thermal zone binding",
                                                 choices=list(criteria_functions.keys()),
                                                 global_key='Thermal_Zones.Bind_Method',
                                                 allow_load=True, allow_save=True,
                                                 collect=False, quick_decide=not True)
                if not criteria_decision.status.value:
                    criteria_decision.decide()
                criteria_function = criteria_functions.get(criteria_decision.value)
                tz_groups = criteria_function()
                new_aggregations = Aggregated_ThermalZone.based_on_groups(tz_groups, self.instances)
                for inst in new_aggregations:
                    self.instances[inst.guid] = inst

    def group_thermal_zones_DIN_V_18599_1(self):
        """groups together all the thermal zones based on 4 criteria:
        * is_external
        * usage
        * external_orientation
        * neighbors criterion"""

        external_binding = []
        internal_binding = []

        # external - internal criterion
        thermal_zones = SubElement.get_class_instances('ThermalZone')
        for tz in thermal_zones:
            tz.set_is_external()
            tz.set_external_orientation()
            tz.set_glass_area()
            if tz.is_external:
                external_binding.append(tz)
            else:
                internal_binding.append(tz)

        # usage criterion + internal and external criterion
        external_binding = self.group_attribute(external_binding, 'usage')
        internal_binding = self.group_attribute(internal_binding, 'usage')
        # orientation and glass percentage criterion + external only
        for k, li in external_binding.items():
            external_binding[k] = {}
            external_binding[k] = self.group_attribute(li, 'external_orientation')
            for nk, nli in external_binding[k].items():
                external_binding[k][nk] = {}
                external_binding[k][nk] = self.group_attribute(nli, 'glass_percentage')

        grouped_instances_criteria = {}
        # groups the resultant thermal zone as a dictionary with key: all criteria in one
        # internal groups resumed
        for k, li in internal_binding.items():
            grouped_instances_criteria[str(['internal', k])] = li
        # external groups resumed
        for k, li in external_binding.items():
            for k2, li2 in li.items():
                for k3, li3 in li2.items():
                    grouped_instances_criteria[str(['external', k, k2, k3])] = li3
        # list of all thermal instances grouped:
        grouped_thermal_instances = []
        for i in grouped_instances_criteria:
            grouped_thermal_instances += grouped_instances_criteria[i]
        # ckeck not grouped instances for fourth criterion
        not_grouped_instances = []
        for tz in thermal_zones:
            if tz not in grouped_thermal_instances:
                not_grouped_instances.append(tz)
        # no similarities criterion
        if len(not_grouped_instances) > 1:
            grouped_instances_criteria['not_bind'] = not_grouped_instances

        # neighbors - filter criterion
        neighbors_decision = BoolDecision(question="Do you want for the bound-spaces to be neighbors? - adds additional"
                                                   " criteria that just bind the thermal zones that are side by side",
                                          global_key='Thermal_Zones.Neighbors',
                                          allow_load=True, allow_save=True,
                                          collect=False, quick_decide=not True)
        neighbors_decision.decide()
        if neighbors_decision.value:
            self.filter_neighbors(grouped_instances_criteria)

        return grouped_instances_criteria

    @staticmethod
    def group_attribute(thermal_zones, attribute):
        """groups together a set of thermal zones, that have an attribute in common """
        groups = {}
        for ele in thermal_zones:
            value = Bind.sub_function_groups(attribute, ele)
            if value not in groups:
                groups[value] = []
            groups[value].append(ele)
        # discard groups with one element
        for k in list(groups.keys()):
            if len(groups[k]) <= 1:
                del groups[k]
        return groups

    @staticmethod
    def sub_function_groups(attribute, tz):
        sub_functions = {'glass_percentage': Bind.glass_percentage_group,
                         'external_orientation': Bind.external_orientation_group}
        fnc_groups = sub_functions.get(attribute)
        value = getattr(tz, attribute)
        if fnc_groups is not None:
            value = fnc_groups(value)
        return value

    @staticmethod
    def glass_percentage_group(value):
        """groups together a set of thermal zones, that have common glass percentage in common """
        # groups based on Norm DIN_V_18599_1
        if 0 <= value < 30:
            value = '0-30%'
        elif 30 <= value < 50:
            value = '30-50%'
        elif 50 <= value < 70:
            value = '50-70%'
        else:
            value = '70-100%'
        return value

    @staticmethod
    def external_orientation_group(value):
        """groups together a set of thermal zones, that have external orientation in common """
        if 135 <= value < 315:
            value = 'S-W'
        else:
            value = 'N-E'
        return value

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
