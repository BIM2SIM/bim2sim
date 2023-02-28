import inspect

from bim2sim.decision import ListDecision, DecisionBunch
from bim2sim.kernel.aggregation import AggregatedThermalZone
from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.workflow import LOD


class BindThermalZones(ITask):
    """Prepares bim2sim instances to later export"""
    # for 1Zone Building - workflow.zoning_setup: LOD.low -
    # Disaggregations not necessary
    reads = ('tz_instances', 'instances')
    touches = ('bounded_tz',)

    def __init__(self):
        super().__init__()
        self.bounded_tz = []
        pass

    def run(self, workflow, tz_instances, instances):
        n_zones_before = len(tz_instances)
        self.logger.info("Try to reduce number of thermal zones by merging")
        if len(tz_instances) == 0:
            self.logger.warning("Found no spaces to bind")
        else:
            if workflow.zoning_setup is LOD.low:
                self.bind_tz_one_zone(
                    list(tz_instances.values()), instances)
            elif workflow.zoning_setup is LOD.medium:
                yield from self.bind_tz_criteria(instances)
            else:
                self.bounded_tz = list(tz_instances.values())
            self.logger.info("Reduced number of thermal zones from %d to  %d",
                             n_zones_before, len(self.bounded_tz))
        self.add_storeys_to_buildings(instances)

        return self.bounded_tz,

    def bind_tz_one_zone(self, thermal_zones, instances):
        """groups together all the thermal zones as one building"""
        tz_group = {'one_zone_building': thermal_zones}
        new_aggregations = AggregatedThermalZone.find_matches(
            tz_group, instances)
        for inst in new_aggregations:
            self.bounded_tz.append(inst)

    def bind_tz_criteria(self, instances):
        """groups together all the thermal zones based on selected criteria
        (answer)"""
        criteria_functions = {}
        # this finds all the criteria methods implemented
        for k, func in dict(
                inspect.getmembers(self, predicate=inspect.ismethod)).items():
            if k.startswith('group_thermal_zones_'):
                criteria_functions[
                    k.replace('group_thermal_zones_by', '')
                    .replace('_', ' ')] = func
        # Choose criteria function to aggregate zones
        if len(criteria_functions) > 0:
            criteria_decision = ListDecision(
                "The following methods were found to merge thermal zones:",
                choices=list(criteria_functions.keys()),
                global_key='Thermal_Zones.Bind_Method')
            yield DecisionBunch([criteria_decision])
            criteria_function = criteria_functions.get(criteria_decision.value)

            tz_groups = criteria_function(instances)
            new_aggregations = AggregatedThermalZone.find_matches(
                tz_groups, instances)
            for inst in new_aggregations:
                self.bounded_tz.append(inst)

    @classmethod
    def group_thermal_zones_by_is_external(cls, instances):
        """groups together the thermal zones based on mixed criteria:
        * is_external"""

        thermal_zones = filter_instances(instances, 'ThermalZone')
        return cls.group_by_is_external(thermal_zones)

    @classmethod
    def group_thermal_zones_by_usage(cls, instances):
        """groups together the thermal zones based on mixed criteria
        * usage"""

        thermal_zones = filter_instances(instances, 'ThermalZone')
        return cls.group_by_usage(thermal_zones)

    @classmethod
    def group_thermal_zones_by_is_external_and_orientation(cls, instances):
        """groups together the thermal zones based on mixed criteria
        * is_external
        * orientation criteria"""

        thermal_zones = filter_instances(instances, 'ThermalZone')
        grouped_instances = cls.group_by_is_external(thermal_zones)
        return cls.group_grouped_tz(grouped_instances,
                                    cls.group_by_external_orientation)

    @classmethod
    def group_thermal_zones_by_is_external_orientation_and_usage(cls,
                                                                 instances):
        """groups together the thermal zones based on mixed criteria:
        * is_external
        * usage
        * orientation criteria"""

        thermal_zones = filter_instances(instances, 'ThermalZone')
        grouped_instances = cls.group_by_is_external(thermal_zones)
        grouped_instances = cls.group_grouped_tz(grouped_instances,
                                                 cls.group_by_usage)
        return cls.group_grouped_tz(grouped_instances,
                                    cls.group_by_external_orientation)

    @classmethod
    def group_by_is_external(cls, thermal_zones: list) -> dict:
        """groups together the thermal zones based on is_external criterion"""
        grouped_tz = {'external': [], 'internal': []}
        for tz in thermal_zones:
            if tz.is_external:
                grouped_tz['external'].append(tz)
            else:
                grouped_tz['internal'].append(tz)
        cls.discard_1_element_groups(grouped_tz)
        return grouped_tz

    @classmethod
    def group_by_usage(cls, thermal_zones: list) -> dict:
        """groups together the thermal zones based on usage criterion"""
        grouped_tz = {}
        for tz in thermal_zones:
            value = getattr(tz, 'usage')
            if value not in grouped_tz:
                grouped_tz[value] = []
            grouped_tz[value].append(tz)
        cls.discard_1_element_groups(grouped_tz)
        return grouped_tz

    @classmethod
    def group_thermal_zones_by_use_all_criteria(cls, instances):
        """groups together the thermal zones based on mixed criteria:
        * is_external
        * usage
        * external_orientation
        * glass percentage
        * neighbors criterion
        * not grouped tz"""

        thermal_zones = filter_instances(instances, 'ThermalZone')

        grouped_instances = cls.group_by_is_external(
            thermal_zones)
        grouped_instances = cls.group_grouped_tz(
            grouped_instances, cls.group_by_usage)
        grouped_instances = cls.group_grouped_tz(
            grouped_instances, cls.group_by_external_orientation)
        grouped_instances = cls.group_grouped_tz(
            grouped_instances, cls.group_by_glass_percentage)
        # neighbors - filter criterion
        grouped_instances = cls.group_grouped_tz(
            grouped_instances, cls.group_by_is_neighbor)
        grouped_instances = cls.group_not_grouped_tz(
            grouped_instances, thermal_zones)

        return grouped_instances

    @classmethod
    def group_by_external_orientation(cls, thermal_zones: list) -> dict:
        """groups together the thermal zones based on external_orientation
        criterion"""
        grouped_tz = {}
        for tz in thermal_zones:
            value = cls.external_orientation_group(
                getattr(tz, 'external_orientation'))
            if value not in grouped_tz:
                grouped_tz[value] = []
            grouped_tz[value].append(tz)
        cls.discard_1_element_groups(grouped_tz)
        return grouped_tz

    @classmethod
    def group_by_glass_percentage(cls, thermal_zones: list) -> dict:
        """groups together the thermal zones based on glass percentage
        criterion"""
        grouped_tz = {}
        for tz in thermal_zones:
            value = cls.glass_percentage_group(getattr(tz, 'glass_percentage'))
            if value not in grouped_tz:
                grouped_tz[value] = []
            grouped_tz[value].append(tz)
        cls.discard_1_element_groups(grouped_tz)
        return grouped_tz

    @classmethod
    def group_by_is_neighbor(cls, thermal_zones: list) -> dict:
        """groups together the thermal zones based on is_neighbor criterion"""
        grouped_tz = {'': list(thermal_zones)}
        for tz in thermal_zones:
            neighbor_statement = False
            for neighbor in tz.space_neighbors:
                if neighbor in thermal_zones:
                    neighbor_statement = True
                    break
            if not neighbor_statement:
                grouped_tz[''].remove(tz)
        cls.discard_1_element_groups(grouped_tz)
        return grouped_tz

    @staticmethod
    def discard_1_element_groups(grouped):
        """discard 1 element group, since a group only makes sense if it has
         more than 1 thermal zone"""
        for k in list(grouped.keys()):
            if len(grouped[k]) <= 1:
                del grouped[k]

    @classmethod
    def group_grouped_tz(cls, grouped_thermal_zones: dict, group_function) -> \
            dict:
        """groups together thermal zones, that were already grouped in previous
         steps"""
        grouped_tz = {}
        external_functions = [cls.group_by_external_orientation,
                              cls.group_by_glass_percentage]
        for group, items in grouped_thermal_zones.items():
            if group_function in external_functions and 'internal' in group:
                grouped_tz[group] = items
            else:
                sub_grouped = group_function(items)
                for sub_group, sub_items in sub_grouped.items():
                    grouped_name = '%s_%s' % (group, sub_group)
                    grouped_tz[grouped_name] = sub_items
        return grouped_tz

    @staticmethod
    def group_not_grouped_tz(grouped_thermal_zones: dict, thermal_zones):
        """groups together thermal zones, that are not already grouped in
        previous steps based on Norm DIN_V_18599_1"""
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
        return grouped_thermal_zones

    @staticmethod
    def glass_percentage_group(value):
        """locates glass percentage value on one of four groups based on
        Norm DIN_V_18599_1
        * 0-30%
        * 30-50%
        * 50-70%
        * 70-100%"""
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
        """locates external orientation value on one of two groups:
        * S-W
        * N-E"""
        if 135 <= value < 315:
            value = 'S-W'
        else:
            value = 'N-E'
        return value

    @classmethod
    def add_storeys_to_buildings(cls, instances):
        """adds storeys to building"""
        bldg_instances = filter_instances(instances, 'Building')
        for bldg in bldg_instances:
            for decomposed in bldg.ifc.IsDecomposedBy:
                for storey_ifc in decomposed.RelatedObjects:
                    storey = instances.get(storey_ifc.GlobalId, None)
                    if storey and storey not in bldg.storeys:
                        bldg.storeys.append(storey)
            cls.add_thermal_zones_to_building(bldg)

    @staticmethod
    def add_thermal_zones_to_building(bldg):
        """adds thermal zones to building"""
        for storey in bldg.storeys:
            for tz in storey.thermal_zones:
                if tz not in bldg.thermal_zones:
                    bldg.thermal_zones.append(tz)
