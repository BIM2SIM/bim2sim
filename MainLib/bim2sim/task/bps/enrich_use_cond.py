from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import get_usage_dict, get_pattern_usage
from bim2sim.decision import ListDecision, DecisionBunch
from bim2sim.workflow import Workflow
from bim2sim.kernel.elements.bps import ThermalZone

UseConditions = get_usage_dict()


class EnrichUseConditions(ITask):
    """Enriches Use Conditions of thermal zones
    based on decisions and translation of zone names"""

    reads = ('tz_instances',)
    touches = ('enriched_tz',)

    def __init__(self):
        super().__init__()
        self.enriched_tz = []

    def run(self, workflow: Workflow, tz_instances: dict):
        self.logger.info("enriches thermal zones usage")
        # case no thermal zones found
        if len(tz_instances) == 0:
            self.logger.warning("Found no spaces to enrich")
        else:
            yield from self.multi_zone_usage(tz_instances)
            self.logger.info("obtained %d thermal zones", len(self.enriched_tz))

        return self.enriched_tz,

    def multi_zone_usage(self, thermal_zones: dict):
        """defines an usage to a determined thermal zone"""
        selected_usage = {}
        pattern_usage = get_pattern_usage()
        for tz in list(thermal_zones.values()):
            if tz.usage in selected_usage:
                tz.usage = selected_usage[tz.usage]
            else:
                previous_usage = str(tz.usage)
                if previous_usage not in pattern_usage:
                    matches = []
                    list_org = tz.usage.replace(' (', ' ').replace(')', ' '). \
                        replace(' -', ' ').replace(', ', ' ').split()
                    for usage, patterns in pattern_usage.items():
                        for i in patterns:
                            for i_name in list_org:
                                if i.match(i_name):
                                    if usage not in matches:
                                        matches.append(usage)
                    # if just a match given
                    if len(matches) == 1:
                        # case its an office
                        if 'office_function' == matches[0]:
                            tz.usage = yield from self.office_usage(tz)
                        # other zone usage
                        else:
                            tz.usage = matches[0]
                    # if no matches given
                    elif len(matches) == 0:
                        matches = list(pattern_usage.keys())
                    if len(matches) > 1:
                        tz.usage = yield from self.list_decision_usage(
                            tz, matches)
                    selected_usage[previous_usage] = tz.usage
            self.load_usage(tz)
            self.enriched_tz.append(tz)

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

    def office_usage(self, tz: ThermalZone):
        """function to determine which office corresponds based on the area of
        the thermal zone and the table on:
        https://skepp.com/en/blog/office-tips/this-is-how-many-square-meters-of
        -office-space-you-need-per-person"""

        default_matches = ["Single office",
                           "Group Office (between 2 and 6 employees)",
                           "Open-plan Office (7 or more employees)"]
        area = tz.area.m
        # case area its available
        if area is not None:
            if area <= 7:
                return default_matches[0]
            elif 7 < area <= 42:
                return default_matches[1]
            else:
                return default_matches[2]
        # case area not available
        else:
            yield from self.list_decision_usage(tz, default_matches)

    @staticmethod
    def list_decision_usage(tz: ThermalZone, matches: list):
        """decision to select an usage that matches the zone name"""
        usage_decision = ListDecision("Which usage does the Space %s have?" %
                                      (str(tz.usage)),
                                      choices=matches,
                                      global_key="%s_%s.BpsUsage" %
                                                 (type(tz).__name__, tz.guid),
                                      allow_skip=False)
        yield DecisionBunch([usage_decision])
        return usage_decision.value

    def load_usage(self, tz: ThermalZone):
        use_condition = UseConditions[tz.usage]
        for attr, value in use_condition.items():
            # avoid to overwrite attrs present on the instance
            if getattr(tz, attr) is None:
                value = self.value_processing(value)
                setattr(tz, attr, value)

    @staticmethod
    def value_processing(value):
        if isinstance(value, dict):
            values = next(iter(value.values()))
            return values[0]/values[1]
        else:
            return value
