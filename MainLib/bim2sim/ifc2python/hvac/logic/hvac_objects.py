from bim2sim.ifc2python.hvac.logic.energy_conversion_device \
    import EnergyConversionDevice
from bim2sim.ifc2python.hvac.logic.flow_device \
    import FlowDevice
from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python.hvac.logic.hvac_object import HVACObject


class Boiler(EnergyConversionDevice):
    """HVACObject class.

        This is the base class for all HVAC elements.

        Parameters
        ----------

        parent : HVACSystem()
            The parent class of this object, the HVACSystem the HVACObject
            belongs to.
            Default is None.

        Attributes
        ----------

        IfcGUID: str
            The GUID of the corresponding IFC element.
        water_volume: float
            Water volume of boiler.
        min_power: float
            Minimum power that boiler operates at.
        rated_power: float
            Rated power of boiler.
        efficiency: list
            Efficiency of boiler provided as list with pairs of [
            percentage_of_rated_power,efficiency]
        """

    def __init__(self, parent=None):
        super(Boiler, self).__init__(parent)
        self.corresponding_ifc_element = 'IfcBoiler'
        self.water_volume = 0.008
        self.min_power = None
        self.rated_power = None
        self.efficiency = None


class Pipe(FlowDevice):
    def __init__(self, parent=None):
        super(Pipe, self).__init__(parent)
        self.diameter = None
        self.length = None

    def calc_length(self, strangliste):
        length = 0
        a = 0
        for g in strangliste:
            if ifc2python.getElementType(ifcElement=g) == 'IfcPipeSegment':
                Abmessungen = ifc2python.get_Property_Sets('Abmessungen', element=g)
                a = Abmessungen['Länge']
                length += a
        self.length = length

    def calc_median_diameter(self, strangliste):
        diameter = 0
        c = self.length
        for h in strangliste:
            if ifc2python.getElementType(ifcElement=h) == 'IfcPipeSegment':
                Abmessungen = ifc2python.get_Property_Sets('Abmessungen', element=h)
                #Länge
                length = Abmessungen['Länge']
                #Außendurchmesser
                outer_diameter = Abmessungen['Außendurchmesser']
                diameter += (length/c) * outer_diameter
        self.diameter = diameter


class SpaceHeater(FlowDevice):
    def __init__(self, parent=None):
        super(SpaceHeater, self).__init__(parent)
        self.length = None
        self.nominal_power = None


class StorageDevice(HVACObject):
    def __init__(self, parent=None):
        super(StorageDevice, self).__init__(parent)


class Valve(FlowDevice):

    def __init__(self, parent=None):
        super(Valve, self).__init__(parent)
        self.diameter = None
        self.length = None


class GenericDevice(HVACObject):
    """
    dummy device
    """
    def __init__(self, parent=None):
        super(GenericDevice, self).__init__(parent)
