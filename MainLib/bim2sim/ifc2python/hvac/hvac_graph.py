""" This module holds a HVACSystem object which is -represented by a graph
network
where each node represents a hvac-component
"""

import logging
import networkx as nx
import matplotlib.pyplot as plt
from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python.aggregation import PipeStrand


class HvacGraph(object):
    def __init__(self, parent):
        self.logger = logging.getLogger(__name__)
        self.parent = parent
        self.hvac_graph = self._create_complete_hvac_network()
        self._contract_ports_into_elements()
        # self.contract_network()
        # self.find_cicyles()

        # self.draw_hvac_network(label='type')

    def _create_complete_hvac_network(self):
        """
        This function creates a graph network of the raw instances . Each
        ports is represented by a node, components are turned into contracted
        nodes, e.g. for a pipe the two nodes are created and turned into an
        aggregated node.
        """
        self.logger.info("Creating HVAC graph representation")
        graph = nx.DiGraph()
        for instance in self.parent.raw_instances.values():
            if not graph.has_node(instance):
                graph.add_node(instance, label=instance.name)
            for port in instance.ports:
                graph.add_node(port)
                for connected_port in port.connections:
                    if not graph.has_node(connected_port):
                        graph.add_node(connected_port)
                        graph.add_edge(port, connected_port)
        self.logger.info("Created %d nodes", graph.number_of_nodes())
        return graph

    def _contract_ports_into_elements(self):
        """
        Contract the port nodes into instance nodes for better handling.
        :return:
        """
        counter = 0
        self.logger.info("Contracting ports into elements ...")
        for instance in self.parent.raw_instances.values():
            for port in instance.ports:
                counter += 1
                self.hvac_graph = nx.contracted_nodes(self.hvac_graph,
                                                      instance, port)
        self.logger.info("Contracted %d ports into node instances, this"
                         " leads to %d nodes.",
                         counter, self.hvac_graph.number_of_nodes())

    def find_cicyles(self):
        """
        Find cycles in the graph.
        :return:
        """
        undirected_graph = nx.Graph(self.hvac_graph)
        cycles = nx.cycle_basis(undirected_graph)
        return cycles

    def get_contractions(self, node):
        """
        Returns a list of contracted nodes for the passed node.
        :param node:
        :return:
        """
        node = self.hvac_graph.node[node]
        inner_nodes = []
        for contraction in node['contraction'].keys():
            inner_nodes.append(contraction)
        return inner_nodes

    def contract_network(self):
        """
        This function reduces the network by searching for reducable elements.
        As an example all successive pipes will be reduced into one pipe.
        """
        graph = self.hvac_graph
        reducible_elements = ['IfcPipeSegment', 'IfcPipeFitting']
        # todo: maybe add reducible flag to elements to be able to check
        #  against this instead of a fixed list
        self.logger.info("Reducing the network by contracting pipes into "
                         "pipestrands ...")
        nx.set_node_attributes(graph, [], 'contracted_nodes')
        reduced_nodes = 0

        for node in graph.nodes():
            node_nbs = self.all_neighbors_without_contractions(graph, node)
            if len(node_nbs) == 2 and node.ifc_type in \
                    reducible_elements:
                for node_nb in node_nbs:
                    node_nb_nbs = self.all_neighbors_without_contractions(
                        graph, node_nb)
                    if len(node_nb_nbs) <= 2 and node.ifc_type in \
                            reducible_elements:
                        # todo integrate contraction not with dict entrys
                        graph.node[node_nb]['contracted_nodes'] = \
                            graph.node[node_nb]['contracted_nodes'] + \
                            graph.node[node]['contracted_nodes'] + \
                            [node]
                        graph = nx.contracted_nodes(graph, node_nb, node)
                        reduced_nodes += 1
                        break
        self.logger.debug("Reduced %d nodes by contracting, %d nodes left.",
                          reduced_nodes, graph.number_of_nodes())

        # for node in graph.nodes():
        #     if node.ifc_type in reducible_elements:
        #         PS = PipeStrand()
        #         PS.pipes = graph.node[node]['contracted_nodes']

        self.hvac_graph = graph



    def all_neighbors_without_contractions(self, graph, node):
        neighbors = list(
            set(nx.all_neighbors(graph, node)) -
            set(graph.node[node]['contracted_nodes']) -
            {node}
        )
        return neighbors



    def plot_graph(self):
        nx.draw(self.hvac_graph, node_size=3, font_size=10,
                with_labels=True)
        plt.draw()
        plt.show()