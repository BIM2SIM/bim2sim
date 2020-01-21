"""Module contains the different classes for all HVAC elements"""

import math
import re

import numpy as np

from bim2sim.decorators import cached_property
from bim2sim.ifc2python import element, attribute
from bim2sim.decision import BoolDecision
from shapely.geometry.polygon import Polygon
from shapely.geometry import Point
import ifcopenshell.geom
import matplotlib.pyplot as plt
from bim2sim.ifc2python import elements
from bim2sim.ifc2python.element import Element

def diameter_post_processing(value):
    if isinstance(value, list):
        return np.average(value).item()
    return value


class Boiler(element.Element):
    """Boiler"""
    ifc_type = 'IfcBoiler'

    # def _add_ports(self):
    #    super()._add_ports()
    #    for port in self.ports:
    #        if port.flow_direction == 1:
    #            port.flow_master = True
    #        elif port.flow_direction == -1:
    #            port.flow_master = True

    def is_generator(self):
        return True

    def get_inner_connections(self):
        connections = []
        vl_pattern = re.compile('.*vorlauf.*', re.IGNORECASE)  # TODO: extend pattern
        rl_pattern = re.compile('.*rücklauf.*', re.IGNORECASE)
        VL = []
        RL = []
        for port in self.ports:
            if any(filter(vl_pattern.match, port.groups)):
                if port.flow_direction == 1:
                    VL.append(port)
                else:
                    self.logger.warning("Flow direction (%s) of %s does not match %s",
                                        port.verbose_flow_direction, port, port.groups)
                    decision = BoolDecision(
                        "Use %s as VL?" % (port),
                        global_key=port.guid,
                        allow_save=True,
                        allow_load=True)
                    use = decision.decide()
                    if use:
                        VL.append(port)
            elif any(filter(rl_pattern.match, port.groups)):
                if port.flow_direction == -1:
                    RL.append(port)
                else:
                    self.logger.warning("Flow direction (%s) of %s does not match %s",
                                        port.verbose_flow_direction, port, port.groups)
                    decision = BoolDecision(
                        "Use %s as RL?" % (port),
                        global_key=port.guid,
                        allow_save=True,
                        allow_load=True)
                    use = decision.decide()
                    if use:
                        RL.append(port)
        if len(VL) == 1 and len(RL) == 1:
            VL[0].flow_side = 1
            RL[0].flow_side = -1
            connections.append((RL[0], VL[0]))
        else:
            self.logger.warning("Unable to solve inner connections for %s", self)

        return connections

    water_volume = attribute.Attribute(
        name='water_volume',
        description="Water volume of boiler"
    )

    min_power = attribute.Attribute(
        name='min_power',
        description="Minimum power that boiler operates at"
    )

    rated_power = attribute.Attribute(
        name='rated_power',
        description="Rated power of boiler",
    )

    efficiency = attribute.Attribute(
        name='efficiency',
        description="Efficiency of boiler provided as list with pairs of [percentage_of_rated_power,efficiency]"
    )


class Pipe(element.Element):
    ifc_type = "IfcPipeSegment"

    diameter = attribute.Attribute(
        name='diameter',
        default_ps=('Pset_PipeSegmentTypeCommon', 'NominalDiameter'),
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=diameter_post_processing,
    )
    # @property
    # def diameter(self):
    #     result = self.find('diameter')
    #
    #     if isinstance(result, list):
    #         return np.average(result).item()
    #     return result

    @staticmethod
    def _length_from_geometry(bind, name):
        try:
            return Pipe.get_lenght_from_shape(bind.ifc.Representation)
        except AttributeError:
            return None

    length = attribute.Attribute(
        name='length',
        default_ps=('Qto_PipeSegmentBaseQuantities', 'Length'),
        patterns=[
            re.compile('.*Länge.*', flags=re.IGNORECASE),
            re.compile('.*Length.*', flags=re.IGNORECASE),
        ],
        functions=[_length_from_geometry],
    )

    @staticmethod
    def get_lenght_from_shape(ifc_representation):
        """Serach for extruded depth in representations

        Warning: Found extrusion may net be the required length!
        :raises: AttributeError if not exactly one extrusion is found"""
        candidates = []
        try:
            for representation in ifc_representation.Representations:
                for item in representation.Items:
                    if item.is_a() == 'IfcExtrudedAreaSolid':
                        candidates.append(item.Depth)
        except:
            raise AttributeError("Failed to determine length.")
        if not candidates:
            raise AttributeError("No representation to determine length.")
        if len(candidates) > 1:
            raise AttributeError("Too many representations to dertermine length %s." % candidates)

        return candidates[0]


class PipeFitting(element.Element):
    ifc_type = "IfcPipeFitting"

    diameter = attribute.Attribute(
        name='diameter',
        default_ps=('Pset_PipeFittingTypeCommon', 'NominalDiameter'),
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=diameter_post_processing,
    )

    length = attribute.Attribute(
        name='length',
        default=0,
    )

    pressure_class = attribute.Attribute(
        name='pressure_class',
        default_ps=('Pset_PipeFittingTypeCommon', 'PressureClass')
    )

    @staticmethod
    def _diameter_post_processing(value):
        if isinstance(value, list):
            return np.average(value).item()
        return value


class SpaceHeater(element.Element):
    ifc_type = 'IfcSpaceHeater'

    def is_consumer(self):
        return True

    nominal_power = attribute.Attribute(
        name='nominal_power',
        description="Nominal power of SpaceHeater",
        default=42,
    )


class HeatPump(element.Element):
    ifc_type = 'IfcUnitaryEquipment'

    def is_consumer(self):
        return True

    nominal_power = attribute.Attribute(
        name='nominal_power',
        description="Nominal power of SpaceHeater",
        default=42,
    )


class Chiller(element.Element):
    ifc_type = 'IfcChiller'

    def is_consumer(self):
        return True

    nominal_power = attribute.Attribute(
        name='nominal_power',
        description="Nominal power of SpaceHeater",
        default=42,
    )


class StorageDevice(element.Element):
    ifc_type = "IfcStorageDevice"


class Storage(element.Element):
    ifc_type = "IfcTank"

    @property
    def storage_type(self):
        return None

    @property
    def height(self):
        return 1

    @property
    def diameter(self):
        return 1

    @property
    def port_positions(self):
        return (0, 0.5, 1)

    @property
    def volume(self):
        return self.height * self.diameter ** 2 / 4 * math.pi


class Distributor(element.Element):
    ifc_type = "IfcDistributionChamberElement"

    @property
    def volume(self):
        return 100

    @property
    def nominal_power(self):  # TODO Workaround, should come from aggregation of consumer circle
        return 100


class Pump(element.Element):
    ifc_type = "IfcPump"

    @property
    def rated_power(self):
        return 3

    @property
    def rated_height(self):
        return 8

    @property
    def rated_volume_flow(self):
        return 4.3

    @property
    def diameter(self):
        return 40


class Valve(element.Element):
    ifc_type = "IfcValve"

    @cached_property
    def diameter(self):
        return

    @cached_property
    def length(self):
        return


class Duct(element.Element):
    ifc_type = "IfcDuctSegment"

    @property
    def diameter(self):
        return 1

    @property
    def length(self):
        return 1


class DuctFitting(element.Element):
    ifc_type = "IfcDuctFitting"

    @property
    def diameter(self):
        return 1

    @property
    def length(self):
        return 1


class AirTerminal(element.Element):
    ifc_type = "IfcAirTerminal"

    @property
    def diameter(self):
        return 1

class ThermalZone(element.Element):
    ifc_type = "IfcSpace"

    area = attribute.Attribute(
        name='area',
        default_ps=('Dimensions', 'Area'),
        default=0
    )

    @classmethod
    def add_elements_space(cls, space, hvac_instances):

        thermal_zone = cls(space)
        settings = ifcopenshell.geom.settings()
        vertices = []
        shape = ifcopenshell.geom.create_shape(settings, space)
        i = 0
        while i < len(shape.geometry.verts):
            vertices.append((shape.geometry.verts[i] + thermal_zone.position[0],
                             shape.geometry.verts[i + 1] + thermal_zone.position[1]))
            i += 3
        polygon = Polygon(vertices)

        bps_space_elements = []

        for ele in space.BoundedBy:
            if ele.RelatedBuildingElement:
                representation = Element.factory(ele.RelatedBuildingElement)

                if not isinstance(representation, element.Dummy):
                    bps_space_elements.append(representation)

        hvac_space_elements = []

        for ele in hvac_instances:
            if (not isinstance(hvac_instances[ele], elements.PipeFitting)) and \
                    (not isinstance(hvac_instances[ele], elements.Pipe)):
                if abs(hvac_instances[ele].position[2]/1000-thermal_zone.position[2]) < 3: # in same floor?
                    point = Point(hvac_instances[ele].position[0]/1000, hvac_instances[ele].position[1]/1000)
                    if polygon.contains(point):
                        hvac_space_elements.append(hvac_instances[ele])
                        # plt.plot(*point.xy, marker='x')
                        # plt.plot(*polygon.exterior.xy)
                        # plt.show()

        thermal_zone._bps_space_elements = bps_space_elements #get bps instances in workflow.bps
        thermal_zone._hvac_space_elements = hvac_space_elements

        for ele in thermal_zone._bps_space_elements:
            ele.thermal_zones.append(thermal_zone)
        for ele in thermal_zone._hvac_space_elements:
            ele.thermal_zones.append(thermal_zone)

        return thermal_zone


class Medium(element.Element):
    ifc_type = "IfcDistributionSystems"


class Wall(element.Element):
    ifc_type = "IfcWall"

    @staticmethod
    def get_orientation(bind, name):
        if bind.is_external is True:
            orientation = []
            placementrel = bind.ifc.ObjectPlacement.PlacementRelTo
            while placementrel is not None:
                if placementrel.PlacementRelTo is None:
                    orientation = placementrel.RelativePlacement.RefDirection.DirectionRatios[0:2]
                placementrel = placementrel.PlacementRelTo
            sign = bind.ifc.ObjectPlacement.RelativePlacement.RefDirection
            orientation_wall = [None, None]
            if sign:
                if sign.DirectionRatios[0] != 0:
                    if sign.DirectionRatios[0] > 0:
                        orientation_wall[0] = -orientation[1]
                        orientation_wall[1] = orientation[0]
                    else:
                        orientation_wall[0] = orientation[1]
                        orientation_wall[1] = -orientation[0]
                elif sign.DirectionRatios[1] != 0:
                    if sign.DirectionRatios[1] > 0:
                        orientation_wall[0] = -orientation[0]
                        orientation_wall[1] = -orientation[1]
                    else:
                        orientation_wall[0] = orientation[0]
                        orientation_wall[1] = orientation[1]
            else:
                orientation_wall[0] = -orientation[1]
                orientation_wall[1] = orientation[0]
            if orientation_wall[0] > 0:
                if orientation_wall[1] > 0:
                    angle_wall = 270 - math.degrees(math.atan(orientation_wall[1] / orientation_wall[0]))
                else:
                    angle_wall = 270 + abs(math.degrees(math.atan(orientation_wall[1] / orientation_wall[0])))
            else:
                if orientation_wall[1] < 0:
                    angle_wall = math.degrees(math.atan(orientation_wall[0] / orientation_wall[1]))
                else:
                    angle_wall = 180 - abs(math.degrees(math.atan(orientation_wall[0] / orientation_wall[1])))
        else:
            angle_wall = "Intern"
        return angle_wall

    area = attribute.Attribute(
        name='area',
        default_ps=('Dimensions', 'Area'),
        default=0
    )

    is_external = attribute.Attribute(
        name='is_external',
        default_ps=('Pset_WallCommon', 'IsExternal'),
        default=0
    )

    orientation = attribute.Attribute(
        name='orientation',
        functions=[get_orientation],
        default=0
    )

    @property
    def capacity(self):
        return 1

    @property
    def u_value(self):
        return 1


class Window(element.Element):
    ifc_type = "IfcWindow"

    @staticmethod
    def get_orientation(bind, name):
        Wall.get_orientation(bind, name)

    is_external = attribute.Attribute(
        name='is_external',
        default_ps=('Pset_WindowCommon', 'IsExternal'),
        default=True
    )
    orientation = attribute.Attribute(
        name='orientation',
        functions=[get_orientation],
        default=0
    )

    @property
    def area(self):
        return 1

    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1


class Plate(element.Element):
    ifc_type = "IfcPlate"

    @property
    def area(self):
        return 1

    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1


class Slab(element.Element):
    ifc_type = "IfcSlab"

    @cached_property
    def Pset_SlabCommon(self):
        return self.get_propertysets()

    @property
    def area(self):
        if "Abmessungen" in self.Pset_SlabCommon:
            area_value = self.Pset_SlabCommon["Abmessungen"]["Fläche"]
        else:
            area_value = 0
        return area_value

    @property
    def is_external(self):
        if self.ifc.Tag == 'True':
            return True
        else:
            return False


    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1



__all__ = [ele for ele in locals().values() if ele in element.Element.__subclasses__()]
