from bim2sim.elements import bps_elements as bps
from bim2sim.elements.aggregation import AggregationMixin
from bim2sim.elements.mapping import attribute
from bim2sim.elements.mapping.units import ureg
from bim2sim.utilities.common_functions import filter_instances


class AggregatedThermalZone(AggregationMixin, bps.ThermalZone):
    """Aggregates thermal zones"""
    aggregatable_elements = {bps.ThermalZone}

    def __init__(self, elements, *args, **kwargs):
        super().__init__(elements, *args, **kwargs)
        # self.get_disaggregation_properties()
        self.bound_elements = self.bind_elements()
        self.storeys = self.bind_storeys()
        self.description = ''
        # todo lump usage conditions of existing zones

    def bind_elements(self):
        """elements binder for the resultant thermal zone"""
        bound_elements = []
        for tz in self.elements:
            for inst in tz.bound_elements:
                if inst not in bound_elements:
                    bound_elements.append(inst)
        return bound_elements

    def bind_storeys(self):
        storeys = []
        for tz in self.elements:
            for storey in tz.storeys:
                if storey not in storeys:
                    storeys.append(storey)
                if self not in storey.thermal_zones:
                    storey.thermal_zones.append(self)
                if tz in storey.thermal_zones:
                    storey.thermal_zones.remove(tz)
        return storeys

    @classmethod
    def find_matches(cls, groups, instances):
        """creates a new thermal zone aggregation instance
         based on a previous filtering"""
        new_aggregations = []
        thermal_zones = filter_instances(instances, 'ThermalZone')
        total_area = sum(i.gross_area for i in thermal_zones)
        for group, group_elements in groups.items():
            if group == 'one_zone_building':
                name = "Aggregated_%s" % group
                cls.create_aggregated_tz(name, group, group_elements,
                                         new_aggregations, instances)
            elif group == 'not_bind':
                # last criterion no similarities
                area = sum(i.gross_area for i in groups[group])
                if area / total_area <= 0.05:
                    # Todo: usage and conditions criterion
                    name = "Aggregated_not_neighbors"
                    cls.create_aggregated_tz(name, group, group_elements,
                                             new_aggregations, instances)
            else:
                # first criterion based on similarities
                # todo reuse this if needed but currently it doesn't seem so
                # group_name = re.sub('[\'\[\]]', '', group)
                group_name = group
                name = "Aggregated_%s" % group_name.replace(', ', '_')
                cls.create_aggregated_tz(name, group, group_elements,
                                         new_aggregations, instances)
        return new_aggregations

    @classmethod
    def create_aggregated_tz(cls, name, group, group_elements,
                             new_aggregations, instances):
        instance = cls(group_elements)
        instance.name = name
        instance.description = group
        new_aggregations.append(instance)
        for tz in instance.elements:
            if tz.guid in instances:
                del instances[tz.guid]
        instances[instance.guid] = instance

    def _calc_net_volume(self, name) -> ureg.Quantity:
        """Calculate the thermal zone net volume"""
        return sum(tz.net_volume for tz in self.elements if
                   tz.net_volume is not None)

    net_volume = attribute.Attribute(
        functions=[_calc_net_volume],
        unit=ureg.meter ** 3,
        dependant_instances='elements'
    )

    def _intensive_calc(self, name) -> ureg.Quantity:
        """intensive properties getter - volumetric mean
        intensive_attributes = ['t_set_heat', 't_set_cool', 'height',  'AreaPerOccupant', 'typical_length',
        'typical_width', 'T_threshold_heating', 'activity_degree_persons', 'fixed_heat_flow_rate_persons',
        'internal_gains_moisture_no_people', 'T_threshold_cooling', 'ratio_conv_rad_persons', 'machines',
        'ratio_conv_rad_machines', 'lighting_power', 'ratio_conv_rad_lighting', 'infiltration_rate',
        'max_user_infiltration', 'min_ahu', 'max_ahu', 'persons']"""
        prop_sum = sum(
            getattr(tz, name) * tz.net_volume for tz in self.elements if
            getattr(tz, name) is not None and tz.net_volume is not None)
        return prop_sum / self.net_volume

    def _intensive_list_calc(self, name) -> list:
        """intensive list properties getter - volumetric mean
        intensive_list_attributes = ['heating_profile', 'cooling_profile', 'persons_profile', 'machines_profile',
         'lighting_profile', 'max_overheating_infiltration', 'max_summer_infiltration',
         'winter_reduction_infiltration']"""
        list_attrs = {'heating_profile': 24, 'cooling_profile': 24,
                      'persons_profile': 24,
                      'machines_profile': 24, 'lighting_profile': 24,
                      'max_overheating_infiltration': 2,
                      'max_summer_infiltration': 3,
                      'winter_reduction_infiltration': 3}
        length = list_attrs[name]
        aux = []
        for x in range(0, length):
            aux.append(sum(
                getattr(tz, name)[x] * tz.net_volume for tz in self.elements
                if getattr(tz, name) is not None and tz.net_volume is not None)
                       / self.net_volume)
        return aux

    def _extensive_calc(self, name) -> ureg.Quantity:
        """extensive properties getter
        intensive_attributes = ['gross_area', 'net_area', 'volume']"""
        return sum(getattr(tz, name) for tz in self.elements if
                   getattr(tz, name) is not None)

    def _bool_calc(self, name) -> bool:
        """bool properties getter
        bool_attributes = ['with_cooling', 'with_heating', 'with_ahu']"""
        # todo: log
        prop_bool = False
        for tz in self.elements:
            prop = getattr(tz, name)
            if prop is not None:
                if prop:
                    prop_bool = True
                    break
        return prop_bool

    def _get_tz_usage(self, name) -> str:
        """usage properties getter"""
        return self.elements[0].usage

    usage = attribute.Attribute(
        functions=[_get_tz_usage],
    )
    # t_set_heat = attribute.Attribute(
    #     functions=[_intensive_calc],
    #     unit=ureg.degC
    # )
    # todo refactor this to remove redundancy for units
    t_set_heat = bps.ThermalZone.t_set_heat.to_aggregation(_intensive_calc)

    t_set_cool = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.degC,
        dependant_instances='elements'
    )
    t_ground = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.degC,
        dependant_instances='elements'
    )
    net_area = attribute.Attribute(
        functions=[_extensive_calc],
        unit=ureg.meter ** 2,
        dependant_instances='elements'
    )
    gross_area = attribute.Attribute(
        functions=[_extensive_calc],
        unit=ureg.meter ** 2,
        dependant_instances='elements'
    )
    gross_volume = attribute.Attribute(
        functions=[_extensive_calc],
        unit=ureg.meter ** 3,
        dependant_instances='elements'
    )
    height = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.meter,
        dependant_instances='elements'
    )
    AreaPerOccupant = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.meter ** 2,
        dependant_instances='elements'
    )
    # use conditions
    with_cooling = attribute.Attribute(
        functions=[_bool_calc],
        dependant_instances='elements'
    )
    with_heating = attribute.Attribute(
        functions=[_bool_calc],
        dependant_instances='elements'
    )
    with_ahu = attribute.Attribute(
        functions=[_bool_calc],
        dependant_instances='elements'
    )
    heating_profile = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    cooling_profile = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    persons = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    typical_length = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    typical_width = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    T_threshold_heating = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    activity_degree_persons = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    fixed_heat_flow_rate_persons = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    internal_gains_moisture_no_people = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    T_threshold_cooling = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    ratio_conv_rad_persons = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    machines = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    ratio_conv_rad_machines = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    lighting_power = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    ratio_conv_rad_lighting = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    use_constant_infiltration = attribute.Attribute(
        functions=[_bool_calc],
        dependant_instances='elements'
    )
    infiltration_rate = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    max_user_infiltration = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    max_overheating_infiltration = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    max_summer_infiltration = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    winter_reduction_infiltration = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    min_ahu = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    max_ahu = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    with_ideal_thresholds = attribute.Attribute(
        functions=[_bool_calc],
        dependant_instances='elements'
    )
    persons_profile = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    machines_profile = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    lighting_profile = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
