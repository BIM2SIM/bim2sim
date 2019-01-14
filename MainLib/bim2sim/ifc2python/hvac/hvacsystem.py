""" This module holds a HVACSystem object which is represented by a graph
network
where each node represents a hvac-component
"""
from os.path import dirname
import logging
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python.hvac.hvac_specific_functions import create_object_from_ifc
from bim2sim.ifc2python.hvac.hvac_specific_functions import connect_elements_by_coordinates


class HVACSystem(object):
    def __init__(self, model):
        self.logger = logging.getLogger(__name__)
        self.ifc = model
        self.hvac_graph = None
        self.create_hvac_network()
        self.hvac_graph = self.reduce_strangs()
        self.draw_hvac_network()

    def create_hvac_network(self, element_types=None):
        """
        This function defines the hvac as graph network, each element is
        represented by a node. The nodes are connected by the geometrical
        positions of their ports.
        """
        self.logger.info("Creating HVAC network")

        if element_types is None:
            element_types = ['IfcSpaceHeater',
                             'IfcPipeFitting',
                             'IfcPipeSegment',
                             'IfcTank',
                             'IfcBoiler',
                             'IfcUnitaryEquipment']
        graph = nx.DiGraph()
        parts = {}
        # all absolute coordinates of the ports are calculated and saved
        # in the parts dict
        for element_type in element_types:
            elements = self.ifc.by_type(element_type)
            for element in elements:
                try:
                    a = element.ObjectPlacement.RelativePlacement
                    x1 = a.RefDirection.DirectionRatios[0]
                    x2 = a.RefDirection.DirectionRatios[1]
                    x3 = a.RefDirection.DirectionRatios[2]
                    x = np.array([x1, x2, x3])
                    z1 = a.Axis.DirectionRatios[0]
                    z2 = a.Axis.DirectionRatios[1]
                    z3 = a.Axis.DirectionRatios[2]
                    z = np.array([z1, z2, z3])
                except:
                    x = np.array([1, 0, 0])
                    z = np.array([0, 0, 1])
                y = np.cross(z, x)
                graph.add_node(element, type=ifc2python.getElementType(
                    element), oid=element.id())
                element_port_connections = element.HasPorts
                ports = {}
                for element_port_connection in element_port_connections:
                    b = element.ObjectPlacement.RelativePlacement.Location \
                        .Coordinates
                    c = element_port_connection.RelatingPort.ObjectPlacement \
                        .RelativePlacement.Location.Coordinates
                    coordinate = []
                    for i in range(0, 3):
                        coordinate.append(
                            b[i] + x[i] * c[0] + y[i] * c[1] + z[i] * c[2])
                    ports[element_port_connection.RelatingPort] = {}
                    ports[element_port_connection.RelatingPort]['coordinate'] \
                        = coordinate
                    ports[element_port_connection.RelatingPort][
                        'flow_direction'] =  \
                        element_port_connection.RelatingPort.FlowDirection
                    parts[element] = ports
        graph = connect_elements_by_coordinates(graph=graph, parts=parts,
                                                threshold=1)
        self.hvac_graph = graph
        self.logger.debug("Number of nodes: %d", graph.number_of_nodes())

    def reduce_strangs(self):
        """
        This function creates all strands. Each strand starts with an
        element that has 3 or more ports. Each strandfinishes with an
        element that has 3 or more ports or with an IFCAIRTERMINAL. For
        each strand a list with the elements of the strand is created.
        """
        graph = self.hvac_graph
        reducible_elements = ['IfcPipeSegment', 'IfcPipeFitting']
        nx.set_node_attributes(graph, [], 'contracted_nodes')
        reduced_nodes = 0
        for node in graph.nodes():
            nodes_nb = list(set(nx.all_neighbors(graph, node)) - set(
                graph.node[node]['contracted_nodes']) - {node})
            if len(nodes_nb) == 2 and ifc2python.getElementType(node) in \
                    reducible_elements:
                for node_nb in nodes_nb:
                    nodes_nb_nb = list(set(nx.all_neighbors(graph, node_nb)) -
                        set(graph.node[node_nb]['contracted_nodes']) -
                        {node_nb})
                    if len(nodes_nb_nb) <= 2 and ifc2python.getElementType(
                            node_nb) in \
                            reducible_elements:
                        graph.node[node_nb]['contracted_nodes'] = \
                            graph.node[node_nb]['contracted_nodes'] + [node]
                        graph = nx.contracted_nodes(graph, node_nb, node)
                        reduced_nodes += 1
                        break
        self.logger.debug("Number of nodes: %d", reduced_nodes)
        return graph

        # todo: add create_object_from_ifc(ifc_element=element)

    def draw_hvac_network(self, label='oid'):
        """
        Function to deliver a graphical output of the HVAC network.
        :param label: label to display at the nodes, default is ifc oid,
        can also be type
        :return:
        """
        labels = nx.get_node_attributes(self.hvac_graph, label)
        nx.draw(self.hvac_graph, labels=labels, node_size=3, font_size=6,
                with_labels=True)
        plt.draw()
        plt.show()


if __name__ == '__main__':
    import ifcopenshell
    IfcFile = ifcopenshell.open(
        dirname(dirname(dirname(dirname(dirname((__file__)))))) +
        '/ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements'
        '.ifc')
    Test = HVACSystem(IfcFile)

