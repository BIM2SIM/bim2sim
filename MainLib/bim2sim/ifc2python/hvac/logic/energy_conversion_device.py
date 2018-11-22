from MainLib.bim2sim.ifc2python.hvac.logic.hvac_object import HVACObject
import MainLib.bim2sim.ifc2python.ifc2python as ifc2python
import ifcopenshell

file = ifcopenshell.open('D:/01_GitHub/Bim2SimHiWi/Bim2Sim/03_Ifc2Python'
                         '/examples/ifc_testfiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_Spaceheaters.ifc')
element = file.by_type('IFCSPACEHEATER')[0]
print(ifc2python.getIfcAttribute(element, 'ConnectedFrom'))
class EnergyConversionDevice(HVACObject):
    def __init__(self, parent=None):
        super(EnergyConversionDevice,self).__init__(parent)
        print(ifc2python.getIfcAttribute(element, 'connectedFrom'))

if __name__ == '__main__':
    test = EnergyConversionDevice()
    print(test)