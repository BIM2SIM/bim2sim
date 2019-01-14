from bim2sim.ifc2python.hvac.logic.flow_device \
    import FlowDevice


class SpaceHeater(FlowDevice):

    def __init__(self, parent=None):
        super(SpaceHeater, self).__init__(parent)
        self.diameter = None
        self.length = None


