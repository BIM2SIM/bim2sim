from MainLib.bim2sim.ifc2python.hvac.logic.energy_conversion_device \
    import EnergyConversionDevice

class Boiler(EnergyConversionDevice):

    def __init__(self,parent=None):
        super(Boiler,self).__init__(parent)
