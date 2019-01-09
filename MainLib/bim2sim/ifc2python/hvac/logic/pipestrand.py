from bim2sim.ifc2python.hvac.logic.flow_device \
    import FlowDevice
from bim2sim.ifc2python import ifc2python
class PipeStrand(FlowDevice):

    def __init__(self, parent=None):
        super(PipeStrand, self).__init__(parent)
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
        a = 0
        b = 0
        c = self.length
        for h in strangliste:
            if ifc2python.getElementType(ifcElement=h) == 'IfcPipeSegment':
                Abmessungen = ifc2python.get_Property_Sets('Abmessungen', element=h)
                #Länge
                a = Abmessungen['Länge']
                #Außendurchmesser
                b = Abmessungen['Außendurchmesser']
                diameter += (a/c) * b
        self.diameter = diameter


