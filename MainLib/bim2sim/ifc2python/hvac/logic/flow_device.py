from bim2sim.ifc2python.hvac.logic.hvac_object import HVACObject


class FlowDevice(HVACObject):
    def __init__(self, parent=None):
        super(FlowDevice, self).__init__(parent)
        self.flow_ports_in = []
        self.flow_ports_out = []
        self.heat_ports = []
        self.zone = None
