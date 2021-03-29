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
        zone_dict = {
            "Schlafzimmer": "Bed room",
            "Wohnen": "Living",
            "Galerie": "Living",
            "Küche": "Living",
            "Flur": "Traffic area",
            "Buero": "Single office",
            "Besprechungsraum": 'Meeting, Conference, seminar',
            "Seminarraum": 'Meeting, Conference, seminar',
            "Technikraum": "Stock, technical equipment, archives",
            "Dachboden": "Traffic area",
            "WC": "WC and sanitary rooms in non-residential buildings",
            "Bad": "WC and sanitary rooms in non-residential buildings",
            "Labor": "Laboratory"
        }
        for tz in thermal_zones:
            if PROJECT.PAPER:
                # hardcode for investigation of KIT Institut
                for key, trans in zone_dict.items():
                    if key in tz.zone_name:
                        return trans
            zone_pattern = []
            matches = []

            if tz.zone_name:
                list_org = tz.zone_name.replace(' (', ' ').replace(')', ' ').replace(' -', ' ').replace(', ', ' ').split()
                for i_org in list_org:
                    trans_aux = ts.bing(i_org, from_language='de')
                    # trans_aux = ts.google(i_org, from_language='de')
                    zone_pattern.append(trans_aux)

                # check if a string matches the zone name
                for usage, pattern in pattern_usage.items():
                    for i in pattern:
                        for i_name in zone_pattern:
                            if i.match(i_name):
                                if usage not in matches:
                                    matches.append(usage)
            # if just a match given
            if len(matches) == 1:
                return matches[0]
            # if no matches given
            elif len(matches) == 0:
                matches = list(pattern_usage.keys())
            usage_decision = ListDecision("Which usage does the Space %s have?" %
                                          (str(tz.zone_name)),
                                          choices=matches,
                                          global_key="%s_%s.BpsUsage" % (type(tz).__name__, tz.guid),
                                          allow_skip=False,
                                          allow_load=True,
                                          allow_save=True,
                                          quick_decide=not True)
            usage_decision.decide()
            tz.usage = usage_decision.value
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
