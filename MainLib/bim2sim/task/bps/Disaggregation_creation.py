from bim2sim.task.base import Task, ITask
from bim2sim.kernel.disaggregation import Disaggregation
from bim2sim.workflow import LOD


class Disaggregation_creation(ITask):
    """Prepares bim2sim instances to later export"""
    # for 1Zone Building - workflow.spaces: LOD.low - Disaggregations not necessary
    reads = ('tz_instances',)
    touches = ('disaggregations',)

    def __init__(self):
        super().__init__()
        self.disaggregations = {}
        pass

    @Task.log
    def run(self, workflow, tz_instances):
        if workflow.spaces is not LOD.low:
            for guid, tz in tz_instances.items():
                tz_disaggregations = self.get_thermal_zone_disaggregations(tz)
                tz.bound_elements = tz_disaggregations
                self.set_tz_properties(tz)
            self.logger.info("disaggregated %d instances", len(self.disaggregations))

        return self.disaggregations,

    def get_thermal_zone_disaggregations(self, tz):
        tz_disaggregations = []
        for sb in tz.space_boundaries:
            bound_instance = sb.bound_instance
            if sb.related_bound is not None:
                if sb.guid in self.disaggregations:
                    inst = self.disaggregations[sb.guid]
                else:
                    inst = Disaggregation.based_on_thermal_zone(bound_instance, sb, tz)
                    self.disaggregations[sb.related_bound.guid] = inst
            else:
                inst = Disaggregation.based_on_thermal_zone(bound_instance, sb, tz)
            tz_disaggregations.append(inst)
            if sb not in inst.space_boundaries:
                inst.space_boundaries.append(sb)
            if tz not in inst.thermal_zones:
                inst.thermal_zones.append(tz)
        return tz_disaggregations

    @staticmethod
    def set_tz_properties(tz):
        tz.set_space_neighbors()
        tz.set_is_external()
        tz.set_external_orientation()
        tz.set_glass_area()
