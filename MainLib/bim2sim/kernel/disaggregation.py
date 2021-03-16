"""Module for disaggregation"""

import math
import numpy as np
import pint
import re

from bim2sim.kernel.element import BaseElement, SubElement


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
        space_boundaries = []

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
    def get_supported_classes(cls):
        supported_classes = {subclass.disaggregatable_elements: subclass for subclass in cls.__subclasses__()}
        return supported_classes

    @classmethod
    def based_on_thermal_zone(cls, parent, space_boundary, thermal_zone):
        """creates a disaggregation based on a thermal zone and an instance parent
        based on area slice (thermal zone - area)"""
        supported_classes = cls.get_supported_classes()
        type_parent = type(parent).__name__
        disaggregation_class = supported_classes.get(type_parent)

        if disaggregation_class is None:
            return parent

        name = 'Sub' + disaggregation_class.disaggregatable_elements + '_' + parent.name
        if not hasattr(parent, "sub_instances"):
            parent.sub_instances = []

        i = len(parent.sub_instances)
        new_pos = np.array(space_boundary.position)
        area_disaggregation = space_boundary.bound_area
        if hasattr(parent, 'gross_side_area'):
            parent_area = parent.gross_side_area
        else:
            parent_area = parent.area

        if abs(parent_area - area_disaggregation) < 0.1 or area_disaggregation == 0 or len(parent.space_boundaries) == 1:
            return parent

        else:
            instance = disaggregation_class(name + '_%d' % i, parent)
            instance.area = area_disaggregation

            # position calc
            if type_parent in vertical_instances:
                instance._pos = get_new_position_vertical_instance(parent, new_pos)
            if type_parent in horizontal_instances:
                instance._pos = thermal_zone.position
                if thermal_zone.area > instance.area:
                    if abs(1-instance.area/thermal_zone.area) < 0.1:
                        instance.area = thermal_zone.area

            parent.sub_instances.append(instance)
            return instance

    def __repr__(self):
        return "<%s '%s' (disaggregation of the element %d)>" % (
            self.__class__.__name__, self.name, len(self.parent))

    def __str__(self):
        return "%s" % self.__class__.__name__


class SubFloor(Disaggregation):
    disaggregatable_elements = 'Floor'


class SubGroundFloor(Disaggregation):
    disaggregatable_elements = 'GroundFloor'


class SubSlab(Disaggregation):
    disaggregatable_elements = 'Slab'


class SubRoof(Disaggregation):
    disaggregatable_elements = 'Roof'


class SubWall(Disaggregation):
    disaggregatable_elements = 'Wall'


class SubInnerWall(Disaggregation):
    disaggregatable_elements = 'InnerWall'


class SubOuterWall(Disaggregation):
    disaggregatable_elements = 'OuterWall'


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
