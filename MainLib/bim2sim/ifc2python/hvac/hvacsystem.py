""" This module holds a HVACSystem object which is represented by a graph
network
where each node represents a hvac-component
"""

import networkx as nx
from os.path import dirname
import os
import numpy as np
import ifcopenshell
import matplotlib.pyplot as plt
from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python.hvac.hvac_specific_functions import \
    create_object_from_ifc
from bim2sim.ifc2python.hvac.logic.pipestrand import PipeStrand

# todo: get ifc file from top function bim2sim
IfcFile = ifcopenshell.open(
    dirname(dirname(dirname(dirname(dirname((__file__)))))) +
    '/ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc')


class HVACSystem(object):
    def __init__(self):
        self.hvac_graph = None
        self.create_hvac_network()
        self.hvac_graph = self.reduce_strangs()
        self.draw_hvac_network()

    def create_hvac_network(self,
                            element_types=None):
        """
        This function defines the hvac as graph network, each element is
        represented by a node. The nodes are connected by the geometrical
        positions of their ports.
        """

        if element_types is None:
            element_types = ['IfcSpaceHeater',
                             'IfcPipeFitting',
                             'IfcPipeSegment',
                             'IfcTank',
                             'IfcBoiler',
                             'IfcUnitaryEquipment']
        DG = nx.DiGraph()
        parts = {}
        # all absolute coordinates of the ports are calculated and saved
        # in the parts dict
        for element_type in element_types:
            elements = IfcFile.by_type(element_type)
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
                DG.add_node(element,
                            type=ifc2python.getElementType(element),
                            oid=element.id())
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
        threshold = 1
        for element1, ports1 in parts.items():
            for port1 in ports1.values():
                for element2, ports2 in parts.items():
                    for port2 in ports2.values():
                        if element1 == element2:
                            continue
                        if abs(port1['coordinate'][0] - port2['coordinate'][
                            0]) <= threshold and abs(port1['coordinate'][1] -
                                                     port2['coordinate'][1]) \
                                <= threshold and abs(port1['coordinate'][2] -
                                                     port2['coordinate'][2]) \
                                <= threshold:
                            if port1['flow_direction'] == 'SOURCE' and  \
                                    port2['flow_direction'] == 'SINK':
                                DG.add_edge(element1, element2)
                            elif port1['flow_direction'] == 'SINK' and  \
                                    port2['flow_direction'] == 'SOURCE':
                                DG.add_edge(element2, element1)
                            elif port1['flow_direction'] == 'SOURCEANDSINK' or \
                                    port2[
                                        'flow_direction'] == 'SOURCEANDSINK':
                                DG.add_edge(element1, element2)
                                DG.add_edge(element2, element1)
        self.hvac_graph = DG

    def reduce_strangs(self):
        """""
          This function creates all strands. Each strand starts with an element that has 3 or more ports. Each strand
          finishes with an element that has 3 or more ports or with an IFCAIRTERMINAL. For each strand a list with the 
          elements of the strand is created. 
          """""
        G = self.hvac_graph
        reducablle_elements = ['IfcPipeSegment', 'IfcPipeFitting']
        nx.set_node_attributes(G, [], 'contracted_nodes')

        reduced_nodes = 0
        for node in G.nodes():
            nodes_nb = list(set(nx.all_neighbors(G, node)) - set(
                G.node[node]['contracted_nodes']) - {node})
            if len(nodes_nb) == 2 and ifc2python.getElementType(node) in \
                    reducablle_elements:
                for node_nb in nodes_nb:
                    nodes_nb_nb = list(set(nx.all_neighbors(G, node_nb)) - set(
                        G.node[node_nb]['contracted_nodes']) - {node_nb})
                    if len(nodes_nb_nb) <= 2 and ifc2python.getElementType(
                            node_nb) in \
                            reducablle_elements:
                        G.node[node_nb]['contracted_nodes'] = G.node[node_nb][
                                                                  'contracted_nodes'] \
                                                              + [node]
                        G = nx.contracted_nodes(G, node_nb,
                                                node)  # merge node into
                        reduced_nodes += 1
                        break
        print('reduced nodes:' + str(reduced_nodes))
        return G

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
    test = HVACSystem()