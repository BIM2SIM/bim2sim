from bim2sim.elements.aggregation.bps_aggregations import AggregatedThermalZone
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import LOD, ZoningCriteria
from typing import Callable


class CombineThermalZones(ITask):
    """Combine thermal zones to reduce the amount of thermal zones.

    As the zoning of simulation models is a time-consuming task we decided to
    automate it with the tasks.
    This task will combine multiple thermal zones into one zone based on the
    criteria selected in the simulation type settings and the decisions made.
    We do this by giving the user multiple criteria to select from:
        * External/Internal
        * Orientation
        * Usage
        * Window to wall ratio
    """
    reads = ('elements',)

    def run(self, elements: dict):
        tz_elements = filter_elements(elements, 'ThermalZone')
        n_zones_before = len(tz_elements)
        self.logger.info("Try to reduce number of thermal zones by combining.")
        if len(tz_elements) == 0:
            self.logger.warning("Found no ThermalZones to combine.")
        else:
            if self.playground.sim_settings.zoning_setup is LOD.low:
                self.combine_tzs_to_one_zone(
                    tz_elements, elements)
            elif self.playground.sim_settings.zoning_setup is LOD.medium:
                self.combine_tzs_based_on_criteria(tz_elements, elements)
            tz_elements_after = filter_elements(
                elements, 'ThermalZone')
            self.logger.info(f"Reduced number of ThermalZone elements from"
                             f" {n_zones_before} to  {len(tz_elements_after)}")

    @staticmethod
    def combine_tzs_to_one_zone(thermal_zones: list, elements: dict):
        """groups together all the thermal zones as one building"""
        tz_group = {'one_zone_building': thermal_zones}
        new_aggregations = AggregatedThermalZone.find_matches(
            tz_group, elements)

    def combine_tzs_based_on_criteria(self, thermal_zones: list, elements: dict):
        """groups together all the thermal zones based on selected criteria
        (answer)"""
        mapping = {
            ZoningCriteria.external:
                self.group_thermal_zones_by_is_external,
            ZoningCriteria.external_orientation:
                self.group_thermal_zones_by_is_external_and_orientation,
            ZoningCriteria.usage:
                self.group_thermal_zones_by_usage,
            ZoningCriteria.external_orientation_usage:
                self.group_thermal_zones_by_is_external_orientation_and_usage,
            ZoningCriteria.all_criteria:
                self.group_thermal_zones_by_use_all_criteria
        }

        criteria_function = \
            mapping[self.playground.sim_settings.zoning_criteria]
        tz_groups = criteria_function(thermal_zones)
        new_aggregations = AggregatedThermalZone.find_matches(
            tz_groups, elements)

    @classmethod
    def group_thermal_zones_by_is_external(cls, thermal_zones: list):
        """groups together the thermal zones based on mixed criteria:
        * is_external"""

        return cls.group_by_is_external(thermal_zones)

    @classmethod
    def group_thermal_zones_by_usage(cls, thermal_zones: list):
        """groups together the thermal zones based on mixed criteria
        * usage"""

        return cls.group_by_usage(thermal_zones)

    @classmethod
    def group_thermal_zones_by_is_external_and_orientation(
            cls, thermal_zones: list):
        """groups together the thermal zones based on mixed criteria
        * is_external
        * orientation criteria"""

        grouped_elements = cls.group_by_is_external(thermal_zones)
        return cls.group_grouped_tz(grouped_elements,
                                    cls.group_by_external_orientation)

    @classmethod
    def group_thermal_zones_by_is_external_orientation_and_usage(
            cls, thermal_zones: list):
        """groups together the thermal zones based on mixed criteria:
        * is_external
        * usage
        * orientation criteria"""

        grouped_elements = cls.group_by_is_external(thermal_zones)
        grouped_elements = cls.group_grouped_tz(grouped_elements,
                                                 cls.group_by_usage)
        return cls.group_grouped_tz(grouped_elements,
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
    def group_thermal_zones_by_use_all_criteria(cls, thermal_zones: list):
        """groups together the thermal zones based on mixed criteria:
        * is_external
        * usage
        * external_orientation
        * glass percentage
        * neighbors criterion
        * not grouped tz"""

        grouped_elements = cls.group_by_is_external(
            thermal_zones)
        grouped_elements = cls.group_grouped_tz(
            grouped_elements, cls.group_by_usage)
        grouped_elements = cls.group_grouped_tz(
            grouped_elements, cls.group_by_external_orientation)
        grouped_elements = cls.group_grouped_tz(
            grouped_elements, cls.group_by_glass_percentage)
        # neighbors - filter criterion
        grouped_elements = cls.group_grouped_tz(
            grouped_elements, cls.group_by_is_neighbor)
        grouped_elements = cls.group_not_grouped_tz(
            grouped_elements, thermal_zones)

        return grouped_elements

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
        grouped_tz: dict = {}
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
    def discard_1_element_groups(grouped: dict):
        """discard 1 element group, since a group only makes sense if it has
         more than 1 thermal zone"""
        for k in list(grouped.keys()):
            if len(grouped[k]) <= 1:
                del grouped[k]

    @classmethod
    def group_grouped_tz(cls, grouped_thermal_zones: dict, group_function: Callable) -> \
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
    def group_not_grouped_tz(grouped_thermal_zones: dict, thermal_zones: list):
        """groups together thermal zones, that are not already grouped in
        previous steps based on Norm DIN_V_18599_1"""
        # list of all thermal elements grouped:
        grouped_thermal_elements = []
        for criteria in grouped_thermal_zones:
            grouped_thermal_elements += grouped_thermal_zones[criteria]
        # check not grouped elements for fourth criterion
        not_grouped_elements: list = []
        for tz in thermal_zones:
            if tz not in grouped_thermal_elements:
                not_grouped_elements.append(tz)
        if len(not_grouped_elements) > 1:
            grouped_thermal_zones['not_combined'] = not_grouped_elements
        return grouped_thermal_zones

    @staticmethod
    def glass_percentage_group(value: float):
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
    def external_orientation_group(value: float):
        """locates external orientation value on one of two groups:
        * S-W
        * N-E"""
        if 135 <= value < 315:
            value = 'S-W'
        else:
            value = 'N-E'
        return value
