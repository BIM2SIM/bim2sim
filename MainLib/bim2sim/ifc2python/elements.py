"""Module contains the different classes for all HVAC elements"""

import math

from bim2sim.decorator import cached_property
from bim2sim.ifc2python import element


class Boiler(element.Element):
    """Boiler"""
    ifc_type = 'IfcBoiler'

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

    def __init__(self, ifc):
        super().__init__(ifc)

        
        self.add_port("port_a", ifc.HasPorts[0].RelatingPort)
        self.add_port("port_a", ifc.HasPorts[1].RelatingPort)

    @cached_property
    def Pset_PipeSegmentTypeCommon(self):
        return self.get_propertysets('Pset_PipeSegmentTypeCommon')

    @property
    def diameter(self):
        return self.ps_abmessungen.get('NominalDiameter')

    @property
    def length(self):
        return None


class PipeFitting(element.Element):
    ifc_type = "IfcPipeFitting"

    @cached_property
    def Pset_PipeFittingTypeCommon(self):
        return self.get_propertysets('Pset_PipeFittingTypeCommon')

    @property
    def diameter(self):
        return self.Pset_PipeFittingTypeCommon.get('NominalDiameter')

    @property
    def length(self):
        return None

    @property
    def pressure_class(self):
        return self.Pset_PipeFittingTypeCommon.get('PressureClass')


class SpaceHeater(element.Element):
    ifc_type = 'IfcSpaceHeater'

    @cached_property
    def nominal_power(self):
        return 42.0

    @cached_property
    def length(self):
        return 42.0


class StorageDevice(element.Element):
    ifc_type = "IfcStorageDevice"


class Storage(element.Element):
    ifc_type = "IfcTank"

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


class Pump(element.Element):
    ifc_type = "IfcPump"

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


class Medium(element.Element):
    ifc_type = "IfcDistributionSystems"
