"""Module contains the different classes for all HVAC elements"""

import math
import re

import numpy as np

from bim2sim.decorators import cached_property
from bim2sim.kernel import element, condition, attribute
from bim2sim.decision import BoolDecision
from shapely.geometry.polygon import Polygon
from shapely.geometry import Point
import ifcopenshell.geom
import matplotlib.pyplot as plt
from bim2sim.kernel.element import Element

def diameter_post_processing(value):
    if isinstance(value, list):
        return np.average(value).item()
    return value


class HeatPump(element.Element):
    """"HeatPump"""

    ifc_type = 'IfcHeatPump'

    pattern_ifc_type = [
        re.compile('Heat.?pump', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?pumpe', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        name='min_power',
        description='Minimum power that HeatPump operates at.',
    )
    rated_power = attribute.Attribute(
        name='rated_power',
        description='Rated power of HeatPump.',
    )
    efficiency = attribute.Attribute(
        name='efficiency',
        description='Efficiency of HeatPump provided as list with pairs of [percentage_of_rated_power,efficiency]'
    )


class Chiller(element.Element):
    """"Chiller"""

    ifc_type = 'IfcChiller'

    pattern_ifc_type = [
        re.compile('Chiller', flags=re.IGNORECASE),
        re.compile('K(ä|ae)lte.?maschine', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        name='min_power',
        description='Minimum power that Chiller operates at.',
    )
    rated_power = attribute.Attribute(
        name='rated_power',
        description='Rated power of Chiller.',
    )
    efficiency = attribute.Attribute(
        name='efficiency',
        description='Efficiency of Chiller provided as list with pairs of [percentage_of_rated_power,efficiency]'
    )


class CoolingTower(element.Element):
    """"CoolingTower"""

    ifc_type = 'IfcCoolingTower'

    pattern_ifc_type = [
        re.compile('Cooling.?Tower', flags=re.IGNORECASE),
        re.compile('Recooling.?Plant', flags=re.IGNORECASE),
        re.compile('K(ü|ue)hl.?turm', flags=re.IGNORECASE),
        re.compile('R(ü|ue)ck.?K(ü|ue)hl.?(werk|turm|er)', flags=re.IGNORECASE),
        re.compile('RKA', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        name='min_power',
        description='Minimum power that CoolingTower operates at.',
    )
    rated_power = attribute.Attribute(
        name='rated_power',
        description='Rated power of CoolingTower.',
    )
    efficiency = attribute.Attribute(
        name='efficiency',
        description='Efficiency of CoolingTower provided as list with pairs of [percentage_of_rated_power,efficiency]'
    )


class HeatExchanger(element.Element):
    """"Heatexchanger"""

    ifc_type = 'IfcHeatExchanger'

    pattern_ifc_type = [
        re.compile('Heat.?Exchanger', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?(ü|e)bertrager', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?tauscher', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        name='min_power',
        description='Minimum power that HeatExchange operates at.',
    )
    rated_power = attribute.Attribute(
        name='rated_power',
        description='Rated power of HeatExchange.',
    )
    efficiency = attribute.Attribute(
        name='efficiency',
        description='Efficiency of HeatExchange provided as list with pairs of [percentage_of_rated_power,efficiency]'
    )


class Boiler(element.Element):
    """Boiler"""
    ifc_type = 'IfcBoiler'

    pattern_ifc_type = [
        #re.compile('Heat.?pump', flags=re.IGNORECASE),
        re.compile('Kessel', flags=re.IGNORECASE),
        re.compile('Boiler', flags=re.IGNORECASE),
    ]

    #def _add_ports(self):
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
    conditions = [
        condition.RangeCondition("diameter", 5.0, 300.00)   #ToDo: unit?!
    ]

    diameter = attribute.Attribute(
        name='diameter',
        default_ps=('Pset_PipeSegmentTypeCommon', 'NominalDiameter'),
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=diameter_post_processing,
    )

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

    conditions = [
        condition.RangeCondition("diameter", 5.0, 300.00)   #ToDo: unit?!
    ]

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
    pattern_ifc_type = [
        re.compile('Space.?heater', flags=re.IGNORECASE)
    ]

    def is_consumer(self):
        return True

    nominal_power = attribute.Attribute(
        name='nominal_power',
        description="Nominal power of SpaceHeater",
        default=42,
    )


class ExpansionTank(element.Element):
    ifc_type = "IfcExpansionTank"   #ToDo: Richtig?!
    pattern_ifc_type = [
        re.compile('Expansion.?Tank', flags=re.IGNORECASE),
        re.compile('Ausdehnungs.?gef(ä|ae)(ss|ß)', flags=re.IGNORECASE),
    ]


class StorageDevice(element.Element):
    ifc_type = "IfcStorageDevice"
    pattern_ifc_type = [
        re.compile('Storage.?device', flags=re.IGNORECASE)
    ]


class Storage(element.Element):
    ifc_type = "IfcTank"
    pattern_ifc_type = [
        re.compile('Tank', flags=re.IGNORECASE),
        re.compile('Speicher', flags=re.IGNORECASE),
    ]

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
    pattern_ifc_type = [
        re.compile('Distribution.?chamber', flags=re.IGNORECASE),
        re.compile('Distributior', flags=re.IGNORECASE),
        re.compile('Verteiler', flags=re.IGNORECASE)
    ]
    @property
    def volume(self):
        return 100

    @property
    def nominal_power(self):  # TODO Workaround, should come from aggregation of consumer circle
        return 100


class Pump(element.Element):
    ifc_type = "IfcPump"
    pattern_ifc_type = [
        re.compile('Pumpe', flags=re.IGNORECASE),
        re.compile('Pump', flags=re.IGNORECASE)
        ]

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
    pattern_ifc_type = [
        re.compile('Valve', flags=re.IGNORECASE),
        re.compile('Drossel', flags=re.IGNORECASE),
        re.compile('Ventil', flags=re.IGNORECASE)
    ]

    conditions = [
        condition.RangeCondition("diameter", 5.0, 500.00)  # ToDo: unit?!
    ]

    diameter = attribute.Attribute(
        name='diameter',
        description='Valve diameter',
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
            re.compile('.*DN.*', flags=re.IGNORECASE),
        ],
    )
    # @cached_property
    # def diameter(self):
    #     result = self.find('diameter')
    #
    #     if isinstance(result, list):
    #         return np.average(result).item()
    #     return result

    length = attribute.Attribute(
        name='length',
        description='Length of Valve',
    )


class Duct(element.Element):
    ifc_type = "IfcDuctSegment"
    pattern_ifc_type = [
        re.compile('Duct.?segment', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        name='diameter',
        description='Duct diameter',
    )
    length = attribute.Attribute(
        name='length',
        description='Length of Duct',
    )


class DuctFitting(element.Element):
    ifc_type = "IfcDuctFitting"
    pattern_ifc_type = [
        re.compile('Duct.?fitting', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        name='diameter',
        description='Duct diameter',
    )
    length = attribute.Attribute(
        name='length',
        description='Length of Duct',
    )


class AirTerminal(element.Element):
    ifc_type = "IfcAirTerminal"
    pattern_ifc_type = [
        re.compile('Air.?terminal', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        name='diameter',
        description='Terminal diameter',
    )


class ThermalZone(element.Element):
    ifc_type = "IfcSpace"

    pattern_ifc_type = [
        re.compile('Space', flags=re.IGNORECASE),
        re.compile('Zone', flags=re.IGNORECASE)
    ]

    area = attribute.Attribute(
        name='area',
        default_ps=('BaseQuantities', 'NetFloorArea'),
        default=0
    )

    height = attribute.Attribute(
        name='height',
        default_ps=('BaseQuantities', 'Height'),
        default=0
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bound_elements = []

    # def add_elements_space(self):
        # todo @dco whats done here?
        # settings = ifcopenshell.geom.settings()
        # vertices = []
        # shape = ifcopenshell.geom.create_shape(settings, space)
        # i = 0
        # while i < len(shape.geometry.verts):
        #     vertices.append((shape.geometry.verts[i] + thermal_zone.position[0],
        #                      shape.geometry.verts[i + 1] + thermal_zone.position[1]))
        #     i += 3
        # polygon = Polygon(vertices)


    def get__elements_by_type(self, type):
        raise NotImplementedError


class Medium(element.Element):
    ifc_type = "IfcDistributionSystems"
    pattern_ifc_type = [
        re.compile('Medium', flags=re.IGNORECASE)
    ]


class Wall(element.Element):
    ifc_type = ["IfcWall", "IfcWallStandardCase"]
    pattern_ifc_type = [
        re.compile('Wall', flags=re.IGNORECASE),
        re.compile('Wand', flags=re.IGNORECASE)
    ]
    material_selected = {}

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
        default_ps=('BaseQuantities', 'NetSideArea'),
        default=1
    )

    is_external = attribute.Attribute(
        name='is_external',
        default_ps=('Pset_WallCommon', 'IsExternal'),
        default=False
    )

    orientation = attribute.Attribute(
        name='orientation',
        functions=[get_orientation],
        default=0
    )

    thickness = attribute.Attribute(
        name='thickness',
        default_ps=('BaseQuantities', 'Width'),
        default=0
    )
    heat_capacity = attribute.Attribute(
        name='heat_capacity',
        default=0
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        default_ps=('Pset_WallCommon', 'ThermalTransmittance'),
        default=0
    )
    density = attribute.Attribute(
        name='density',
        default=0
    )
    material = attribute.Attribute(
        name='material',
        default=0
    )
        #todo just for testing, this is file specific
        default_ps=('ArchiCADProperties', 'Baustoff/Mehrschicht/Profil'),

    tilt = attribute.Attribute(
        name='thermal_transmittance',
        #todo just for testing, this is file specific
        default_ps=('ArchiCADProperties', 'Äußerer Neigungswinkel'),
        default=0
    )

    # @property
    # def capacity(self):
    #     return 1
    #
    # @property
    # def u_value(self):
    #     return 1


class Window(element.Element):
    ifc_type = "IfcWindow"
    pattern_ifc_type = [
        re.compile('Window', flags=re.IGNORECASE),
        re.compile('Fenster', flags=re.IGNORECASE)
    ]

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

    area = attribute.Attribute(
        name='area',
        default_ps=('BaseQuantities', 'NetArea'),
        default=0
    )

# class OuterWall(Wall):
#     pattern_ifc_type = [
#         re.compile('Outer.?wall', flags=re.IGNORECASE),
#         re.compile('Au(ß|ss)en.?wand', flags=re.IGNORECASE)
#     ]
#
#     @property
#     def area(self):
#         return 1
#
#     @property
#     def u_value(self):
#         return 1
#
#     @property
#     def g_value(self):
#         return 1


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

    area = attribute.Attribute(
        name='area',
        default_ps=('BaseQuantities', 'NetArea'),
        default=0
    )

    thickness = attribute.Attribute(
        name='thickness',
        default_ps=('BaseQuantities', 'Width'),
        default=0
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        default_ps=('Pset_SlabCommon', 'ThermalTransmittance'),
        default=0
    )

    is_external = attribute.Attribute(
        name='thermal_transmittance',
        default_ps=('Pset_SlabCommon', 'IsExternal'),
        default=0
    )

    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1


__all__ = [ele for ele in locals().values() if ele in element.Element.__subclasses__()]
