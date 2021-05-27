import inspect

from bim2sim.task.base import Task, ITask
from bim2sim.decision import BoolDecision, ListDecision
from bim2sim.kernel.element import RelationBased
from bim2sim.kernel.aggregation import AggregatedThermalZone
from bim2sim.workflow import LOD
from bim2sim.utilities.common_functions import filter_instances


class BindThermalZones(ITask):
    """Prepares bim2sim instances to later export"""
    # for 1Zone Building - workflow.spaces: LOD.low - Disaggregations not necessary
    reads = ('tz_instances', 'instances', 'finder')
    touches = ('bounded_tz',)

    def __init__(self):
        super().__init__()
        self.bounded_tz = []
        pass

    @Task.log
    def run(self, workflow, tz_instances, instances, finder):
        self.logger.info("Binds thermal zones based on criteria")
        if len(tz_instances) == 0:
            self.logger.warning("Found no spaces to bind")
        else:
            if workflow.spaces is LOD.low:
                self.bind_tz_one_zone(
                    list(tz_instances.values()), instances, finder)
            elif workflow.spaces is LOD.medium:
                self.bind_tz_criteria(instances, finder)
            else:
                self.bounded_tz = list(tz_instances.values())
            self.logger.info("obtained %d thermal zones", len(self.bounded_tz))

        return self.bounded_tz,

    def bind_tz_one_zone(self, thermal_zones, instances, finder):
        tz_group = {'one_zone_building': thermal_zones}
        new_aggregations = AggregatedThermalZone.find_matches(
            tz_group, instances, finder)
        for inst in new_aggregations:
            self.bounded_tz.append(inst)

    def bind_tz_criteria(self, instances, finder):
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
            tz_groups = criteria_function(instances)
            new_aggregations = AggregatedThermalZone.find_matches(
                tz_groups, instances, finder=finder)
            for inst in new_aggregations:
                self.bounded_tz.append(inst)

    def group_thermal_zones_by_all_criteria(self, instances):
        """groups together all the thermal zones based on 4 criteria:
        * is_external
        * usage
        * external_orientation
        * neighbors criterion"""

        thermal_zones = filter_instances(instances, 'ThermalZone')

        grouped_instances = self.group_by_is_external(thermal_zones)
        grouped_instances = self.group_grouped_tz(grouped_instances, self.group_by_usage)
        grouped_instances = self.group_grouped_tz(grouped_instances, self.group_by_external_orientation)
        grouped_instances = self.group_grouped_tz(grouped_instances, self.group_by_glass_percentage)

        self.group_not_grouped_tz(grouped_instances, thermal_zones)

        # neighbors - filter criterion
        neighbors_decision = BoolDecision(question="Do you want for the bound-spaces to be neighbors? - adds additional"
                                                   " criteria that just bind the thermal zones that are side by side",
                                          global_key='Thermal_Zones.Neighbors',
                                          allow_load=True, allow_save=True,
                                          collect=False, quick_decide=not True)
        neighbors_decision.decide()
        if neighbors_decision.value:
            self.filter_neighbors(grouped_instances)

        return grouped_instances

    def group_thermal_zones_by_is_external(self, instances):
        """groups together all the thermal zones based on criteria:
        * is_external"""

        thermal_zones = filter_instances(instances, 'ThermalZone')
        return self.group_by_is_external(thermal_zones)

    def group_thermal_zones_by_is_external_and_orientation(self, instances):
        """groups together all the thermal zones based on criteria:
        * is_external"""

        thermal_zones = filter_instances(instances, 'ThermalZone')
        grouped_instances = self.group_by_is_external(thermal_zones)
        return self.group_grouped_tz(grouped_instances, self.group_by_external_orientation)

    def group_thermal_zones_by_usage(self, instances):
        """groups together all the thermal zones based on criteria:
        * is_external"""

        thermal_zones = filter_instances(instances, 'ThermalZone')
        return self.group_by_usage(thermal_zones)

    def group_thermal_zones_by_is_external_orientation_and_usage(self, instances):
        """groups together all the thermal zones based on criteria:
        * is_external"""

        thermal_zones = filter_instances(instances, 'ThermalZone')
        grouped_instances = self.group_by_is_external(thermal_zones)
        grouped_instances = self.group_grouped_tz(grouped_instances, self.group_by_usage)
        return self.group_grouped_tz(grouped_instances, self.group_by_external_orientation)

    def group_by_is_external(self, thermal_zones: list) -> dict:
        grouped_tz = {'external': [], 'internal': []}
        for tz in thermal_zones:
            if tz.is_external:
                grouped_tz['external'].append(tz)
            else:
                grouped_tz['internal'].append(tz)
        self.discard_1_element_groups(grouped_tz)
        return grouped_tz

    def group_by_usage(self, thermal_zones: list) -> dict:
        grouped_tz = {}
        for tz in thermal_zones:
            value = getattr(tz, 'usage')
            if value not in grouped_tz:
                grouped_tz[value] = []
            grouped_tz[value].append(tz)
        self.discard_1_element_groups(grouped_tz)
        return grouped_tz

    def group_by_external_orientation(self, thermal_zones: list) -> dict:
        grouped_tz = {}
        for tz in thermal_zones:
            value = self.external_orientation_group(getattr(tz, 'external_orientation'))
            if value not in grouped_tz:
                grouped_tz[value] = []
            grouped_tz[value].append(tz)
        self.discard_1_element_groups(grouped_tz)
        return grouped_tz

    def group_by_glass_percentage(self, thermal_zones: list) -> dict:
        grouped_tz = {}
        for tz in thermal_zones:
            value = self.glass_percentage_group(getattr(tz, 'glass_percentage'))
            if value not in grouped_tz:
                grouped_tz[value] = []
            grouped_tz[value].append(tz)
        self.discard_1_element_groups(grouped_tz)
        return grouped_tz

    @staticmethod
    def discard_1_element_groups(grouped):
        for k in list(grouped.keys()):
            if len(grouped[k]) <= 1:
                del grouped[k]

    @staticmethod
    def group_grouped_tz(grouped_thermal_zones: dict, group_function) -> dict:
        grouped_tz = {}
        for group, items in grouped_thermal_zones.items():
            sub_grouped = group_function(items)
            for sub_group, sub_items in sub_grouped.items():
                grouped_name = '%s_%s' % (group, sub_group)
                grouped_tz[grouped_name] = sub_items
        return grouped_tz

    @staticmethod
    def group_not_grouped_tz(grouped_thermal_zones: dict, thermal_zones):
        # list of all thermal instances grouped:
        grouped_thermal_instances = []
        for criteria in grouped_thermal_zones:
            grouped_thermal_instances += grouped_thermal_zones[criteria]
        # check not grouped instances for fourth criterion
        not_grouped_instances = []
        for tz in thermal_zones:
            if tz not in grouped_thermal_instances:
                not_grouped_instances.append(tz)
        if len(not_grouped_instances) > 1:
            grouped_thermal_zones['not_bind'] = not_grouped_instances

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
