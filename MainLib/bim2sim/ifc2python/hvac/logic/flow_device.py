from bim2sim.ifc2python.hvac.logic.hvac_object import HVACObject


class FlowDevice(HVACObject):
    def __init__(self,parent=None):
        super(FlowDevice,self).__init__(parent)
        self.ports_in = None
        self.ports_out = None
