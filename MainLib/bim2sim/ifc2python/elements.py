"""Module contains the different classes for all HVAC elements"""

from bim2sim.ifc2python import element


class Boiler(element.Element):
    """Boiler"""
    ifc_type = 'IfcBoiler'

    @property
    def water_volume(self):
        """water_volume: float
            Water volume of boiler."""
        return 0.008

    @property
    def min_power(self):
        """min_power: float
            Minimum power that boiler operates at."""
        return None

    @property
    def rated_power(self):
        """rated_power: float
            Rated power of boiler."""
        return None

    @property
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

    @property
    def diameter(self):
        return self.get_propertysets('Abmessungen')['Innendurchmesser']

    @property
    def length(self):
        return self.get_propertysets('Abmessungen')['Länge']


class PipeFitting(element.Element):
    ifc_type = "IfcPipeFitting"

    @property
    def diameter(self):
        return self.get_propertysets('Abmessungen').get('Nenndurchmesser')

    @property
    def length(self):
        return self.get_propertysets('Abmessungen').get('Muffenlänge')

    @property
    def radius(self):
        return self.get_propertysets('Abmessungen').get('Bogenradius')

    @property
    def angle(self):
        return self.get_propertysets('Abmessungen').get('Winkel')


class SpaceHeater(element.Element):
    ifc_type = 'IfcSpaceHeater'

    @property
    def nominal_power(self):
        return 42.0

    @property
    def length(self):
        return 42.0


class StorageDevice(element.Element):
    ifc_type = "IfcStorageDevice"


class Valve(element.Element):
    ifc_type = "IfcValve"

    @property
    def diameter(self):
        return

    @property
    def length(self):
        return
