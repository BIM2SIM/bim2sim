"""Module for disaggregation"""

import math
import numpy as np

from bim2sim.kernel import attribute
from bim2sim.kernel.element import BaseElement
from bim2sim.task.bps_f.bps_functions import get_boundaries


class Disaggregation(BaseElement):
    """Base disaggregation of models"""
    vertical_instances = ['Wall', 'InnerWall', 'OuterWall']
    horizontal_instances = ['Roof', 'Floor', 'GroundFloor']

    def __init__(self, name, element, *args, **kwargs):
        if 'guid' not in kwargs:
            kwargs['guid'] = self.get_id("Disagg")
        super().__init__(*args, **kwargs)
        self.name = name
        self.parent = element
        self.ifc_type = element.ifc_type
        self.guid = None

    # @classmethod
    # def get_empty_mapping(cls, elements: list):
    #     """Get information to remove elements
    #     :returns tuple of
    #         mapping dict with original ports as values and None as keys
    #         connection list of outer connections"""
    #     ports = [port for element in elements for port in element.ports]
    #     mapping = {port: None for port in ports}
    #     # TODO: len > 1, optimize
    #     external_ports = []
    #     for port in ports:
    #         if port.connection and port.connection.parent not in elements:
    #             external_ports.append(port.connection)
    #
    #     mapping[external_ports[0].connection] = external_ports[1]
    #     mapping[external_ports[1].connection] = external_ports[0]
    #     connections = []  # (external_ports[0], external_ports[1])
    #
    #     return mapping, connections

    def calc_position(self):
        try:
            thermalzone = self.thermal_zones[0]
        except:
            return None
        if self.parent.__class__.__name__ in self.horizontal_instances:
            pos = thermalzone.position
        elif self.parent.__class__.__name__ in self.vertical_instances:
            thermalzone = self.thermal_zones[0]
            x1, y1, z1 = thermalzone.position

            space_selected, space_not_selected = get_dimensions_subwall(self, thermalzone)

            rel_orientation = self.orientation + self.parent.get_true_north()
            x = x1 + math.sin(math.radians(rel_orientation)) * space_not_selected / 2
            y = y1 + math.cos(math.radians(rel_orientation)) * space_not_selected / 2
            pos = np.array([x, y, z1])
        else:
            return None
        return pos

    def calc_orientation(self):
        try:
            return self.parent.orientation
        except:
            return None

    @classmethod
    def based_on_thermal_zone(cls, name, parent, thermal_zone):
        instance = cls(name, parent)
        if parent.__class__.__name__ in cls.horizontal_instances:
            if not hasattr(instance, 'area'):
                return parent
            if instance.area > thermal_zone.area:
                instance.area = float(thermal_zone.area)
            else:
                # return the original instance, no new instance created
                return parent

        elif parent.__class__.__name__ in cls.vertical_instances:
            if get_boundaries(parent.ifc) is None:
                return parent
            if get_dimensions_subwall(instance, thermal_zone) is None:
                return parent

            instance_length, instance_width = get_boundaries(parent.ifc)
            space_selected, space_not_selected = get_dimensions_subwall(instance, thermal_zone)

            if instance_length > space_selected + 2 * instance_width:
                instance.length = space_selected
            # return the original instance, no new instance created
            else:
                return parent

        else:
            return parent

        if not hasattr(parent, "sub_instances"):
            parent.sub_instances = []
        parent.sub_instances.append(instance)
        return instance

    def __repr__(self):
        return "<%s '%s' (disaggregation of the element %d)>" % (
            self.__class__.__name__, self.name, len(self.parent))


class SubFloor(Disaggregation):
    disaggregatable_elements = ['IfcSlab']

    @attribute.multi_calc
    def _get_properties(self):
        result = dict(
            area=self.parent.area,
            thickness=self.parent.thickness,
            thermal_transmittance=self.parent.thermal_transmittance,
            is_external=self.parent.is_external
        )
        return result

    area = attribute.Attribute(
        name='area',
        functions=[_get_properties]
    )

    thickness = attribute.Attribute(
        name='thickness',
        functions=[_get_properties]
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_get_properties]
    )

    is_external = attribute.Attribute(
        name='is_external',
        functions=[_get_properties]
    )


class SubGroundFloor(Disaggregation):
    disaggregatable_elements = ['IfcSlab']

    @attribute.multi_calc
    def _get_properties(self):
        result = dict(
            area=self.parent.area,
            thickness=self.parent.thickness,
            thermal_transmittance=self.parent.thermal_transmittance,
            is_external=self.parent.is_external
        )
        return result

    area = attribute.Attribute(
        name='area',
        functions=[_get_properties]
    )

    thickness = attribute.Attribute(
        name='thickness',
        functions=[_get_properties]
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_get_properties]
    )

    is_external = attribute.Attribute(
        name='is_external',
        functions=[_get_properties]
    )


class SubSlab(Disaggregation):
    disaggregatable_elements = ['IfcSlab']

    @attribute.multi_calc
    def _get_properties(self):
        result = dict(
            area=self.parent.area,
            thickness=self.parent.thickness,
            thermal_transmittance=self.parent.thermal_transmittance,
            is_external=self.parent.is_external
        )
        return result

    area = attribute.Attribute(
        name='area',
        functions=[_get_properties]
    )

    thickness = attribute.Attribute(
        name='thickness',
        functions=[_get_properties]
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_get_properties]
    )

    is_external = attribute.Attribute(
        name='is_external',
        functions=[_get_properties]
    )


class SubRoof(Disaggregation):
    disaggregatable_elements = ['IfcRoof', 'IfcSlab']

    @attribute.multi_calc
    def _get_properties(self):
        result = dict(
            area=self.parent.area,
            thickness=self.parent.thickness,
            thermal_transmittance=self.parent.thermal_transmittance,
            is_external=self.parent.is_external
        )
        return result

    area = attribute.Attribute(
        name='area',
        functions=[_get_properties]
    )

    thickness = attribute.Attribute(
        name='thickness',
        functions=[_get_properties]
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_get_properties]
    )

    is_external = attribute.Attribute(
        name='is_external',
        functions=[_get_properties]
    )



class SubWall(Disaggregation):
    disaggregatable_elements = ['IfcWall']


    @attribute.multi_calc
    def _get_properties(self):
        result = dict(
            area=self.parent.area,
            is_external=self.parent.is_external,
            thermal_transmittance=self.parent.thermal_transmittance,
            material=self.parent.material,
            thickness=self.parent.thickness,
            heat_capacity=self.parent.heat_capacity,
            density=self.parent.density

        )
        return result

    area = attribute.Attribute(
        name='area',
        functions=[_get_properties]
    )

    is_external = attribute.Attribute(
        name='is_external',
        functions=[_get_properties]
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_get_properties]
    )

    material = attribute.Attribute(
        name='material',
        functions=[_get_properties]
    )

    thickness = attribute.Attribute(
        name='thickness',
        functions=[_get_properties]
    )

    heat_capacity = attribute.Attribute(
        name='heat_capacity',
        functions=[_get_properties]
    )

    density = attribute.Attribute(
        name='density',
        functions=[_get_properties]
    )

    tilt = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_get_properties]
    )



class SubInnerWall(Disaggregation):
    disaggregatable_elements = ['IfcWall']


    @attribute.multi_calc
    def _get_properties(self):
        result = dict(
            area=self.parent.area,
            is_external=self.parent.is_external,
            thermal_transmittance=self.parent.thermal_transmittance,
            material=self.parent.material,
            thickness=self.parent.thickness,
            heat_capacity=self.parent.heat_capacity,
            density=self.parent.density

        )
        return result

    area = attribute.Attribute(
        name='area',
        functions=[_get_properties]
    )

    is_external = attribute.Attribute(
        name='is_external',
        functions=[_get_properties]
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_get_properties]
    )

    material = attribute.Attribute(
        name='material',
        functions=[_get_properties]
    )

    thickness = attribute.Attribute(
        name='thickness',
        functions=[_get_properties]
    )

    heat_capacity = attribute.Attribute(
        name='heat_capacity',
        functions=[_get_properties]
    )

    density = attribute.Attribute(
        name='density',
        functions=[_get_properties]
    )

    tilt = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_get_properties]
    )

class SubOuterWall(Disaggregation):
    disaggregatable_elements = ['IfcWall']


    @attribute.multi_calc
    def _get_properties(self):
        result = dict(
            area=self.parent.area,
            is_external=self.parent.is_external,
            thermal_transmittance=self.parent.thermal_transmittance,
            material=self.parent.material,
            thickness=self.parent.thickness,
            heat_capacity=self.parent.heat_capacity,
            density=self.parent.density

        )
        return result

    area = attribute.Attribute(
        name='area',
        functions=[_get_properties]
    )

    is_external = attribute.Attribute(
        name='is_external',
        functions=[_get_properties]
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_get_properties]
    )

    material = attribute.Attribute(
        name='material',
        functions=[_get_properties]
    )

    thickness = attribute.Attribute(
        name='thickness',
        functions=[_get_properties]
    )

    heat_capacity = attribute.Attribute(
        name='heat_capacity',
        functions=[_get_properties]
    )

    density = attribute.Attribute(
        name='density',
        functions=[_get_properties]
    )

    tilt = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_get_properties]
    )


# change name
def get_dimensions_subwall(subwall, thermal_zone):
    space_length, space_width, space_selected, space_not_selected = 0, 0, 0, 0

    # geometrical space dimensions not given
    if get_boundaries(thermal_zone.ifc) is None:
        return None

    rel_orientation_space = math.floor(thermal_zone.orientation + thermal_zone.get_true_north())
    if 315 <= rel_orientation_space <= 360 or 0 <= rel_orientation_space < 45 or 135 <= rel_orientation_space < 225:
        space_length, space_width = get_boundaries(thermal_zone.ifc)
    elif 45 <= rel_orientation_space < 135 or 225 <= rel_orientation_space < 315:
        space_width, space_length = get_boundaries(thermal_zone.ifc)
    else:
        print(thermal_zone.name)

    # check if the wall length  corresponds to space length or width
    wall = subwall.parent
    rel_orientation_wall = math.floor(wall.orientation + wall.get_true_north())
    if 315 <= rel_orientation_wall <= 360 or 0 <= rel_orientation_wall < 45 or 135 <= rel_orientation_wall < 225:
        space_selected = space_length
        space_not_selected = space_width
    elif 45 <= rel_orientation_wall < 135 or 225 <= rel_orientation_wall < 315:
        space_selected = space_width
        space_not_selected = space_length
    else:
        print(wall.name)

    return space_selected, space_not_selected


