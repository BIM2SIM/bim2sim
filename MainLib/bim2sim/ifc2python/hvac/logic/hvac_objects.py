"""Module contains the different classes for all HVAC elements"""

from bim2sim.ifc2python import ifc2python


class HVACObject(object):
    """HVACObject class.

    This is the base class for all HVAC elements.

    Parameters
    ----------


    parent: HVACSystem()
        The parent class of this object, the HVACSystem the HVACObject
        belongs to.
        Default is None.


    Attributes
    ----------

    IfcGUID: list of strings
        A list with the GUID of the corresponding IFC elements, in general
        only one element, for pipeStrand mostly more than one.
    """
    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
        """Constructor for HVACObject"""

        self.parent = parent
        self.ifcfile = ifcfile
        self.IfcGUID = IfcGUID
        self.graph = graph
        self.flow_ports_in = []
        self.flow_ports_out = []
        self.heat_ports = []
        self.zone = None

    def get_port_connections(self, graph, node):
        for next_node in list(graph.successors(node)):
            self.flow_ports_out.append(graph.node[next_node][
                                           'belonging_object'])
        for previous_node in list(graph.predecessors(node)):
            self.flow_ports_out.append(graph.node[previous_node][
                                           'belonging_object'])

class FlowDevice(HVACObject):
    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
        super(FlowDevice, self).__init__(graph, IfcGUID, ifcfile, parent)


class EnergyConversionDevice(HVACObject):
    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
        super(EnergyConversionDevice,self).__init__(graph, IfcGUID, ifcfile,
                                                    parent)


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

    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
        super(Boiler, self).__init__(graph, IfcGUID, ifcfile, parent)
        self.corresponding_ifc_element = 'IfcBoiler'
        self.water_volume = 0.008
        self.min_power = None
        self.rated_power = None
        self.efficiency = None


class Pipe(FlowDevice):
    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
        super(Pipe, self).__init__(graph, IfcGUID, ifcfile, parent)
        self.diameter = 0
        self.length = 0
        self.calc_attributes()

    def calc_attributes(self):
        """
        Calculates the length and diameter of the pipe. If more than
        one pipe was contracted the total length and the median diameter are
        used.
        """
        diameter_times_length = 0
        length_total = 0
        for guid in self.IfcGUID:
            element = ifc2python.getElementByGUID(ifcfile=self.ifcfile,
                                                  guid=guid)
            if ifc2python.getElementType(element) == 'IfcPipeSegment':
                length = ifc2python.get_Property_Sets(
                    'Abmessungen', element=element)['Länge']
                diameter = ifc2python.get_Property_Sets(
                    'Abmessungen', element=element)['Innendurchmesser']
                diameter_times_length += length * diameter
                length_total += length
        self.diameter = diameter_times_length / length_total

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


class PipeFitting(FlowDevice):
    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
        super(PipeFitting, self).__init__(graph, IfcGUID, ifcfile, parent)
        self.diameter = 0
        self.radius = 0
        self.length = 0
        self.angle = 0
        #self.calc_attributes()

    def calc_attributes(self):
        element = ifc2python.getElementByGUID(ifcfile=self.ifcfile,
                                              guid=self.IfcGUID)
        # todo doesn't work for "übergang" fix
        self.diameter = \
            ifc2python.get_Property_Sets(
                'Abmessungen',
                element=element)['Nenndurchmesser']
        self.length = \
            ifc2python.get_Property_Sets(
                'Abmessungen',
                element=element)['Muffenlänge']
        self.radius = \
            ifc2python.get_Property_Sets(
                'Abmessungen',
                element=element)['Bogenradius']
        self.angle = \
            ifc2python.get_Property_Sets(
                'Abmessungen',
                element=element)['Winkel']
    pass

class SpaceHeater(FlowDevice):
    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
        super(SpaceHeater, self).__init__(graph, IfcGUID, ifcfile, parent)
        self.length = None
        self.nominal_power = None


class StorageDevice(HVACObject):
    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
        super(StorageDevice, self).__init__(graph, IfcGUID, ifcfile, parent)


class Valve(FlowDevice):
    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
        super(Valve, self).__init__(graph, IfcGUID, ifcfile, parent)
        self.diameter = None
        self.length = None


class GenericDevice(HVACObject):
    """
    dummy device
    """
    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
        super(GenericDevice, self).__init__(graph, IfcGUID, ifcfile, parent)
