from MainLib.bim2sim.ifc2python.hvac.logic.flow_device \
    import FlowDevice

class PipeStrand(FlowDevice):

    def __init__(self,parent=None):
        super(PipeStrand, self).__init__(parent)
        self.diameter = None
        self.length = None


