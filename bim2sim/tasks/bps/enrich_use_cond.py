from typing import Union, Dict

from bim2sim.kernel.decision import ListDecision, DecisionBunch
from bim2sim.elements.bps_elements import ThermalZone
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import get_use_conditions_dict, \
    get_effective_usage_data, wildcard_match, filter_elements
from bim2sim.tasks.base import Playground
from bim2sim.sim_settings import BuildingSimSettings
from bim2sim.utilities.types import AttributeDataSource
import re
from typing import Dict

class EnrichUseConditions(ITask):
    """Enriches Use Conditions of thermal zones
    based on decisions and translation of zone names"""

    reads = ('elements',)

    def __init__(self, playground: Playground):
        super().__init__(playground)
        self.enriched_tz: list = []
        self.use_conditions: dict = {}
    def run(self, elements: dict):
        """Enriches Use Conditions of thermal zones and central AHU settings.

        Enrichment data in the files commonUsages.json and UseConditions.json
        is taken from TEASER. The underlying data comes from DIN 18599-10 and
        SIA 2024.
        """
        tz_elements = filter_elements(elements, 'ThermalZone', True)
        # case no thermal zones found
        if len(tz_elements) == 0:
            self.logger.warning("Found no spaces to enrich")
        else:
            custom_use_cond_path = (
                self.playground.sim_settings.prj_use_conditions)
            custom_usage_path = \
                self.playground.sim_settings.prj_custom_usages

            self.logger.info("enriches thermal zones usage")
            self.use_conditions, pattern_usage = get_effective_usage_data(custom_usage_path, custom_use_cond_path)
            final_usages = yield from self.enrich_usages(
                pattern_usage, tz_elements)
            for tz, usage in final_usages.items():
                orig_usage = tz.usage
                tz.usage = usage
                self.load_usage(tz)
                # overwrite loaded heating and cooling profiles with
                # template values if setpoints_from_template == True
                if self.playground.sim_settings.setpoints_from_template:
                    tz.heating_profile = \
                        self.use_conditions[usage]['heating_profile']
                    tz.cooling_profile = \
                        self.use_conditions[usage]['cooling_profile']
                # set maintained illuminance from sim_setting
                tz.use_maintained_illuminance = (
                    self.playground.sim_settings.use_maintained_illuminance,
                    AttributeDataSource.enrichment)
                # reset lighting_power if it was calculated before
                tz.reset('lighting_power')
                self.enriched_tz.append(tz)
                self.logger.info('Enrich ThermalZone from IfcSpace with '
                                 'original usage "%s" with usage "%s"',
                                 orig_usage, usage)
            # set heating and cooling based on sim settings configuration
            building_elements = filter_elements(elements, 'Building')
            self.overwrite_heating_cooling_ahu_by_settings(
                tz_elements, building_elements, self.playground.sim_settings)



    @staticmethod
    def overwrite_heating_cooling_ahu_by_settings(
            tz_elements: dict,
            bldg_elements: list,
            sim_settings: BuildingSimSettings) -> None:
        """Set HVAC settings for thermal zones based on simulation settings.

        Updates heating, cooling, and AHU usage for all thermal zones
         according to the provided simulation settings.

        Args:
            tz_elements: Dictionary of thermal zone elements
            bldg_elements: List of building elements
            sim_settings: Building simulation settings
        """
        # Apply settings to all thermal zones
        for tz in tz_elements.values():
            if sim_settings.heating_tz_overwrite is not None:
                tz.with_heating = (sim_settings.heating_tz_overwrite,
                                   AttributeDataSource.enrichment)
            if sim_settings.cooling_tz_overwrite is not None:
                tz.with_cooling = (sim_settings.cooling_tz_overwrite,
                                   AttributeDataSource.enrichment)
            if sim_settings.ahu_tz_overwrite is not None:
                tz.with_ahu = (sim_settings.ahu_tz_overwrite,
                               AttributeDataSource.enrichment)
            if sim_settings.base_infiltration_rate_overwrite is not None:
                tz.base_infiltration = (
                    sim_settings.base_infiltration_rate_overwrite,
                    AttributeDataSource.enrichment)
            if sim_settings.use_constant_infiltration_overwrite is not None:
                tz.use_constant_infiltration = (
                    sim_settings.use_constant_infiltration_overwrite,
                    AttributeDataSource.enrichment)

        # overwrite building AHU settings if sim_settings are used
        for building in bldg_elements:
            if sim_settings.ahu_heating_overwrite is not None:
                building.ahu_heating = (
                    sim_settings.ahu_heating_overwrite,
                    AttributeDataSource.enrichment)
            if sim_settings.ahu_cooling_overwrite is not None:
                building.ahu_cooling = (
                    sim_settings.ahu_cooling_overwrite,
                    AttributeDataSource.enrichment)
            if sim_settings.ahu_humidification_overwrite is not None:
                building.ahu_humidification = (
                    sim_settings.ahu_humidification_overwrite,
                    AttributeDataSource.enrichment)
            if sim_settings.ahu_dehumidification_overwrite is not None:
                building.ahu_dehumidification = (
                    sim_settings.ahu_dehumidification_overwrite,
                    AttributeDataSource.enrichment)
            if sim_settings.ahu_heat_recovery_overwrite is not None:
                building.ahu_heat_recovery = (
                    sim_settings.ahu_heat_recovery_overwrite,
                    AttributeDataSource.enrichment)
            if sim_settings.ahu_heat_recovery_efficiency_overwrite is not None:
                building.ahu_heat_recovery_efficiency = (
                    sim_settings.ahu_heat_recovery_efficiency_overwrite,
                    AttributeDataSource.enrichment)

            # reset with_ahu on building level to make sure that _check_tz_ahu
            #  is performed again
            building.reset('with_ahu')



    @staticmethod
    def list_decision_usage(tz: ThermalZone, choices: list) -> ListDecision:
        """decision to select an usage that matches the zone name

        Args:
            tz: bim2sim ThermalZone element
            choices: list of possible answers
        Returns:
            usage_decision: ListDecision to find the correct usage
            """
        usage_decision = ListDecision("Which usage does the Space %s have?" %
                                      (str(tz.usage)),
                                      choices=choices,
                                      key='usage_'+str(tz.usage),
                                      related=tz,
                                      global_key="%s_%s.BpsUsage" %
                                                 (type(tz).__name__, tz.guid),
                                      allow_skip=False,
                                      live_search=True)
        return usage_decision

    @staticmethod
    def office_usage(tz: ThermalZone) -> Union[str, list]:
        """function to determine which office usage is best fitting"

        The used enrichment for usage conditions come from DIN 18599-10. This
        standard offers 3 types of office usages:
        * Single office (1 workplace)
        * Group office (2 - 6 workplaces)
        * Open open offices (> 6 workplaces)

        Based on the standards given medium occupancy density the following area
        sections are defined.
        * Single office < 14 m2
        * Group office [14m2; 70 m2]
            (70 m² is lower bound from open plan office)
        * Open plan office > 70 m²

        Args:
            tz: bim2sim thermalzone element
        Returns
            matching usage as string or a list of str of no fitting
            usage could be found
        """

        default_matches = ["Single office",
                           "Group Office (between 2 and 6 employees)",
                           "Open-plan Office (7 or more employees)"]
        if tz.gross_area:
            area = tz.gross_area.m
            if area < 14:
                return default_matches[0]
            elif 14 <= area <= 70:
                return default_matches[1]
            else:
                return default_matches[2]
            # case area not available
        else:
            return default_matches

    @classmethod
    def enrich_usages(
            cls,
            pattern_usage: dict,
            thermal_zones: Dict[str, ThermalZone]) -> Dict[str, ThermalZone]:
        """
        Enriches the usage field of given thermal_zones using the pattern_usage.
        """
        def clean_usage_name(usage_str):
            """Remove suffixes like B-EG-002 from a usage string."""
            parts = usage_str.split()
            return ' '.join([p for p in parts if not re.match(r'^B-[A-Z0-9]+-\d+$', p)])

        def match_zone_usage(tz_usage, pattern_usage):
            """Returns the best matching usage or a list of possible ones."""
            original_usage = tz_usage
            usage = clean_usage_name(tz_usage)
            usage_words = usage.replace(' (', ' ').replace(')', ' ') \
                            .replace(' -', ' ').replace(', ', ' ').split()
            matches = []

            for usage_key, patterns in pattern_usage.items():
                # Check custom patterns
                for custom in patterns.get("custom", []):
                    if "*" in custom or "?" in custom:
                        regex = re.compile('^' + custom.replace("*", ".*").replace("?", ".") + '$', re.IGNORECASE)
                        if regex.match(original_usage):
                            matches.append(usage_key)
                            break
                    else:
                        if custom.lower() in usage.lower():
                            matches.append(usage_key)
                            break

                # If no match yet, check common patterns
                if usage_key not in matches:
                    for common_regex in patterns.get("common", []):
                        for word in usage_words:
                            if common_regex.match(word):
                                matches.append(usage_key)
                                break
                        if usage_key in matches:
                            break

            return matches

        final_usages = {}
        for tz in list(thermal_zones.values()):
            orig_usage = str(tz.usage)
            if orig_usage in pattern_usage:
                final_usages[tz] = orig_usage
            else:
                matches = match_zone_usage(orig_usage, pattern_usage)
                if len(matches) == 1:
                    if matches[0] == 'office_function':
                        office_use = cls.office_usage(tz)
                        final_usages[tz] = cls.list_decision_usage(tz, office_use) if isinstance(office_use, list) else office_use
                    else:
                        final_usages[tz] = matches[0]
                # if no matches given forward all (for decision)
                elif len(matches) == 0:
                    matches = list(pattern_usage.keys())
                    final_usages[tz] = cls.list_decision_usage(tz, matches)
                elif len(matches) > 1:
                    # Multiple matches found
                    final_usages[tz] = cls.list_decision_usage(tz, matches)

        # collect decisions
        usage_dec_bunch = DecisionBunch()
        for tz, use_or_dec in final_usages.items():
            if isinstance(use_or_dec, ListDecision):
                usage_dec_bunch.append(use_or_dec)
        # remove duplicate decisions
        unique_decisions, doubled_decisions = usage_dec_bunch.get_reduced_bunch(
            criteria='key')
        yield unique_decisions
        answers = unique_decisions.to_answer_dict()
        # combine answers and not answered decision
        for dec in doubled_decisions:
            final_usages[dec.related] = answers[dec.key]
        for dec in unique_decisions:
            final_usages[dec.related] = dec.value
        # set usages
        return final_usages

    # def one_zone_usage(self, thermal_zones: dict):
    #     """defines an usage to all the building - since its a singular zone"""
    #     usage_decision = ListDecision("Which usage does the one_zone_building"
    #                                   " %s have?",
    #                                   choices=list(UseConditions.keys()),
    #                                   global_key="one_zone_usage",
    #                                   allow_skip=False,
    #                                   allow_load=True,
    #                                   allow_save=True,
    #                                   quick_decide=not True)
    #     usage_decision.decide()
    #     for tz in list(thermal_zones.values()):
    #         tz.usage = usage_decision.value
    #         self.enriched_tz.append(tz)

    def load_usage(self, tz: ThermalZone):
        """loads the usage of the corresponding ThermalZone.

        Loads the usage from the statistical data in assets/enrichment/usage.

        Args:
            tz: bim2sim ThermalZone element
        """
        use_condition = self.use_conditions[tz.usage]
        for attr, value in use_condition.items():
            # avoid to overwrite attrs present on the element
            if getattr(tz, attr) is None:
                value = self.value_processing(value)
                setattr(tz, attr, value)

    @staticmethod
    def value_processing(value: float):
        """"""
        if isinstance(value, dict):
            values = next(iter(value.values()))
            return values[0]/values[1]
        else:
            return value
