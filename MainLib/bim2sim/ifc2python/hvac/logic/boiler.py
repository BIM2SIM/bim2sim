from bim2sim.ifc2python.hvac.logic.energy_conversion_device \
    import EnergyConversionDevice

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
        super(Boiler,self).__init__(parent)
        self.corresponding_ifc_element = 'IfcBoiler'
        self.water_volume = 0.008
        self.min_power = None
        self.rated_power = None
        self.efficiency = None

if __name__ == '__main__':
    from os.path import dirname
    import ifcopenshell


    # todo: get ifc file from top function bim2sim
    IfcFile = ifcopenshell.open(
        dirname(dirname(dirname(dirname(dirname(dirname((__file__))))))) +
        '/ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_Spaceheaters'
        '.ifc')
    element = IfcFile.by_type('IfcBoiler')[0]
    print(getattr(element,'GlobalId'))
    # test = Boiler()
    # test.ifc_element = element
    # print(test.ifc_element)

