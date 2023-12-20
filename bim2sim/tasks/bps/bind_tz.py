from bim2sim.elements.aggregation.bps_aggregations import AggregatedThermalZone
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import LOD, ZoningCriteria


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

    # for 1Zone Building - workflow.zoning_setup: LOD.low -
    # Disaggregations not necessary
    reads = ('tz_elements', 'elements')
    touches = ('bounded_tz',)

    def __init__(self, playground):
        super().__init__(playground)
        self.bounded_tz = []

    def run(self, tz_elements, elements):
        n_zones_before = len(tz_elements)
        self.logger.info("Try to reduce number of thermal zones by merging")
        if len(tz_elements) == 0:
            self.logger.warning("Found no spaces to bind")
        else:
            if self.playground.sim_settings.zoning_setup is LOD.low:
                self.bind_tz_one_zone(
                    list(tz_elements.values()), elements)
            elif self.playground.sim_settings.zoning_setup is LOD.medium:
                self.bind_tz_criteria(elements)
            else:
                self.bounded_tz = list(tz_elements.values())
            self.logger.info("Reduced number of thermal zones from %d to  %d",
                             n_zones_before, len(self.bounded_tz))
        self.add_storeys_to_buildings(elements)

        return self.bounded_tz,

    def bind_tz_one_zone(self, thermal_zones, elements):
        """groups together all the thermal zones as one building"""
        tz_group = {'one_zone_building': thermal_zones}
        new_aggregations = AggregatedThermalZone.find_matches(
            tz_group, elements)
        for inst in new_aggregations:
            self.bounded_tz.append(inst)

    def bind_tz_criteria(self, elements):
        """groups together all the thermal zones based on selected criteria
        (answer)"""
        mapping = {
            ZoningCriteria.external: self.group_thermal_zones_by_is_external,
            ZoningCriteria.external_orientation:
                self.group_thermal_zones_by_is_external_and_orientation,
            ZoningCriteria.usage: self.group_thermal_zones_by_usage,
            ZoningCriteria.external_orientation_usage:
                self.group_thermal_zones_by_is_external_orientation_and_usage,
            ZoningCriteria.all_criteria: self.group_thermal_zones_by_use_all_criteria
        }

        criteria_function = \
            mapping[self.playground.sim_settings.zoning_criteria]
        tz_groups = criteria_function(elements)
        new_aggregations = AggregatedThermalZone.find_matches(
            tz_groups, elements)
        for inst in new_aggregations:
            self.bounded_tz.append(inst)

    @classmethod
    def group_thermal_zones_by_is_external(cls, elements):
        """groups together the thermal zones based on mixed criteria:
        * is_external"""

        thermal_zones = filter_elements(elements, 'ThermalZone')
        return cls.group_by_is_external(thermal_zones)

    @classmethod
    def group_thermal_zones_by_usage(cls, elements):
        """groups together the thermal zones based on mixed criteria
        * usage"""

        thermal_zones = filter_elements(elements, 'ThermalZone')
        return cls.group_by_usage(thermal_zones)

    @classmethod
    def group_thermal_zones_by_is_external_and_orientation(cls, elements):
        """groups together the thermal zones based on mixed criteria
        * is_external
        * orientation criteria"""

        thermal_zones = filter_elements(elements, 'ThermalZone')
        grouped_elements = cls.group_by_is_external(thermal_zones)
        return cls.group_grouped_tz(grouped_elements,
                                    cls.group_by_external_orientation)

    @classmethod
    def group_thermal_zones_by_is_external_orientation_and_usage(cls,
                                                                 elements):
        """groups together the thermal zones based on mixed criteria:
        * is_external
        * usage
        * orientation criteria"""

        thermal_zones = filter_elements(elements, 'ThermalZone')
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
    def group_thermal_zones_by_use_all_criteria(cls, elements):
        """groups together the thermal zones based on mixed criteria:
        * is_external
        * usage
        * external_orientation
        * glass percentage
        * neighbors criterion
        * not grouped tz"""

        thermal_zones = filter_elements(elements, 'ThermalZone')

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
        # list of all thermal elements grouped:
        grouped_thermal_elements = []
        for criteria in grouped_thermal_zones:
            grouped_thermal_elements += grouped_thermal_zones[criteria]
        # check not grouped elements for fourth criterion
        not_grouped_elements = []
        for tz in thermal_zones:
            if tz not in grouped_thermal_elements:
                not_grouped_elements.append(tz)
        if len(not_grouped_elements) > 1:
            grouped_thermal_zones['not_bind'] = not_grouped_elements
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
    def add_storeys_to_buildings(cls, elements):
        """adds storeys to building"""
        bldg_elements = filter_elements(elements, 'Building')
        for bldg in bldg_elements:
            for decomposed in bldg.ifc.IsDecomposedBy:
                for rel_object in decomposed.RelatedObjects:
                  if rel_object.is_a("IfcBuildingStorey"):
                    storey = elements.get(rel_object.GlobalId, None)
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