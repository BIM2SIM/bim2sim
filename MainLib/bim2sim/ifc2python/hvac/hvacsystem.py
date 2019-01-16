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
from bim2sim.ifc2python.hvac.hvac_specific_functions import\
    create_generic_objects, connect_elements_by_coordinates, all_neighbors,\
    connect_generic_objects


class HVACSystem(object):
    def __init__(self, model):
        self.logger = logging.getLogger(__name__)
        self.ifc = model
        self.hvac_graph = None
        self.create_hvac_network()
        self.tranfser_to_generel_description(graph=self.hvac_graph)
        self.draw_hvac_network(label='oid')

    def create_hvac_network(self, element_types=None):
        """
        This function defines the hvac system as graph network. Each element is
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
        for element_type in element_types:
            elements = self.ifc.by_type(element_type)
            for element in elements:
                try:
                    relative_placement = \
                        element.ObjectPlacement.RelativePlacement
                    x_direction = np.array([
                        relative_placement.RefDirection.DirectionRatios[0],
                        relative_placement.RefDirection.DirectionRatios[1],
                        relative_placement.RefDirection.DirectionRatios[2]])
                    z_direction = np.array([
                        relative_placement.Axis.DirectionRatios[0],
                        relative_placement.Axis.DirectionRatios[1],
                        relative_placement.Axis.DirectionRatios[2]])
                except AttributeError as ae:
                    self.logger.info(str(ae) +
                                     ' - DirectionRatios not existing, assuming'
                                     ' [1, 1, 1] as direction of element ',
                                     element)
                    x_direction = np.array([1, 0, 0])
                    z_direction = np.array([0, 0, 1])
                y_direction = np.cross(z_direction, x_direction)
                graph.add_node(element, type=ifc2python.getElementType(
                    element), oid=element.id())
                element_port_connections = element.HasPorts
                ports = {}
                for element_port_connection in element_port_connections:
                    element_coordinates = \
                        tuple(map(sum, zip(element.ObjectPlacement.
                                           RelativePlacement.Location
                                           .Coordinates,
                                           element.ObjectPlacement.
                                           PlacementRelTo.RelativePlacement.
                                           Location.Coordinates)))
                    port_coordinates =\
                        element_port_connection.RelatingPort.ObjectPlacement.\
                        RelativePlacement.Location.Coordinates
                    coordinate = []
                    for i in range(0, 3):
                        coordinate.append(
                            element_coordinates[i]
                            + x_direction[i] * port_coordinates[0]
                            + y_direction[i] * port_coordinates[1]
                            + z_direction[i] * port_coordinates[2])
                    ports[element_port_connection.RelatingPort] = {}
                    ports[element_port_connection.RelatingPort]['coordinate'] \
                        = coordinate
                    ports[element_port_connection.RelatingPort][
                        'flow_direction'] =  \
                        element_port_connection.RelatingPort.FlowDirection
                    parts[element] = ports
        graph = connect_elements_by_coordinates(graph=graph, parts=parts,
                                                threshold=0.5)
        self.hvac_graph = self.contract_network(graph)
        self.logger.debug("Number of nodes: %d", graph.number_of_nodes())

    def contract_network(self, graph):
        """
        This function creates all strands. Each strand starts with an
        element that has 3 or more ports. Each strandfinishes with an
        element that has 3 or more ports or with an IFCAIRTERMINAL. For
        each strand a list with the elements of the strand is created.
        """
        reducible_elements = ['IfcPipeSegment', 'IfcPipeFitting']
        nx.set_node_attributes(graph, [], 'contracted_nodes')
        reduced_nodes = 0
        for node in graph.nodes():
            nodes_nb = list(set(nx.all_neighbors(graph, node)) - set(
                graph.node[node]['contracted_nodes']) - {node})
            if len(nodes_nb) == 2 and ifc2python.getElementType(node) in \
                    reducible_elements:
                for node_nb in nodes_nb:
                    nodes_nb_nb = all_neighbors(graph, node)
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

    def tranfser_to_generel_description(self, graph):
        for node in graph.nodes():
            create_generic_objects(graph, node)
        for edge in graph.edges():
            connect_generic_objects()
        pass

    def draw_hvac_network(self, label='oid'):
        """
        Function to deliver a graphical output of the HVAC network.
        :param label: label to display at the nodes, default is ifc oid,
        can also be type
        :return:
        """
        labels = nx.get_node_attributes(self.hvac_graph, label)
        nx.draw(self.hvac_graph, labels=labels, node_size=3, font_size=10,
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

