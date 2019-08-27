"""Module contains the different classes for all HVAC elements"""

import math
import re

import numpy as np

from bim2sim.decorators import cached_property
from bim2sim.ifc2python import element, condition
from bim2sim.decision import BoolDecision


class HeatPump(element.Element):
    """"HeatPump"""

    ifc_type = 'IfcHeatPump'

    pattern_ifc_type = [
        re.compile('Heat.?pump', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?pumpe', flags=re.IGNORECASE),
    ]

    @cached_property
    def min_power(self):
        """min_power: float
            Minimum power that HeatPump operates at."""
        return None

    @cached_property
    def rated_power(self):
        """rated_power: float
            Rated power of HeatPump."""
        return None

    @cached_property
    def efficiency(self):
        """efficiency: list
            Efficiency of HeatPump provided as list with pairs of [
            percentage_of_rated_power,efficiency]"""
        return None


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
                        "Use %s as VL?"%(port),
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
                        "Use %s as RL?"%(port),
                        global_key=port.guid,
                        allow_save=True,
                        allow_load=True)
                    use = decision.decide()
                    if use:
                        RL.append(port)
        if len(VL) == 1 and len(RL) == 1:
            connections.append((RL[0], VL[0]))
        else:
            self.logger.warning("Unable to solve inner connections for %s", self)

        return connections

    @cached_property
    def water_volume(self):
        """water_volume: float
            Water volume of boiler."""
        return 0.008

    @cached_property
    def min_power(self):
        """min_power: float
            Minimum power that boiler operates at."""
        return None

    @cached_property
    def rated_power(self):
        """rated_power: float
            Rated power of boiler."""
        return None

    @cached_property
    def efficiency(self):
        """efficiency: list
            Efficiency of boiler provided as list with pairs of [
            percentage_of_rated_power,efficiency]"""
        return None


class Pipe(element.Element):
    ifc_type = "IfcPipeSegment"
    pattern_ifc_type = [
        re.compile('Pipe', flags=re.IGNORECASE),
        re.compile('Rohr', flags=re.IGNORECASE)
    ]
    default_diameter = ('Pset_PipeSegmentTypeCommon', 'NominalDiameter')
    pattern_diameter = [
        re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
        re.compile('.*Diameter.*', flags=re.IGNORECASE),
    ]
    default_length = ('Qto_PipeSegmentBaseQuantities', 'Length')
    pattern_length = [
        re.compile('.*Länge.*', flags=re.IGNORECASE),
        re.compile('.*Length.*', flags=re.IGNORECASE),
    ]
    conditions = [
        condition.RangeCondition("diameter", 5.0, 200.00)   #ToDo: unit?!
    ]

    @property
    def diameter(self):
        result = self.find('diameter')

        if isinstance(result, list):
            return np.average(result).item()
        return result

    @property
    def length(self):
        try:
            return self.get_lenght_from_shape(self.ifc.Representation)
        except AttributeError:
            return None

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
            raise AttributeError("Failed to dertermine length.")
        if not candidates:
            raise AttributeError("No representation to dertermine length.")
        if len(candidates) > 1:
            raise AttributeError("Too many representations to dertermine length %s."%candidates)
        return candidates[0]


class PipeFitting(element.Element):
    ifc_type = "IfcPipeFitting"
    pattern_ifc_type = [
        # re.compile('Pipe', flags=re.IGNORECASE),
        # re.compile('Rohr', flags=re.IGNORECASE)
    ]
    default_diameter = ('Pset_PipeFittingTypeCommon', 'NominalDiameter')
    default_pressure_class = ('Pset_PipeFittingTypeCommon', 'PressureClass')
    
    pattern_diameter = [
        re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
        re.compile('.*Diameter.*', flags=re.IGNORECASE),
    ]

    @property
    def diameter(self):
        result = self.find('diameter')

        if isinstance(result, list):
            return np.average(result).item()
        return result

    @property
    def length(self):
        return self.find('length')

    @property
    def pressure_class(self):
        return self.find('pressure_class')


class SpaceHeater(element.Element):
    ifc_type = 'IfcSpaceHeater'
    pattern_ifc_type = [
        re.compile('Space.?heater', flags=re.IGNORECASE)
    ]
    @cached_property
    def nominal_power(self):
        return 42.0

    @cached_property
    def length(self):
        return 42.0


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
    def hight(self):
        return 1

    @ property
    def diameter(self):
        return 1

    @property
    def port_positions(self):
        return (0, 0.5, 1)

    @property
    def volume(self):
        return self.hight * self.diameter ** 2 / 4 * math.pi


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
    def rated_hight(self):
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

    @cached_property
    def diameter(self):
        return

    @cached_property
    def length(self):
        return


class Duct(element.Element):
    ifc_type = "IfcDuctSegment"
    pattern_ifc_type = [
        re.compile('Duct.?segment', flags=re.IGNORECASE)
        ]
    @property
    def diameter(self):
        return 1

    @property
    def length(self):
        return 1


class DuctFitting(element.Element):
    ifc_type = "IfcDuctFitting"
    pattern_ifc_type = [
        re.compile('Duct.?fitting', flags=re.IGNORECASE)
        ]
    @property
    def diameter(self):
        return 1

    @property
    def length(self):
        return 1


class AirTerminal(element.Element):
    ifc_type = "IfcAirTerminal"
    pattern_ifc_type = [
        re.compile('Air.?terminal', flags=re.IGNORECASE)
        ]

    @property
    def diameter(self):
        return 1


class ThermalZones(element.Element):
    ifc_type = "IfcSpace"
    pattern_ifc_type = [
        re.compile('Space', flags=re.IGNORECASE),
        re.compile('Zone', flags=re.IGNORECASE)
        ]


class Medium(element.Element):
    ifc_type = "IfcDistributionSystems"
    pattern_ifc_type = [
        re.compile('Medium', flags=re.IGNORECASE)
        ]


class Wall(element.Element):
    ifc_type = "IfcWall"
    pattern_ifc_type = [
        re.compile('Wall', flags=re.IGNORECASE),
        re.compile('Wand', flags=re.IGNORECASE)
        ]

    @property
    def area(self):
        return 1

    @property
    def capacity(self):
        return 1

    @property
    def u_value(self):
        return 1


class OuterWall(Wall):
    pattern_ifc_type = [
        re.compile('Outer.?wall', flags=re.IGNORECASE),
        re.compile('Außen.?wand', flags=re.IGNORECASE)
        ]

    @property
    def orientation(self):
        return 1


class Window(element.Element):
    ifc_type = "IfcWindow"
    pattern_ifc_type = [
        re.compile('Window', flags=re.IGNORECASE),
        re.compile('Fenster', flags=re.IGNORECASE)
        ]

    @property
    def area(self):
        return 1

    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1

__all__ = [ele for ele in locals().values() if ele in element.Element.__subclasses__()]
