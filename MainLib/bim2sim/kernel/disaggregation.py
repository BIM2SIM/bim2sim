"""Module for disaggregation"""

import math
import numpy as np
import pint
import re

from bim2sim.kernel.element import BaseElement, SubElement
from bim2sim.task.bps_f.bps_functions import get_disaggregations_instance


vertical_instances = ['Wall', 'InnerWall', 'OuterWall']
horizontal_instances = ['Roof', 'Floor', 'GroundFloor']


class Disaggregation(BaseElement):
    """Base disaggregation of models"""

    def __init__(self, name, element, *args, **kwargs):
        if 'guid' not in kwargs:
            kwargs['guid'] = self.get_id("Disagg")
        super().__init__(*args, **kwargs)
        self.parent = element
        self.name = name
        self.ifc_type = element.ifc_type
        self.get_disaggregation_properties()

    def get_disaggregation_properties(self):
        """properties getter -> that way no sub instances has to be defined"""
        for prop in self.parent.attributes:
            value = getattr(self.parent, prop)
            setattr(self, prop, value)

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
    def based_on_thermal_zone(cls, space_boundaries_info, thermal_zone):
        """creates a disaggregation based on a thermal zone and an instance parent
        based on area slice (thermal zone - area)"""
        parent = space_boundaries_info[0]
        space_boundaries = space_boundaries_info[1]

        name = 'Sub' + parent.__class__.__name__ + '_' + parent.name
        if not hasattr(parent, "sub_instances"):
            parent.sub_instances = []

        i = len(parent.sub_instances)
        area_disaggregation = 0
        new_pos = np.array((0, 0, 0))
        for s_boundary in space_boundaries:
            area_disaggregation += s_boundary.area
            new_pos = new_pos + np.array(s_boundary.position)
        new_pos = new_pos / len(space_boundaries)

        if (parent.area - area_disaggregation) < 0.1 or area_disaggregation == 0 or len(parent.space_boundaries) == 1:
            return parent
        else:
            type_parent = type(parent).__name__
            re_search = re.compile('Sub%s' % type_parent)
            instance = cls(name + '_%d' % i, parent)

            # class assignment for subinstances -> based on re and factory
            for sub_cls in SubElement.get_all_subclasses(cls):
                type_search = sub_cls.__name__
                if re_search.match(type_search):
                    instance = sub_cls(name + '_%d' % i, parent)
                    break

            instance.area = area_disaggregation

            # position calc
            if parent.__class__.__name__ in vertical_instances:
                instance._pos = get_new_position_vertical_instance(parent, new_pos)
            if parent.__class__.__name__ in horizontal_instances:
                instance._pos = thermal_zone.position

            parent.sub_instances.append(instance)
            if thermal_zone not in parent.thermal_zones:
                parent.thermal_zones.append(thermal_zone)

            return instance

    def __repr__(self):
        return "<%s '%s' (disaggregation of the element %d)>" % (
            self.__class__.__name__, self.name, len(self.parent))

    def __str__(self):
        return "%s" % self.__class__.__name__


class SubFloor(Disaggregation):
    disaggregatable_elements = ['IfcSlab']


class SubGroundFloor(Disaggregation):
    disaggregatable_elements = ['IfcSlab']


class SubSlab(Disaggregation):
    disaggregatable_elements = ['IfcSlab']


class SubRoof(Disaggregation):
    disaggregatable_elements = ['IfcRoof', 'IfcSlab']


class SubWall(Disaggregation):
    disaggregatable_elements = ['IfcWall']


class SubInnerWall(Disaggregation):
    disaggregatable_elements = ['IfcWall']


class SubOuterWall(Disaggregation):
    disaggregatable_elements = ['IfcWall']


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
