from bim2sim.task.base import Task, ITask
from bim2sim.kernel.element import SubElement
from bim2sim.kernel.disaggregation import Disaggregation


class Disaggregation_creation(ITask):
    """Prepares bim2sim instances to later export"""
    reads = ('instances',)
    touches = ('instances',)

    disaggregations = {}

    @Task.log
    def run(self, workflow, instances):
        thermal_zones = SubElement.get_class_instances('ThermalZone')
        for tz in thermal_zones:
            tz_disaggregations = self.get_thermal_zone_disaggregations(tz)
            tz.bound_elements = tz_disaggregations
            self.set_tz_properties(tz)

        return instances,

    @classmethod
    def get_thermal_zone_disaggregations(cls, tz):
        tz_disaggregations = []
        for sb in tz.space_boundaries:
            bound_instance = sb.bound_instance
            if sb.related_bound is not None:
                if sb.guid in cls.disaggregations:
                    inst = cls.disaggregations[sb.guid]
                else:
                    inst = Disaggregation.based_on_thermal_zone(bound_instance, sb, tz)
                    cls.disaggregations[sb.related_bound.guid] = inst
            else:
                inst = Disaggregation.based_on_thermal_zone(bound_instance, sb, tz)
            tz_disaggregations.append(inst)
            if sb not in inst.space_boundaries:
                inst.space_boundaries.append(sb)
            if tz not in inst.thermal_zones:
                inst.thermal_zones.append(tz)
        return tz_disaggregations

    @classmethod
    def set_tz_properties(cls, tz):
        tz.set_space_neighbors()
        tz.set_is_external()
        tz.set_external_orientation()
        tz.set_glass_area()


