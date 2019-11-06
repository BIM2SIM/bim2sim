""" This module holds a HVACSystem object which is -represented by a graph
network
where each node represents a hvac-component
"""

import os
import logging

import networkx as nx
from networkx.readwrite import json_graph
import matplotlib.pyplot as plt


class HvacGraph():
    """HVAC related graph manipulations"""

    def __init__(self, instances: list):
        self.logger = logging.getLogger(__name__)
        self.graph = self._create_hvac_network_by_ports(instances)

    def _create_hvac_network_by_ports(self, instances):
        """
        This function creates a graph network of the raw instances. Each
        component and each port of the instances is represented by a node.
        """
        self.logger.info("Creating HVAC graph representation ...")
        graph = nx.Graph()

        nodes = [port for instance in instances for port in
                 instance.ports]
        inner_edges = [connection for instance in instances
                       for connection in instance.get_inner_connections()]
        edges = [(port, port.connection) for port in nodes if port.connection]
        graph.update(nodes=nodes, edges=edges + inner_edges)

        self.logger.info("HVAC graph building is completed")
        return graph

    def _contract_ports_into_elements(self, graph, port_nodes):
        """
        Contract the port nodes into the belonging instance nodes for better
        handling, the information about the ports is still accessible via the
        get_contractions function.
        :return:
        """
        new_graph = graph.copy()
        self.logger.info("Contracting ports into elements ...")
        for port in port_nodes:
            new_graph = nx.contracted_nodes(new_graph, port.parent, port)
        self.logger.info("Contracted the ports into node instances, this"
                         " leads to %d nodes.",
                         new_graph.number_of_nodes())
        return graph

    @property
    def element_graph(self) -> nx.Graph:
        """View of graph with elements instead of ports"""
        graph = nx.Graph()
        nodes = {ele.parent for ele in self.graph.nodes if ele}
        edges = {(con[0].parent, con[1].parent) for con in self.graph.edges
                 if not con[0].parent is con[1].parent}
        graph.update(nodes=nodes, edges=edges)
        return graph

    @property
    def elements(self):
        """List of elements present in graph"""
        nodes = {ele.parent for ele in self.graph.nodes if ele}
        return list(nodes)

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
        base_cycles = nx.cycle_basis(self.graph)
        # for cycle in base_cycles:
        #     x = {port.parent for port in cycle}
        cycles = [cycle for cycle in base_cycles if len({port.parent for port in cycle}) > 1]
        self.logger.info("Found %d cycles", len(cycles))
        return cycles

    def get_type_chains(self, types, include_singles=False):
        """Returns lists of consecutive elements of the given types ordered as connected.

        :param types: iterable of ifcType names"""

        undirected_graph = nx.Graph(self.element_graph)
        nodes_degree2 = [v for v, d in undirected_graph.degree() if d ==
                         2 and v.ifc_type in types]
        subgraph_aggregations = nx.subgraph(undirected_graph, nodes_degree2)

        chain_lists = []
        # order elements as connected

        for component in nx.connected_components(subgraph_aggregations):
            subgraph = subgraph_aggregations.subgraph(component).copy()
        # for subgraph in nx.connected_component_subgraphs(subgraph_aggregations):  # marked as deprecated in nx 2.1
            end_nodes = [v for v, d in subgraph.degree() if d == 1]

            if len(end_nodes) != 2:
                if include_singles:
                    chain_lists.append(list(subgraph.nodes))
                continue
            elements = nx.shortest_path(subgraph, *end_nodes) # TODO more efficient
            chain_lists.append(elements)

        return chain_lists

    def merge(self, mapping: dict, inner_connections: list):
        """Merge port nodes in graph

        according to mapping dict port nodes are removed {port: None}
        or replaced {port: new_port} ceeping connections.

        WARNING: connections from removed port nodes are also removed

        :param mapping: replacement dict. ports as keys and replacement ports or None as values
        :param inner_connections: connections to add"""

        replace = {k: v for k, v in mapping.items() if not v is None}
        remove = [k for k, v in mapping.items() if v is None]

        nx.relabel_nodes(self.graph, replace, copy=False)
        self.graph.remove_nodes_from(remove)
        self.graph.add_edges_from(inner_connections)

    def get_connections(self):
        """Returns connections between different parent elements"""
        return [edge for edge in self.graph.edges
                if not edge[0].parent is edge[1].parent]

    def get_nodes(self):
        """Returns list of nodes represented by graph"""
        return list(self.graph.nodes)

    def plot(self, path=None, ports=False):
        """Plot graph

        if path is provided plot is saved as pdf else it gets displayed"""
        # https://plot.ly/python/network-graphs/
        colors = {
            1: 'green',
            0: 'blue',
            -1: 'red',
            None: 'yellow',
        }

        kwargs = {}
        if ports:
            graph = self.graph
            node_color_map = [colors[port.flow_side] for port in self.graph]
            kwargs['node_color'] = node_color_map
        else:
            # set connection colors based on flow_side
            graph = self.element_graph
            edge_color_map = []
            for edge in graph.edges:
                sides0 = {port.flow_side for port in edge[0].ports}
                sides1 = {port.flow_side for port in edge[1].ports}
                side = None
                # element with multiple sides is usually a consumer / generator (or result of conflicts)
                # hence side of definite element is used
                if len(sides0) == 1:
                    side = sides0.pop()
                elif len(sides1) == 1:
                    side = sides1.pop()
                edge_color_map.append(colors[side])
            kwargs['edge_color'] = edge_color_map

        nx.draw(graph, node_size=6, font_size=5, with_labels=True, **kwargs)
        plt.draw()
        if path:
            name = "%sgraph.pdf"%("port" if ports else "element")
            try:
                plt.savefig(
                    os.path.join(path, name),
                    bbox_inches='tight')
            except IOError as ex:
                self.logger.error("Unable to save plot of graph (%s)", ex)
        else:
            plt.show()
        plt.clf()

    def to_serializable(self):
        """Returns a json serializable object"""
        return json_graph.adjacency_data(self.graph)

    def from_serialized(self, data):
        """Sets grapg from serialized data"""
        self.graph = json_graph.adjacency_graph(data)

    def recurse_set_side(self, port, side, known: dict = None, raise_error=True):
        """Recursive set flow_side to connected ports"""
        if known is None:
            known = {}

        # set side suggestion
        is_known = port in known
        current_side = known.get(port, port.flow_side)
        if not is_known:
            known[port] = side
        elif is_known and current_side == side:
            return known
        else:
            # conflict
            if raise_error:
                raise AssertionError("Conflicting flow_side in %r" % port)
            else:
                self.logger.error("Conflicting flow_side in %r", port)
                known[port] = None
                return known

        # call neighbours
        for neigh in self.graph.neighbors(port):
            if (neigh.parent.is_consumer() or neigh.parent.is_generator()) and port.parent is neigh.parent:
                # switch flag over consumers / generators
                self.recurse_set_side(neigh, -side, known, raise_error)
            else:
                self.recurse_set_side(neigh, side, known, raise_error)

        return known

    def recurse_set_unknown_sides(self, port, visited: list = None, masters: list = None):
        """Recursive checks neighbours flow_side.
        :returns tuple of
            common flow_side (None if conflict)
            list of checked ports
            list of ports on which flow_side s are determined"""

        if visited is None:
            visited = []
        if masters is None:
            masters = []

        # mark as visited to prevent deadloops
        visited.append(port)

        if port.flow_side in (-1, 1):
            # use port with known flow_side as master
            masters.append(port)
            return port.flow_side, visited, masters

        # call neighbours
        neighbour_sides = {}
        for neigh in self.graph.neighbors(port):
            if neigh not in visited:
                if (neigh.parent.is_consumer() or neigh.parent.is_generator()) and port.parent is neigh.parent:
                    # switch flag over consumers / generators
                    side, _, _ = self.recurse_set_unknown_sides(neigh, visited, masters)
                    side = -side
                else:
                    side, _, _ = self.recurse_set_unknown_sides(neigh, visited, masters)
                neighbour_sides[neigh] = side
            # else:
            #     print(neigh, neigh.flow_side)

        sides = set(neighbour_sides.values())
        if not sides:
            return port.flow_side, visited, masters
        elif len(sides) == 1:
            # all neighbours have same site
            side = sides.pop()
            return side, visited, masters
        elif len(sides) == 2 and 0 in sides:
            side = (sides - {0}).pop()
            return side, visited, masters
        else:
            # conflict
            return None, visited, masters
