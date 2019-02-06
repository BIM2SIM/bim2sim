""" This module holds a HVACSystem object which is represented by a graph
network
where each node represents a hvac-component
"""
from os.path import dirname
import logging
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python.hvac.hvac_objects import Boiler, SpaceHeater, \
    StorageDevice, Pipe, Valve, PipeFitting #,GenericDevice, EnergyConversionDevice, \


class HVACSystem(object):
    def __init__(self, model):
        self.logger = logging.getLogger(__name__)
        self.hvac_objects = []
        self.ifc = model
        self.hvac_graph = None
        self.create_hvac_network()
        # self.transfer_to_generel_description(graph=self.hvac_graph)
        # self.draw_hvac_network(label='type')


    def create_hvac_network(self, element_types=None):
        """
        This function defines the hvac system as graph network. Each element is
        represented by a node. The nodes are connected by the geometrical
        positions of their ports.
        """
        self.logger.info("Creating HVAC network")

        if element_types is None:
            element_types = ['IfcAirTerminal', 'IfcAirTerminalBox', 'IfcAirToAirHeatRecovery', 'IfcBoiler', 'IfcBurner',
                             'IfcChiller', 'IfcCoil', 'IfcCompressor', 'IfcCondenser', 'IfcCooledBeam',
                             'IfcCoolingTower', 'IfcDamper', 'IfcDuctFitting', 'IfcDuctSegment', 'IfcDuctSilencer',
                             'IfcEngine', 'IfcEvaporativeCooler', 'IfcEvaporator', 'IfcFan', 'IfcFilter',
                             'IfcFlowMeter', 'IfcHeatExchanger', 'IfcHumidifier', 'IfcMedicalDevice', 'IfcPipeFitting',
                             'IfcPipeSegment', 'IfcPump', 'IfcSpaceHeater', 'IfcTank', 'IfcTubeBundle',
                             'IfcUnitaryEquipment', 'IfcValve', 'IfcVibrationIsolator']

        # graph = nx.DiGraph()

        for element_type in element_types:
            elements = self.ifc.by_type(element_type)
            for element in elements:
                if element_type == "IfcBoiler":
                # todo extend, at the moment just short example for boiler,
                    instance = Boiler(ifc=element)
                    instance.position
        # self.hvac_graph = self.contract_network(graph)
        # todo add logger msg how many nodes have been contracted
        # self.logger.debug("Number of nodes: %d", graph.number_of_nodes())

    def contract_network(self, graph):
        """
        This function reduces the network by searching for reducable elements.
        As an example all successive pipes will be reduced into one pipe.
        """
        reducible_elements = ['IfcPipeSegment', 'IfcPipeFitting']
        nx.set_node_attributes(graph, [], 'contracted_nodes')
        nx.set_node_attributes(graph, str, 'belonging_object')
        reduced_nodes = 0
        for node in graph.nodes():
            node_nbs = self.all_neighbors(graph, node)
            if len(node_nbs) == 2 and ifc2python.getElementType(node) in \
                    reducible_elements:
                for node_nb in node_nbs:
                    node_nb_nbs = self.all_neighbors(graph, node_nb)
                    if len(node_nb_nbs) <= 2 and ifc2python.getElementType(
                            node_nb) in \
                            reducible_elements:
                        graph.node[node_nb]['contracted_nodes'] = \
                            graph.node[node_nb]['contracted_nodes'] + [node]
                        graph = nx.contracted_nodes(graph, node_nb, node)
                        reduced_nodes += 1
                        break
        self.logger.debug("Number of nodes: %d", reduced_nodes)
        return graph

    def transfer_to_generel_description(self, graph):
        for node in graph.nodes():
            self.create_generic_objects(graph, node)
        for node in graph.nodes():
            self.connect_generic_objects(graph, node)
        pass

    def connect_generic_objects(self, graph, node):
        instance = graph.node[node]['belonging_object']
        instance.get_port_connections(graph, node)

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

    def create_generic_objects(self, graph, node):
        """
        Creating an hvac_object by the corresponding ifc_element and add the
        instance of the object to the networkx node.
        :param node:
        :return: object of class corresponding to the ifc_element
        """

        object_type = ifc2python.getElementType(node)
        if object_type == "IfcBoiler":
            instance = Boiler(graph=graph,
                              IfcGUID=self.get_all_neighbor_GUIDS(graph=graph,
                                                                  node=node),
                              ifcfile=self.ifc)
        elif object_type == "IfcTank":
            instance = StorageDevice(graph=graph,
                                     IfcGUID=self.get_all_neighbor_GUIDS(
                                         graph=graph, node=node),
                                     ifcfile=self.ifc)
        elif object_type == "IfcSpaceHeater":
            instance = SpaceHeater(graph=graph,
                                   IfcGUID=self.get_all_neighbor_GUIDS(
                                       graph=graph, node=node),
                                   ifcfile=self.ifc)
        elif object_type == "IfcPipeSegment":
            instance = Pipe(graph=graph,
                                   IfcGUID=self.get_all_neighbor_GUIDS(
                                       graph=graph, node=node),
                                   ifcfile=self.ifc)
        elif object_type == "IfcPipeFitting":
            if len(self.all_neighbors(graph, node)) > 2:
                instance = Valve(graph=graph,
                                   IfcGUID=self.get_all_neighbor_GUIDS(
                                       graph=graph, node=node),
                                   ifcfile=self.ifc)
            else:
                instance = PipeFitting(graph=graph,
                                   IfcGUID=self.get_all_neighbor_GUIDS(
                                       graph=graph, node=node),
                                   ifcfile=self.ifc)
        elif object_type == "IfcUnitaryEquipment":
            instance = EnergyConversionDevice(graph=graph,
                                   IfcGUID=self.get_all_neighbor_GUIDS(
                                       graph=graph, node=node),
                                   ifcfile=self.ifc)
        else:
            instance = GenericDevice(graph=graph,
                                   IfcGUID=self.get_all_neighbor_GUIDS(
                                       graph=graph, node=node),
                                   ifcfile=self.ifc)
        graph.node[node]['belonging_object'] = instance
        self.hvac_objects.append(instance)
        return instance

    def all_neighbors(self, graph, node):
        neighbors = list(
            set(nx.all_neighbors(graph, node)) -
            set(graph.node[node]['contracted_nodes']) - {node}
        )
        return neighbors

    def get_all_neighbor_GUIDS(self, graph, node):
        guids = [ifc2python.getGUID(node)] + list(map(ifc2python.getGUID,
                                                      graph.node[node][
                                                      'contracted_nodes']))
        return guids

    def connect_elements_by_coordinates(self, graph, parts, threshold):
        """
        Connects the ifc elements of the parts dict to each other by taking the
        geometrical position of the ports into account. The threshold value
        determines how far apart the ports may be from each other so that a
        connection is still established.

        Parameters
        ----------


        graph : Graph object from networkx
            Graph that displays the hvac network
        parts : dict
            Dictionary holding all ifc elements of the hvac network
        threshold : float
            Value to specify how far apart the ports may be from each other so that
            a connection is still established.
        """
        for element1, ports1 in parts.items():
            for port1 in ports1.values():
                for element2, ports2 in parts.items():
                    for port2 in ports2.values():
                        if element1 == element2:
                            continue

                        distance = list((abs(coord1 - coord2)
                                         for (coord1, coord2)
                                         in zip(port1['coordinate'],
                                                port2['coordinate'])))
                        if all(diff <= threshold for diff in distance):
                            if port1['flow_direction'] == 'SOURCE' and \
                                    port2['flow_direction'] == 'SINK':
                                graph.add_edge(element1, element2)
                            elif port1['flow_direction'] == 'SINK' and \
                                    port2['flow_direction'] == 'SOURCE':
                                graph.add_edge(element2, element1)
                            elif port1['flow_direction'] == 'SOURCEANDSINK' or \
                                    port2['flow_direction'] == 'SOURCEANDSINK':
                                graph.add_edge(element1, element2)
                                graph.add_edge(element2, element1)
                            else:
                                continue
        return graph

if __name__ == '__main__':
    import ifcopenshell
    IfcFile = ifcopenshell.open(
        dirname(dirname(dirname(dirname(dirname((__file__)))))) +
        '/ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements'
        '.ifc')
    Test = HVACSystem(IfcFile)

