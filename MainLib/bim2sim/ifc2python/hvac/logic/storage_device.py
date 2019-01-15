from bim2sim.ifc2python.hvac.logic.hvac_object import HVACObject


class StorageDevice(HVACObject):
    def __init__(self, parent=None):
        super(StorageDevice, self).__init__(parent)
