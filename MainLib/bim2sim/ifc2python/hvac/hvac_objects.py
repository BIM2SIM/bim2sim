"""Module contains the different classes for all HVAC elements"""

from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python import element

#class HVACObject(model.Model):
#    """HVACObject class.

#    This is the base class for all HVAC elements.

#    Parameters
#    ----------


#    parent: HVACSystem()
#        The parent class of this object, the HVACSystem the HVACObject
#        belongs to.
#        Default is None.


#    Attributes
#    ----------

#    IfcGUID: list of strings
#        A list with the GUID of the corresponding IFC elements, in general
#        only one element, for pipeStrand mostly more than one.
#    """
#    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
#        """Constructor for HVACObject"""
#        super().__init__(ifcfile)
#        self.parent = parent
#        self.ifcfile = ifcfile
#        self.IfcGUID = IfcGUID
#        self.graph = graph
#        self.flow_ports_in = []
#        self.flow_ports_out = []
#        self.heat_ports = []
#        self.zone = None

#    def get_port_connections(self, graph, node):
#        for next_node in list(graph.successors(node)):
#            self.flow_ports_out.append(graph.node[next_node][
#                                           'belonging_object'])
#        for previous_node in list(graph.predecessors(node)):
#            self.flow_ports_out.append(graph.node[previous_node][
#                                           'belonging_object'])

#class FlowDevice(HVACObject):
#    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
#        super(FlowDevice, self).__init__(graph, IfcGUID, ifcfile, parent)


#class EnergyConversionDevice(HVACObject):
#    def __init__(self, graph, IfcGUID, ifcfile, parent=None):
#        super(EnergyConversionDevice,self).__init__(graph, IfcGUID, ifcfile,
#                                                    parent)


class Boiler(element.Element):
    """Boiler"""

    ifc_type = 'IfcBoiler'

    @property
    def water_volume(self):
        """water_volume: float
            Water volume of boiler."""
        return 0.008

    @property
    def min_power(self):
        """min_power: float
            Minimum power that boiler operates at."""
        return None

    @property
    def rated_power(self):
        """rated_power: float
            Rated power of boiler."""
        return None

    @property
    def efficiency(self):
        """efficiency: list
            Efficiency of boiler provided as list with pairs of [
            percentage_of_rated_power,efficiency]"""
        return None


class Pipe(element.Element):
    ifc_type = "IfcPipe"

    @property
    def diameter(self):
        return 0.0

    @property
    def length(self):
        return 0.0

    #def combine(self, others):
    #    """
    #    Calculates the length and diameter of the pipe. If more than
    #    one pipe was contracted the total length and the median diameter are
    #    used.
    #    """
    #    diameter_times_length = 0
    #    length_total = 0
    #    for guid in self.IfcGUID:
    #        element = ifc2python.getElementByGUID(ifcfile=self.ifcfile,
    #                                              guid=guid)
    #        if ifc2python.getElementType(element) == 'IfcPipeSegment':
    #            length = ifc2python.get_Property_Sets(
    #                'Abmessungen', element=element)['Länge']
    #            diameter = ifc2python.get_Property_Sets(
    #                'Abmessungen', element=element)['Innendurchmesser']
    #            diameter_times_length += length * diameter
    #            length_total += length
    #    self.diameter = diameter_times_length / length_total


class PipeFitting(element.Element):
    ifc_type = "IfcPipeFitting"

    @property
    def diameter(self):
        return ifc2python.get_Property_Sets(
            'Abmessungen',
            element=element)['Nenndurchmesser']

    @property
    def length(self):
        return ifc2python.get_Property_Sets(
            'Abmessungen',
            element=element)['Muffenlänge']

    @property
    def radius(self):
        return ifc2python.get_Property_Sets(
            'Abmessungen',
            element=element)['Bogenradius']

    @property
    def angle(self):
        return ifc2python.get_Property_Sets(
            'Abmessungen',
            element=element)['Winkel']

class SpaceHeater(element.Element):

    ifc_type = 'IfcSpaceHeater'

    @property
    def nominal_power(self):
        return 42.0

    @property
    def length(self):
        return 42.0



class StorageDevice(element.Element):

    ifc_type = "IfcStorageDevice"


class Valve(element.Element):

    ifc_type = "IfcValve"

    @property
    def diameter(self):
        return

    @property
    def length(self):
        return

