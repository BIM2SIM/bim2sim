import math
import numpy as np

from bim2sim.task.base import ITask
from bim2sim.workflow import LOD
from bim2sim.utilities.common_functions import filter_instances


class DisaggregationCreation(ITask):
    """Prepares bim2sim instances to later export"""
    # for 1Zone Building - workflow.spaces: LOD.low - Disaggregations
    # not necessary
    reads = ('instances', 'finder')
    touches = ('disaggregations',)

    def __init__(self):
        super().__init__()
        self.disaggregations = {}
        self.vertical_instances = ['Wall', 'InnerWall', 'OuterWall']
        self.horizontal_instances = ['Roof', 'Floor', 'GroundFloor']

    def run(self, workflow, finder, instances):
        thermal_zones = filter_instances(instances, 'ThermalZone')
        if workflow.spaces is not LOD.low:
            for tz in thermal_zones:
                new_bound_elements = self.get_thermal_zone_disaggregations(
                    tz, finder)
                tz.bound_elements = new_bound_elements
            self.logger.info("disaggregated %d instances",
                             len(self.disaggregations))

        return self.disaggregations,

    def get_thermal_zone_disaggregations(self, tz, finder):
        tz_disaggregations = []
        for sb in tz.space_boundaries:
            bound_instance = sb.bound_instance
            if bound_instance is not None:
                if sb.related_bound is not None:
                    if sb.guid in self.disaggregations:
                        inst = self.disaggregations[sb.guid]
                    else:
                        inst = self.create_disaggregation(
                            finder, bound_instance, sb, tz)
                        self.disaggregations[sb.related_bound.guid] = inst
                else:
                    inst = self.create_disaggregation(
                        finder, bound_instance, sb, tz)
                tz_disaggregations.append(inst)

                if sb not in inst.space_boundaries:
                    inst.space_boundaries.append(sb)
                if tz not in inst.thermal_zones:
                    inst.thermal_zones.append(tz)
        return tz_disaggregations

    def create_disaggregation(self, finder, bound_instance, sb, tz):
        """# todo write documentation"""
        sub_class = type(bound_instance)
        if self.check_disaggregation(bound_instance, sb):
            inst = sub_class(finder=finder)
            self.overwrite_attributes(inst, bound_instance, sb, tz, sub_class)
        else:
            inst = bound_instance
        return inst

    @staticmethod
    def check_disaggregation(parent, sb, threshold=0.1):
        """# todo write documentation"""
        if len(parent.space_boundaries) == 1:
            return False
        elif sb.bound_area == 0:
            return False
        elif abs(parent.gross_area - sb.bound_area) / sb.bound_area < threshold:
            return False
        else:
            return True

    def overwrite_attributes(self, inst, parent, sb, tz, subclass,
                             threshold=0.1):
        """# todo write documentation"""
        type_parent = subclass.__name__

        inst.parent = parent
        inst.space_boundaries.append(sb)
        inst.thermal_zones.append(tz)
        inst.net_area = sb.net_bound_area
        inst.gross_area = sb.bound_area
        inst.orientation = parent.orientation
        for prop in inst.attributes:
            dis_value = getattr(inst, prop)
            if not dis_value:
                parent_value = getattr(inst.parent, prop)
                if parent_value:
                    setattr(inst, prop, parent_value)

        new_pos = np.array(sb.position)
        if type_parent in self.vertical_instances:
            inst.position = self.get_new_position_vertical_instance(parent,
                                                                    new_pos)
        if type_parent in self.horizontal_instances:
            inst.position = tz.position
            if tz.net_area and abs(1 - inst.net_area / tz.net_area) < threshold:
                inst.net_area = tz.net_area

    @staticmethod
    def get_new_position_vertical_instance(parent, sub_position):
        """get new position based on parent position, orientation and relative
        disaggregation position"""
        rel_orientation_wall = math.floor(parent.orientation)
        x1, y1, z1 = sub_position
        x, y, z = parent.position
        if 45 <= rel_orientation_wall < 135 or 225 <= rel_orientation_wall \
                < 315:
            y1, z1, z1 = sub_position

        x = x - x1 * math.cos(math.radians(rel_orientation_wall))
        y = y - y1 * math.sin(math.radians(rel_orientation_wall))

        position = np.array([x, y, z])

        return position
