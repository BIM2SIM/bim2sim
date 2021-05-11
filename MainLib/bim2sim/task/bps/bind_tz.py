import inspect

from bim2sim.task.base import Task, ITask
from bim2sim.decision import BoolDecision, ListDecision
from bim2sim.kernel.element import RelationBased
from bim2sim.kernel.aggregation import AggregatedThermalZone
from bim2sim.workflow import LOD


class BindThermalZones(ITask):
    """Prepares bim2sim instances to later export"""
    # for 1Zone Building - workflow.spaces: LOD.low - Disaggregations not necessary
    reads = ('tz_instances',)
    touches = ('bounded_tz',)

    def __init__(self):
        super().__init__()
        self.bounded_tz = []
        pass

    def run(self, workflow, tz_instances):
        self.logger.info("Binds thermal zones based on criteria")
        if len(tz_instances) == 0:
            self.logger.warning("Found no spaces to bind")
        else:
            if workflow.spaces is LOD.low:
                self.bind_tz_one_zone(list(tz_instances.values()))
            elif workflow.spaces is LOD.medium:
                self.bind_tz_criteria()
            else:
                self.bounded_tz = list(tz_instances.values())
            self.logger.info("obtained %d thermal zones", len(self.bounded_tz))

        return self.bounded_tz,

    def bind_tz_one_zone(self, thermal_zones):
        tz_group = {'one_zone_building': thermal_zones}
        new_aggregations = AggregatedThermalZone.based_on_groups(tz_group)
        for inst in new_aggregations:
            self.bounded_tz.append(inst)

    def bind_tz_criteria(self):
        bind_decision = BoolDecision(question="Do you want for thermal zones to be bind? - this allows to bind the "
                                              "thermal zones into a thermal zone aggregation based on different "
                                              "criteria -> Simplified operations",
                                     global_key='Thermal_Zones.Bind',
                                     allow_load=True, allow_save=True,
                                     collect=False, quick_decide=not True)
        bind_decision.value = True
        # bind_decision.decide()
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
                new_aggregations = AggregatedThermalZone.based_on_groups(tz_groups)
                for inst in new_aggregations:
                    self.bounded_tz.append(inst)

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
            if tz.is_external:
                external_binding.append(tz)
            else:
                internal_binding.append(tz)

        # usage criterion + internal and external criterion
        external_binding = self.group_attribute(external_binding, 'usage')
        internal_binding = self.group_attribute(internal_binding, 'usage')
        # orientation and glass percentage criterion + external only
        for k, li in external_binding.items():
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
        # check not grouped instances for fourth criterion
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

    @classmethod
    def group_attribute(cls, thermal_zones, attribute):
        """groups together a set of thermal zones, that have an attribute in common """
        groups = {}
        for ele in thermal_zones:
            value = cls.sub_function_groups(attribute, ele)
            if value not in groups:
                groups[value] = []
            groups[value].append(ele)
        # discard groups with one element
        for k in list(groups.keys()):
            if len(groups[k]) <= 1:
                del groups[k]
        return groups

    @classmethod
    def sub_function_groups(cls, attribute, tz):
        sub_functions = {'glass_percentage': cls.glass_percentage_group,
                         'external_orientation': cls.external_orientation_group}
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
