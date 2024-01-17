import inspect
import math

import numpy as np

from functools import cached_property
from bim2sim.elements.mapping import attribute
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import LOD


class DisaggregationCreation(ITask):
    """Disaggregates building elements based on their space boundaries.

    This task is needed to allow the later combination for thermal zones. If two
    thermal zones are combined to one, we might need to cut/disaggregate
    elements like walls into pieces that belong to the different zones.
    """

    reads = ('elements',)
    touches = ('disaggregations',)

    def __init__(self, playground):
        super().__init__(playground)
        self.disaggregations = {}
        self.vertical_elements = ['Wall', 'InnerWall', 'OuterWall']
        self.horizontal_elements = ['Roof', 'Floor', 'GroundFloor']
        self.attributes_dict = {}

    def run(self, elements):
        thermal_zones = filter_elements(elements, 'ThermalZone')
        # Disaggregations not necessary for buildings with one zone
        if self.playground.sim_settings.zoning_setup is not LOD.low:
            for tz in thermal_zones:
                new_bound_elements = self.get_thermal_zone_disaggregations(
                    tz)
                tz.bound_elements = new_bound_elements
            self.logger.info("disaggregated %d elements",
                             len(self.disaggregations))

        return self.disaggregations,

    def get_thermal_zone_disaggregations(self, tz):
        tz_disaggregations = []
        for sb in tz.space_boundaries:
            bound_element = sb.bound_element
            if bound_element is not None:
                if sb.guid in self.disaggregations:
                    inst = self.disaggregations[sb.guid]
                else:
                    if len(bound_element.thermal_zones) == 1:
                        inst = bound_element
                        for sb_ins in bound_element.space_boundaries:
                            self.disaggregations[sb_ins.guid] = inst
                    else:
                        if not sb.net_bound_area:
                            inst = None
                            self.disaggregations[sb.guid] = inst
                        else:
                            inst = self.create_disaggregation(
                                bound_element, sb, tz)
                            self.disaggregations[sb.guid] = inst
                            if sb.related_bound is not None:
                                self.disaggregations[sb.related_bound.guid] = \
                                    inst
                if inst:
                    if inst not in tz_disaggregations:
                        tz_disaggregations.append(inst)
                    if sb not in inst.space_boundaries:
                        inst.space_boundaries.append(sb)
                    if tz not in inst.thermal_zones:
                        inst.thermal_zones.append(tz)

        return tz_disaggregations

    def create_disaggregation(self, bound_element, sb, tz):
        """# todo write documentation"""
        sub_class = type(bound_element)
        if self.check_disaggregation(bound_element, sb):
            inst = sub_class(finder=bound_element.finder)
            self.overwrite_attributes(inst, bound_element, sb, tz, sub_class)
        else:
            inst = bound_element
        return inst

    @staticmethod
    def check_disaggregation(parent, sb, threshold=0.1):
        """# todo write documentation"""
        if len(parent.space_boundaries) == 1:
            return False
        elif sb.bound_area <= 0 or sb.net_bound_area <= 0:
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
        if type_parent not in self.attributes_dict:
            attributes = inspect.getmembers(
                type(parent), lambda a: (type(a) in [attribute.Attribute,
                                                     cached_property]))
            self.attributes_dict[type_parent] = [attr[0] for attr in attributes]

        inst.space_boundaries.append(sb)
        inst.thermal_zones.append(tz)
        inst.net_area = sb.net_bound_area
        inst.gross_area = sb.bound_area
        inst.orientation = parent.orientation
        inst.layerset = parent.layerset
        new_pos = np.array(sb.position)
        if type_parent in self.vertical_elements:
            inst.position = self.get_new_position_vertical_element(parent,
                                                                   new_pos)
        if type_parent in self.horizontal_elements:
            inst.position = tz.position
            if tz.net_area and abs(1 - inst.net_area / tz.net_area) < threshold:
                inst.net_area = tz.net_area
        blacklist = ['position', 'net_area', 'gross_area', 'opening_area']
        for prop in self.attributes_dict[type_parent]:
            if prop not in blacklist:
                dis_value = getattr(inst, prop)
                if dis_value is None or dis_value == []:
                    parent_value = getattr(inst.parent, prop)
                    if parent_value:
                        setattr(inst, prop, parent_value)

    @staticmethod
    def get_new_position_vertical_element(parent, sub_position):
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
