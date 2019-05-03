""" This module holds a HVACSystem object which is -represented by a graph
network
where each node represents a hvac-component
"""

import logging
import networkx as nx
import matplotlib.pyplot as plt

class HvacGraph(object):
    def __init__(self, instances, parent):
        self.logger = logging.getLogger(__name__)
        self.instances = instances
        self.parent = parent
        self.hvac_graph = None
        self._create_hvac_network()
        self.cycles = []

    def _create_hvac_network(self):
        """
        This function creates a graph network of the raw instances. Each
        component and each port of this component is represented by a node.
        """
        self.logger.info("Creating HVAC graph representation ...")
        graph = nx.DiGraph()
        for instance in self.instances.values():
            if not graph.has_node(instance):
                graph.add_node(instance, label=instance.name)
            for port in instance.ports:
                graph.add_node(port)
                for connected_port in port.connections:
                    if not graph.has_node(connected_port):
                        graph.add_node(connected_port)
                        graph.add_edge(port, connected_port)
        self.hvac_graph = graph
        self.logger.info("Created %d nodes", graph.number_of_nodes())
        self._contract_ports_into_elements()

    def _contract_ports_into_elements(self):
        """
        Contract the port nodes into the belonging instance nodes for better
        handling, the information about the ports is still accessible via the
        get_contractions function.
        :return:
        """
        counter = 0
        self.logger.info("Contracting ports into elements ...")
        for instance in self.instances.values():
            for port in instance.ports:
                counter += 1
                self.hvac_graph = nx.contracted_nodes(self.hvac_graph,
                                                      instance, port)
        self.logger.info("Contracted %d ports into node instances, this"
                         " leads to %d nodes.",
                         counter, self.hvac_graph.number_of_nodes())

    def create_cycles(self):
        """
        Find cycles in the graph.
        :return:
        """
        self.logger.info("Searching for cycles in hvac network ...")
        undirected_graph = nx.Graph(self.hvac_graph)
        cycles = nx.cycle_basis(undirected_graph)
        self.cycles = cycles
        self.logger.info("Found %d cycles", len(self.cycles))

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

    def plot_graph(self):
        nx.draw(self.hvac_graph, node_size=3, font_size=6,
                with_labels=True)
        plt.draw()
        plt.show()