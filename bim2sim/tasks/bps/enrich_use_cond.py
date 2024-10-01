from typing import Union, Dict

from bim2sim.kernel.decision import ListDecision, DecisionBunch
from bim2sim.elements.bps_elements import ThermalZone
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import get_use_conditions_dict, \
    get_pattern_usage, wildcard_match, filter_elements
from bim2sim.utilities.types import AttributeDataSource


class EnrichUseConditions(ITask):
    """Enriches Use Conditions of thermal zones
    based on decisions and translation of zone names"""

    reads = ('elements',)

    def __init__(self, playground):
        super().__init__(playground)
        self.enriched_tz = []
        self.use_conditions = {}

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
            # set heating and cooling based on sim settings configuration
            self.set_heating_cooling(tz_elements, self.playground.sim_settings)
            custom_use_cond_path = self.playground.sim_settings.prj_use_conditions
            custom_usage_path = \
                self.playground.sim_settings.prj_custom_usages

            self.logger.info("enriches thermal zones usage")
            self.use_conditions = get_use_conditions_dict(custom_use_cond_path)
            pattern_usage = get_pattern_usage(self.use_conditions,
                                              custom_usage_path)
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
                self.enriched_tz.append(tz)
                self.logger.info('Enrich ThermalZone from IfcSpace with '
                                 'original usage "%s" with usage "%s"',
                                 orig_usage, usage)
        building_elements = filter_elements(elements, 'Building')
        if self.playground.sim_settings.overwrite_ahu_by_settings:
            for building in building_elements:
                building.ahu_heating = (
                    self.playground.sim_settings.ahu_heating,
                    AttributeDataSource.enrichment)
                building.ahu_cooling = (
                    self.playground.sim_settings.ahu_cooling,
                    AttributeDataSource.enrichment)
                building.ahu_humidification = (
                    self.playground.sim_settings.ahu_humidification,
                    AttributeDataSource.enrichment)
                building.ahu_dehumidification = (
                    self.playground.sim_settings.ahu_dehumidification,
                    AttributeDataSource.enrichment)
                building.ahu_heat_recovery = (
                    self.playground.sim_settings.ahu_heat_recovery,
                    AttributeDataSource.enrichment)
                building.ahu_heat_recovery_efficiency = (
                    self.playground.sim_settings.ahu_heat_recovery_efficiency,
                    AttributeDataSource.enrichment)

    @staticmethod
    def set_heating_cooling(tz_elements:dict , sim_settings):
        """set cooling and heating values based on simulation settings"""

        for tz in tz_elements.values():
            tz.with_cooling = sim_settings.cooling
            tz.with_heating = sim_settings.heating
            if sim_settings.deactivate_ahu:
                tz.with_ahu = False

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
        """Sets the usage of the given thermal_zones and enriches them.

        Looks for fitting usages in assets/enrichment/usage based on the given
        usage of a zone in the IFC. The way the usage is obtained is described
        in the ThermalZone classes attribute "usage".
        The following data is taken into account:
            commonUsages.json: typical translations for the existing usage data
            customUsages<prj_name>.json: project specific translations that can
                be stored for easier simulation.

        Args:
            pattern_usage: Dict with custom and common pattern
            thermal_zones: dict with tz elements guid as key and the element
            itself as value
        Returns:
            final_usages: key: str of usage type, value: ThermalZone element

        """
        # selected_usage = {}
        final_usages = {}
        for tz in list(thermal_zones.values()):
            orig_usage = str(tz.usage)
            if orig_usage in pattern_usage:
                final_usages[tz] = orig_usage
            else:
                matches = []
                list_org = tz.usage.replace(' (', ' ').replace(')', ' '). \
                    replace(' -', ' ').replace(', ', ' ').split()
                for usage in pattern_usage.keys():
                    # check custom first
                    if "custom" in pattern_usage[usage]:
                        for cus_usage in pattern_usage[usage]["custom"]:
                            # if cus_usage == tz.usage:
                            if wildcard_match(cus_usage, tz.usage):
                                if usage not in matches:
                                    matches.append(usage)
                    # if not found in custom, continue with common
                    if len(matches) == 0:
                        for i in pattern_usage[usage]["common"]:
                            for i_name in list_org:
                                if i.match(i_name):
                                    if usage not in matches:
                                        matches.append(usage)
                # if just one match
                if len(matches) == 1:
                    # case its an office
                    if 'office_function' == matches[0]:
                        office_use = cls.office_usage(tz)
                        if isinstance(office_use, list):
                            final_usages[tz] = cls.list_decision_usage(
                                tz, office_use)
                        else:
                            final_usages[tz] = office_use
                    # other zone usage
                    else:
                        final_usages[tz] = matches[0]
                # if no matches given forward all (for decision)
                elif len(matches) == 0:
                    matches = list(pattern_usage.keys())
                if len(matches) > 1:
                    final_usages[tz] = cls.list_decision_usage(
                        tz, matches)
                # selected_usage[orig_usage] = tz.usage
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
    def value_processing(value):
        """"""
        if isinstance(value, dict):
            values = next(iter(value.values()))
            return values[0]/values[1]
        else:
            return value
