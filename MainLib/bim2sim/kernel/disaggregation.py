"""Module for disaggregation"""

import math
import numpy as np

from bim2sim.kernel.element import BaseSubElement
from bim2sim.task.bps_f.bps_functions import get_disaggregations_instance

vertical_instances = ['Wall', 'InnerWall', 'OuterWall']
horizontal_instances = ['Roof', 'Floor', 'GroundFloor']


class Disaggregation(BaseSubElement):
    """Base disaggregation of models"""

    def __init__(self, name, element, *args, **kwargs):
        if 'guid' not in kwargs:
            kwargs['guid'] = self.get_id("Disagg")
        super().__init__(*args, **kwargs)
        self.parent = element
        self.name = name
        self.ifc_type = element.ifc_type
        self.guid = None
        # properties getter
        for prop in self.parent.attributes:
            value = getattr(self.parent, prop)
            setattr(self, prop, value)
        switcher = {'SubFloor': SubFloor,
                    'SubGroundFloor': SubGroundFloor,
                    'SubSlab': SubSlab,
                    'SubRoof': SubRoof,
                    'SubWall': SubWall,
                    'SubInnerWall': SubInnerWall,
                    'SubOuterWall': SubOuterWall}
        sub_module = 'Sub' + self.parent.__class__.__name__
        func = switcher.get(sub_module)
        if func is not None:
            self.__class__ = func
            self.__init__(self.name, self.parent)

    def calc_position(self):
        try:
            return self._pos
        except:
            return None

    def calc_orientation(self):
        try:
            return self.parent.orientation
        except:
            return None

    @classmethod
    def based_on_thermal_zone(cls, parent, thermal_zone):
        """creates a disaggregation based on a thermal zone and an instance parent
        based on area cutting (thermal zone - area)"""
        new_bound_instances = []
        disaggregations = get_disaggregations_instance(parent, thermal_zone)

        # no disaggregation possible
        if disaggregations is None:
            return [parent]

        # for vertical instances: if just one disaggregation is possible, check if disaggregation is parent
        # disaggregation is parent if has the same area
        if parent.__class__.__name__ in vertical_instances:
            if len(disaggregations) == 1:
                disaggregation_area = disaggregations[next(iter(disaggregations))][0]
                # here was a tolerance of 0.1 necessary in order to get no false positives
                if abs(disaggregation_area - parent.area) <= 0.1:
                    return [parent]

        name = 'Sub' + parent.__class__.__name__ + '_' + parent.name
        if not hasattr(parent, "sub_instances"):
            parent.sub_instances = []

        i = len(parent.sub_instances)
        for ins in disaggregations:

            scontinue = False
            for dis in parent.sub_instances:
                #  check if disaggregation exists on subinstances, compares disaggregation and existing sub_instances
                # here was a tolerance of 0.1 necessary in order to get no false positives
                if abs(disaggregations[ins][0] - dis.area) <= 0.1:
                    new_bound_instances.append(dis)
                    scontinue = True
                    break
            if scontinue:
                continue

            # create instance
            instance = cls(name + '_%d' % i, parent)
            instance.area = disaggregations[ins][0]

            # position calc
            if parent.__class__.__name__ in vertical_instances:
                instance._pos = get_new_position_vertical_instance(parent, disaggregations[ins][1])
            if parent.__class__.__name__ in horizontal_instances:
                instance._pos = thermal_zone.position

            parent.sub_instances.append(instance)
            new_bound_instances.append(instance)

            if thermal_zone not in parent.thermal_zones:
                parent.thermal_zones.append(thermal_zone)

            i += 1

        return new_bound_instances

    def __repr__(self):
        return "<%s '%s' (disaggregation of the element %d)>" % (
            self.__class__.__name__, self.name, len(self.parent))


class SubFloor(Disaggregation):
    disaggregatable_elements = ['IfcSlab']

    def __init__(self, *args, **kwargs):
        pass


class SubGroundFloor(Disaggregation):
    disaggregatable_elements = ['IfcSlab']

    def __init__(self, *args, **kwargs):
        pass


class SubSlab(Disaggregation):
    disaggregatable_elements = ['IfcSlab']

    def __init__(self, *args, **kwargs):
        pass

class SubRoof(Disaggregation):
    disaggregatable_elements = ['IfcRoof', 'IfcSlab']

    def __init__(self, *args, **kwargs):
        pass


class SubWall(Disaggregation):
    disaggregatable_elements = ['IfcWall']

    def __init__(self, *args, **kwargs):
        pass


class SubInnerWall(Disaggregation):
    disaggregatable_elements = ['IfcWall']

    def __init__(self, *args, **kwargs):
        pass


class SubOuterWall(Disaggregation):
    disaggregatable_elements = ['IfcWall']

    def __init__(self, *args, **kwargs):
        pass


def get_new_position_vertical_instance(parent, sub_position):
    """get new position based on parent position, orientation and relative disaggregation position"""
    rel_orientation_wall = math.floor(parent.orientation + parent.get_true_north())
    x1, y1, z1 = sub_position
    x, y, z = parent.position
    if 45 <= rel_orientation_wall < 135 or 225 <= rel_orientation_wall < 315:
        y1, z1, z1 = sub_position

    x = x - x1 * math.cos(math.radians(rel_orientation_wall))
    y = y - y1 * math.sin(math.radians(rel_orientation_wall))

    position = np.array([x, y, z])

    return position
