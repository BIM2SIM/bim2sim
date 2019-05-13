""" This module holds a HVACSystem object which is -represented by a graph
network
where each node represents a hvac-component
"""

import os
import logging

import networkx as nx
import matplotlib.pyplot as plt


class HvacGraph():

    def __init__(self, instances:list):
        self.logger = logging.getLogger(__name__)
        self.graph = self._create_hvac_network_by_ports(instances)

    def _create_hvac_network_by_ports(self, instances):
        """
        This function creates a graph network of the raw instances. Each
        component and each port of the instances is represented by a node.
        """
        self.logger.info("Creating HVAC graph representation ...")
        graph = nx.DiGraph()

        port_nodes = [port for instance in instances for port in
                       instance.ports]
        edges = [(port, connected_port) for port in port_nodes for
                      connected_port in port.connections]
        nodes = instances + port_nodes
        graph.update(nodes=nodes, edges=edges)

        hvac_graph = self._contract_ports_into_elements(graph, port_nodes)
        self.logger.info("HVAC graph building is completed")
        return hvac_graph

    def _contract_ports_into_elements(self, graph, port_nodes):
        """
        Contract the port nodes into the belonging instance nodes for better
        handling, the information about the ports is still accessible via the
        get_contractions function.
        :return:
        """

        self.logger.info("Contracting ports into elements ...")
        for port in port_nodes:
            graph = nx.contracted_nodes(graph, port.parent, port)
        self.logger.info("Contracted the ports into node instances, this"
                         " leads to %d nodes.",
                         graph.number_of_nodes())
        return graph

    def get_not_contracted_neighbors(self, graph, node):
        neighbors = list(
            set(nx.all_neighbors(graph, node)) -
            set(graph.node[node]['contracted_nodes']) -
            {node}
        )
        return neighbors

    def get_contractions(self, node):
        """
        Returns a list of contracted nodes for the passed node.
        :param node: node in whose connections you are interested
        :return:
        """
        node = self.graph.node[node]
        inner_nodes = []
        if 'contraction' in node:
            for contraction in node['contraction'].keys():
                inner_nodes.append(contraction)
        return inner_nodes

    def get_cycles(self):
        """
        Find cycles in the graph.
        :return cycles:
        """
        self.logger.info("Searching for cycles in hvac network ...")
        undirected_graph = nx.Graph(self.graph)
        cycles = nx.cycle_basis(undirected_graph)
        self.logger.info("Found %d cycles", len(cycles))
        return cycles

    def get_type_chains(self, types):
        """Returns lists of consecutive elements of the given types ordered as connected.
        
        :param types: iterable of ifcType names"""

        undirected_graph = nx.Graph(self.graph)
        nodes_degree2 = [v for v, d in undirected_graph.degree() if d ==
                            2 and v.ifc_type in types]
        subgraph_aggregations = nx.subgraph(undirected_graph, nodes_degree2)

        chain_lists = []
        # order elements as connected
        for subgraph in nx.connected_component_subgraphs(subgraph_aggregations):
            end_nodes = [v for v, d in subgraph.degree() if d == 1]
            if len(end_nodes) != 2:
                continue
            elements = nx.shortest_path(subgraph, *end_nodes) # TODO more efficient
            chain_lists.append(elements)

        return chain_lists

    def replace(self, elements, replacement=None):
        """Replaces elements in graph with replaement. If replacement is not given elements are deleted.

        Updates the network by:
            - deleting old nodes which are now represented by the aggregation
            - connecting the aggregation to the rest of the network
        :param elements:
        :param replacement:
        :return graph:
        """

        if replacement:
            self.graph.add_node(replacement)
    
            outer_connections = [connection for port in replacement.ports
                for connection in port.connections]

            for port in outer_connections:
                other_port = port.connections[0]
                node = self.graph.node[port.parent]
                del node['contraction'][port]
                self.graph.add_edge(port, other_port)
                self.graph = nx.contracted_nodes(self.graph, port.parent, port)
                self.graph = nx.contracted_nodes(self.graph, replacement, other_port)

        for element in elements:
            self.graph.remove_node(element)

        return self.graph

    def get_nodes(self):
        """Returns list of nodes represented by graph"""
        return list(self.graph.nodes)

    def plot(self, path=None):
        """Plot graph
        
        if path is provided plot is saved as pdf else it gets displayed"""
        nx.draw(self.graph, node_size=3, font_size=6,
                with_labels=True)
        plt.draw()
        if path:
            plt.savefig(
                os.path.join(path, 'graphnetwork.pdf'),
                bbox_inches='tight')
        else:
            plt.show()

