import logging
from typing import Set, TYPE_CHECKING
from ifcopenshell import guid

from bim2sim.elements import bps_elements as bps
from bim2sim.elements.aggregation import AggregationMixin
from bim2sim.elements.bps_elements import InnerFloor, Roof, OuterWall, \
    GroundFloor, InnerWall, Window, InnerDoor, OuterDoor, Slab, Wall, Door, \
    ExtSpatialSpaceBoundary
from bim2sim.elements.mapping import attribute
from bim2sim.elements.mapping.units import ureg
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import AttributeDataSource

if TYPE_CHECKING:
    from bim2sim.elements.bps_elements import (BPSProduct, SpaceBoundary,
                                               ThermalZone)
logger = logging.getLogger(__name__)


class AggregatedThermalZone(AggregationMixin, bps.ThermalZone):
    """Aggregates thermal zones"""
    aggregatable_elements = {bps.ThermalZone}

    def __init__(self, elements, *args, **kwargs):
        super().__init__(elements, *args, **kwargs)
        # self.get_disaggregation_properties()
        self.bound_elements = self.bind_elements()
        self.bind_tz_to_storeys()
        self.bind_tz_to_building()
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

    def bind_tz_to_storeys(self):
        storeys = []
        for tz in self.elements:
            for storey in tz.storeys:
                if storey not in storeys:
                    storeys.append(storey)
                if self not in storey.thermal_zones:
                    storey.thermal_zones.append(self)
                if tz in storey.thermal_zones:
                    storey.thermal_zones.remove(tz)
        self.storeys = storeys

    def bind_tz_to_building(self):
        # there should be only one building, but to be sure use list and check
        buildings = []
        for tz in self.elements:
            building = tz.building
            if building not in buildings:
                buildings.append(building)
            if self not in building.thermal_zones:
                building.thermal_zones.append(self)
            if tz in building.thermal_zones:
                building.thermal_zones.remove(tz)

        if len(buildings) > 1:
            raise ValueError(
                f"An AggregatedThermalZone should only contain ThermalZone "
                f"elements from the same Building. But {self} contains "
                f"ThermalZone elements from {buildings}.")
        else:
            tz.building = buildings[0]

    @classmethod
    def find_matches(cls, groups, elements):
        """creates a new thermal zone aggregation instance
         based on a previous filtering"""
        new_aggregations = []
        thermal_zones = filter_elements(elements, 'ThermalZone')
        total_area = sum(i.gross_area for i in thermal_zones)
        for group, group_elements in groups.items():
            aggregated_tz = None
            if group == 'one_zone_building':
                name = "Aggregated_%s" % group
                aggregated_tz = cls.create_aggregated_tz(
                    name, group, group_elements, elements)
            elif group == 'not_combined':
                # last criterion no similarities
                area = sum(i.gross_area for i in groups[group])
                if area / total_area <= 0.05:
                    # Todo: usage and conditions criterion
                    name = "Aggregated_not_neighbors"
                    aggregated_tz = cls.create_aggregated_tz(
                        name, group, group_elements, elements)
            else:
                # first criterion based on similarities
                # todo reuse this if needed but currently it doesn't seem so
                # group_name = re.sub('[\'\[\]]', '', group)
                group_name = group
                name = "Aggregated_%s" % group_name.replace(', ', '_')
                aggregated_tz = cls.create_aggregated_tz(
                    name, group, group_elements, elements)
            if aggregated_tz:
                new_aggregations.append(aggregated_tz)
        return new_aggregations

    @classmethod
    def create_aggregated_tz(cls, name, group, group_elements, elements):
        aggregated_tz = cls(group_elements)
        aggregated_tz.name = name
        aggregated_tz.description = group
        for tz in aggregated_tz.elements:
            if tz.guid in elements:
                del elements[tz.guid]
        elements[aggregated_tz.guid] = aggregated_tz
        return aggregated_tz

    def _calc_net_volume(self, name) -> ureg.Quantity:
        """Calculate the thermal zone net volume"""
        return sum(tz.net_volume for tz in self.elements if
                   tz.net_volume is not None)

    net_volume = attribute.Attribute(
        functions=[_calc_net_volume],
        unit=ureg.meter ** 3,
        dependant_elements='elements'
    )

    def _intensive_calc(self, name) -> ureg.Quantity:
        """intensive properties getter - volumetric mean
        intensive_attributes = ['t_set_heat', 't_set_cool', 'height',
         'AreaPerOccupant',  'T_threshold_heating', 'activity_degree_persons',
         'fixed_heat_flow_rate_persons', 'internal_gains_moisture_no_people',
         'T_threshold_cooling', 'ratio_conv_rad_persons', 'machines',
         'ratio_conv_rad_machines', 'lighting_power',
        'ratio_conv_rad_machines', 'lighting_power', 'fixed_lighting_power',
        'ratio_conv_rad_lighting', 'maintained_illuminance',
        'lighting_efficiency_lumen', base_infiltration',
        'max_user_infiltration', 'min_ahu', 'max_ahu', 'persons']"""
        # only calculate intensive calc if all zones have this attribute
        if all([getattr(tz, name) is not None and tz.net_volume is not None for
                tz in self.elements]):
            prop_sum = sum(
                getattr(tz, name) * tz.net_volume for tz in self.elements)
            return prop_sum / self.net_volume

    def _intensive_list_calc(self, name) -> list:
        """intensive list properties getter - volumetric mean
        intensive_list_attributes = ['heating_profile', 'cooling_profile',
        'persons_profile', 'machines_profile', 'lighting_profile',
        'max_overheating_infiltration', 'max_summer_infiltration',
        'winter_reduction_infiltration']"""
        if all([getattr(tz, name) is not None and tz.net_volume is not None
                for tz in self.elements]):
            list_attrs = {'heating_profile': 24, 'cooling_profile': 24,
                          'persons_profile': 24,
                          'machines_profile': 24, 'lighting_profile': 24,
                          'max_overheating_infiltration': 2,
                          'max_summer_infiltration': 3,
                          'winter_reduction_infiltration': 3}
            length = list_attrs[name]
            aux = []
            for x in range(0, length):
                aux.append(sum(getattr(tz, name)[x] * tz.net_volume for tz in
                               self.elements if
                               getattr(tz, name)) / self.net_volume)
            return aux

    def _extensive_calc(self, name) -> ureg.Quantity:
        """extensive properties getter
        intensive_attributes = ['gross_area', 'net_area', 'volume']"""
        # only calculate extensive calc if all zones have this attribute
        if all([getattr(tz, name) is not None for tz in self.elements]):
            return sum(getattr(tz, name) for tz in self.elements)

    def _bool_calc(self, name) -> bool:
        """bool properties getter
        bool_attributes = ['with_cooling', 'with_heating', 'with_ahu',
        'use_maintained_illuminance']"""
        # todo: log
        # only calculate intensive calc if all zones have this attribute
        if all([getattr(tz, name) is not None for tz in self.elements]):
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

    usage = bps.ThermalZone.usage.to_aggregation(_get_tz_usage)
    t_set_heat = bps.ThermalZone.t_set_heat.to_aggregation(_intensive_calc)
    t_set_cool = bps.ThermalZone.t_set_cool.to_aggregation(_intensive_calc)
    t_ground = bps.ThermalZone.t_ground.to_aggregation(_intensive_calc)
    net_area = bps.ThermalZone.net_area.to_aggregation(_extensive_calc)
    gross_area = bps.ThermalZone.gross_area.to_aggregation(_extensive_calc)
    gross_volume = bps.ThermalZone.gross_volume.to_aggregation(_extensive_calc)
    height = bps.ThermalZone.height.to_aggregation(_extensive_calc)
    area_per_occupant = bps.ThermalZone.area_per_occupant.to_aggregation(
        _intensive_calc)
    with_cooling = bps.ThermalZone.with_cooling.to_aggregation(_bool_calc)
    with_heating = bps.ThermalZone.with_heating.to_aggregation(_bool_calc)
    with_ahu = bps.ThermalZone.with_ahu.to_aggregation(_bool_calc)
    heating_profile = bps.ThermalZone.heating_profile.to_aggregation(
        _intensive_list_calc)
    cooling_profile = bps.ThermalZone.cooling_profile.to_aggregation(
        _intensive_list_calc)
    persons = bps.ThermalZone.persons.to_aggregation(_intensive_calc)
    T_threshold_heating = bps.ThermalZone.T_threshold_heating.to_aggregation(
        _intensive_calc)
    T_threshold_cooling = bps.ThermalZone.T_threshold_cooling.to_aggregation(
        _intensive_calc)
    ratio_conv_rad_persons = (
        bps.ThermalZone.ratio_conv_rad_persons.to_aggregation(
        _intensive_calc))
    machines = bps.ThermalZone.machines.to_aggregation(_intensive_calc)
    ratio_conv_rad_machines = (
        bps.ThermalZone.ratio_conv_rad_machines.to_aggregation(
        _intensive_calc))
    use_maintained_illuminance = (
        bps.ThermalZone.use_maintained_illuminance.to_aggregation(
        _bool_calc))
    activity_degree_persons = (
        bps.ThermalZone.activity_degree_persons.to_aggregation(
            _intensive_calc))
    fixed_heat_flow_rate_persons = (
        bps.ThermalZone.fixed_heat_flow_rate_persons.
        to_aggregation(_intensive_calc))
    internal_gains_moisture_no_people = (
        bps.ThermalZone.internal_gains_moisture_no_people.
        to_aggregation(_intensive_calc))
    fixed_lighting_power = bps.ThermalZone.fixed_lighting_power.to_aggregation(
        _intensive_calc)
    ratio_conv_rad_lighting = (
        bps.ThermalZone.ratio_conv_rad_lighting.to_aggregation(
            _intensive_calc))
    maintained_illuminance = (
        bps.ThermalZone.maintained_illuminance.to_aggregation(
            _intensive_calc))
    lighting_efficiency_lumen = (
        bps.ThermalZone.lighting_efficiency_lumen.to_aggregation(
            _intensive_calc))
    use_constant_infiltration = (
        bps.ThermalZone.use_constant_infiltration.to_aggregation(
            _bool_calc))
    base_infiltration = bps.ThermalZone.base_infiltration.to_aggregation(
        _intensive_calc)
    max_user_infiltration = (
        bps.ThermalZone.max_user_infiltration.to_aggregation(
            _intensive_calc))
    max_overheating_infiltration = (
        bps.ThermalZone.max_overheating_infiltration.to_aggregation(
            _intensive_list_calc))
    max_summer_infiltration = (
        bps.ThermalZone.max_summer_infiltration.to_aggregation(
            _intensive_list_calc))
    winter_reduction_infiltration = (
        bps.ThermalZone.winter_reduction_infiltration.to_aggregation(
            _intensive_list_calc))
    min_ahu = bps.ThermalZone.min_ahu.to_aggregation(_intensive_calc)
    max_ahu = bps.ThermalZone.max_ahu.to_aggregation(_intensive_calc)
    with_ideal_thresholds = (
        bps.ThermalZone.with_ideal_thresholds.to_aggregation(
            _bool_calc))
    persons_profile = bps.ThermalZone.persons_profile.to_aggregation(
        _intensive_list_calc)
    machines_profile = bps.ThermalZone.machines_profile.to_aggregation(
        _intensive_list_calc)
    lighting_profile = bps.ThermalZone.lighting_profile.to_aggregation(
        _intensive_list_calc)


class SBDisaggregationMixin:
    guid_prefix = 'DisAgg_'
    disaggregatable_classes: Set['BPSProduct'] = set()
    thermal_zones = []

    def __init__(self, disagg_parent: 'BPSProduct', sbs: list['SpaceBoundary']
                 , *args, **kwargs):
        """

        Args:
            disagg_parent: Parent bim2sim element that was disaggregated
        """
        super().__init__(*args, **kwargs)
        if self.disaggregatable_classes:
            received = {type(disagg_parent)}
            mismatch = received - self.disaggregatable_classes
            if mismatch:
                raise AssertionError("Can't aggregate %s from elements: %s" %
                                     (self.__class__.__name__, mismatch))
        self.thermal_zones = [sb.bound_thermal_zone for sb in sbs]
        for tz in self.thermal_zones:
            if disagg_parent in tz.bound_elements:
                tz.bound_elements.remove(disagg_parent)
            tz.bound_elements.append(self)
        if sbs[0].related_bound and not isinstance(
                sbs[0].related_bound, ExtSpatialSpaceBoundary):
            # if the space boundary and its related_bound have different
            # bound_elements which are assigned to have the same
            # bound_element during disaggregation, the thermal zone must
            # get a reference to the newly assigned bound_element instead.
            if sbs[0].bound_element != sbs[0].related_bound.bound_element:
                if (sbs[0].related_bound.bound_element in
                        sbs[0].related_bound.bound_thermal_zone.bound_elements):
                    sbs[0].related_bound.bound_thermal_zone.bound_elements.remove(
                        sbs[0].related_bound.bound_element)
                    sbs[0].related_bound.bound_thermal_zone.bound_elements.append(
                        self)
        for sb in sbs:
            # Only set disagg_parent if disagg_parent is the element of the SB
            # because otherwise we prevent creation of disaggregations for this
            # SB
            if disagg_parent == sb.bound_element:
                sb.disagg_parent = disagg_parent
            sb.bound_element = self
            # if sb.related_bound:
            #     if not isinstance(sb.related_bound, ExtSpatialSpaceBoundary):
            #         sb.related_bound.bound_element = self
            #         sb.related_bound.disagg_parent = disagg_parent

        # set references to other elements
        self.disagg_parent = disagg_parent
        self.disagg_parent.disaggregations.append(self)
        if len(sbs) > 2:
            logger.error(f'More than 2 SBs detected here (GUID: {self}.')
        if len(sbs) == 2:
            if abs(sbs[0].net_bound_area - sbs[1].net_bound_area).m > 0.001:
                logger.error(f'Large deviation in net bound area for SBs '
                             f'{sbs[0].guid} and {sbs[1].guid}')
            if abs(sbs[0].bound_area - sbs[1].bound_area).m > 0.001:
                logger.error(f'Large deviation in net bound area for SBs '
                             f'{sbs[0].guid} and {sbs[1].guid}')

        # Get information from SB
        self.space_boundaries = sbs
        self.net_area = (
            sbs[0].net_bound_area, AttributeDataSource.space_boundary)
        self.gross_area = (
            sbs[0].bound_area, AttributeDataSource.space_boundary)
        self.opening_area = (
            sbs[0].opening_area, AttributeDataSource.space_boundary)
        # get information from disagg_parent
        for att_name, value in disagg_parent.attributes.items():
            if att_name not in ['net_area', 'gross_area', 'opening_area',
                                'gross_volume', 'net_volume']:
                self.attributes[att_name] = value
        self.layerset = disagg_parent.layerset
        self.material = disagg_parent.material
        self.material_set = disagg_parent.material_set
        self.ifc = disagg_parent.ifc
        self.storeys = disagg_parent.storeys

    @staticmethod
    def get_id(prefix=""):
        prefix_length = len(prefix)
        if prefix_length > 10:
            raise AttributeError("Max prefix length is 10!")
        ifcopenshell_guid = guid.new()[prefix_length + 1:]
        return f"{prefix}{ifcopenshell_guid}"


class InnerFloorDisaggregated(SBDisaggregationMixin, InnerFloor):
    disaggregatable_classes = {
        InnerFloor, Slab, Roof, GroundFloor}


class GroundFloorDisaggregated(SBDisaggregationMixin, GroundFloor):
    disaggregatable_classes = {
        InnerFloor, Slab, Roof, GroundFloor}


class RoofDisaggregated(SBDisaggregationMixin, Roof):
    disaggregatable_classes = {
        InnerFloor, Slab, Roof, GroundFloor}


class InnerWallDisaggregated(SBDisaggregationMixin, InnerWall):
    disaggregatable_classes = {
        Wall, OuterWall, InnerWall}


class OuterWallDisaggregated(SBDisaggregationMixin, OuterWall):
    disaggregatable_classes = {
        Wall, OuterWall, InnerWall, InnerFloor}


class InnerDoorDisaggregated(SBDisaggregationMixin, InnerDoor):
    disaggregatable_classes = {
        Door, OuterDoor, InnerDoor}


class OuterDoorDisaggregated(SBDisaggregationMixin, OuterDoor):
    disaggregatable_classes = {
        Door, OuterDoor, InnerDoor}


class WindowDisaggregated(SBDisaggregationMixin, Window):
    disaggregatable_classes = {Window}
