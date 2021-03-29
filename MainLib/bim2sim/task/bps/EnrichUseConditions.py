import translators as ts

from bim2sim.task.base import Task, ITask
from bim2sim.workflow import LOD
from bim2sim.task.common.common_functions import get_usage_list, get_pattern_usage
from bim2sim.project import PROJECT
from bim2sim.decision import ListDecision


class EnrichUseConditions(ITask):
    """Prepares bim2sim instances to later export"""

    reads = ('tz_instances',)
    touches = ('enriched_tz',)

    def __init__(self):
        super().__init__()
        self.enriched_tz = []

    @Task.log
    def run(self, workflow, tz_instances):
        self.logger.info("enriches thermal zones usage")
        if len(tz_instances) == 0:
            self.logger.warning("Found no spaces to bind")
        else:
            if workflow.spaces is LOD.low:
                self.one_zone_usage(list(tz_instances.values()))
            else:
                self.multi_zone_usage(list(tz_instances.values()))
            self.logger.info("obtained %d thermal zones", len(self.enriched_tz))

        return self.enriched_tz,

    def multi_zone_usage(self, thermal_zones):
        pattern_usage = get_pattern_usage()
        for tz in thermal_zones:
            if tz.usage is None:
                matches = []
                if tz.zone_name:
                    list_org = tz.zone_name.replace(' (', ' ').replace(')', ' ').replace(' -', ' ').replace(', ', ' ').split()
                    for usage, patterns in pattern_usage.items(): # optimize this
                        for i in patterns:
                            for i_name in list_org:
                                if i.match(i_name):
                                    if usage not in matches:
                                        matches.append(usage)
                # if just a match given
                if len(matches) == 1:
                    if 'office_function' == matches[0]:
                        tz.usage = self.office_usage(tz)
                    else:
                        tz.usage = matches[0]
                    self.enriched_tz.append(tz)
                    continue
                # if no matches given
                elif len(matches) == 0:
                    matches = list(pattern_usage.keys())
                tz.usage = self.list_decision_usage(tz, matches)
                self.enriched_tz.append(tz)

    def one_zone_usage(self, thermal_zones):
        usage_decision = ListDecision("Which usage does the one_zone_building %s have?",
                                      choices=get_usage_list(),
                                      global_key="one_zone_usage",
                                      allow_skip=False,
                                      allow_load=True,
                                      allow_save=True,
                                      quick_decide=not True)
        usage_decision.decide()
        for tz in thermal_zones:
            tz.usage = usage_decision.value
            self.enriched_tz.append(tz)

    def office_usage(self, tz):
        """function to determine which office corresponds based
        https://skepp.com/en/blog/office-tips/this-is-how-many-square-meters-of-office-space-you-need-per-person
        table"""
        default_matches = ["Single office", "Group Office (between 2 and 6 employees)",
                           "Open-plan Office (7 or more employees)"]
        area = tz.area.m
        if area is not None:
            if area <= 7:
                return default_matches[0]
            elif 7 < area <= 42:
                return default_matches[1]
            else:
                return default_matches[2]
        else:
            self.list_decision_usage(tz, default_matches)

    @staticmethod
    def list_decision_usage(tz, matches):
        usage_decision = ListDecision("Which usage does the Space %s have?" %
                                      (str(tz.zone_name)),
                                      choices=matches,
                                      global_key="%s_%s.BpsUsage" % (type(tz).__name__, tz.guid),
                                      allow_skip=False,
                                      allow_load=True,
                                      allow_save=True,
                                      quick_decide=not True)
        usage_decision.decide()
        return usage_decision.value
