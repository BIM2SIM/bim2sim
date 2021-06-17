""" This module holds a HVACSystem object which is -represented by a graph
network
where each node represents a hvac-component
"""

import os
import logging
import itertools
from typing import Set, Iterable, Type

import networkx as nx
from networkx.readwrite import json_graph

from bim2sim.kernel.element import ProductBased

logger = logging.getLogger(__name__)


class HvacGraph(nx.Graph):
    """HVAC related graph manipulations based on ports."""

    def __init__(self, elements=None, **attr):
        super().__init__(incoming_graph_data=None, **attr)
        if elements:
            self._update_from_elements(elements)

    def _update_from_elements(self, instances):
        """
        Update graph based on ports of elements.
        """

        nodes = [port for instance in instances for port in instance.ports
                 if port.connection]
        inner_edges = [connection for instance in instances
                       for connection in instance.inner_connections]
        edges = [(port, port.connection) for port in nodes if port.connection]

        self.update(nodes=nodes, edges=edges + inner_edges)

    @staticmethod
    def _contract_ports_into_elements(graph, port_nodes):
        """
        Contract the port nodes into the belonging instance nodes for better
        handling, the information about the ports is still accessible via the
        get_contractions function.
        :return:
        """
        new_graph = graph.copy()
        logger.info("Contracting ports into elements ...")
        for port in port_nodes:
            new_graph = nx.contracted_nodes(new_graph, port.parent, port)
        logger.info("Contracted the ports into node instances, this"
                    " leads to %d nodes.",
                    new_graph.number_of_nodes())
        return graph

    @property
    def element_graph(self) -> nx.Graph:
        """View of graph with elements instead of ports"""
        graph = nx.Graph()
        nodes = {ele.parent for ele in self.nodes if ele}
        edges = {(con[0].parent, con[1].parent) for con in self.edges
                 if not con[0].parent is con[1].parent}
        graph.update(nodes=nodes, edges=edges)
        return graph

    @property
    def elements(self):
        """List of elements present in graph"""
        nodes = {ele.parent for ele in self.nodes if ele}
        return list(nodes)

    @staticmethod
    def get_not_contracted_neighbors(graph, node):
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
        node = self.nodes[node]
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
        logger.info("Searching for cycles in hvac network ...")
        base_cycles = nx.cycle_basis(self)
        # for cycle in base_cycles:
        #     x = {port.parent for port in cycle}
        cycles = [cycle for cycle in base_cycles if len({port.parent for port in cycle}) > 1]
        logger.info("Found %d cycles", len(cycles))
        return cycles

    @staticmethod
    def get_type_chains(
            element_graph: nx.Graph,
            types: Iterable[Type[ProductBased]],
            include_singles=False):
        """Returns lists of consecutive elements of the given types ordered as connected.

        :param include_singles:
        :param element_graph: graph object with elements as nodes
        :param types: items the chains are built of"""

        undirected_graph = element_graph
        nodes_degree2 = [v for v, d in undirected_graph.degree() if 1 <= d <= 2
                         and type(v) in types]
        subgraph_aggregations = nx.subgraph(undirected_graph, nodes_degree2)

        chain_lists = []
        # order elements as connected

        for component in nx.connected_components(subgraph_aggregations):
            subgraph = subgraph_aggregations.subgraph(component).copy()
            end_nodes = [v for v, d in subgraph.degree() if d == 1]

            if len(end_nodes) != 2:
                if include_singles:
                    chain_lists.append(list(subgraph.nodes))
                continue
            elements = nx.shortest_path(subgraph, *end_nodes)  # TODO more efficient
            chain_lists.append(elements)

        return chain_lists

    def merge(self, mapping: dict, inner_connections: list,
              add_connections=None):
        """Merge port nodes in graph

        according to mapping dict port nodes are removed {port: None}
        or replaced {port: new_port} ceeping connections.
        adds also inner connections to graph and if passed additional
        connections.

        WARNING: connections from removed port nodes are also removed

        :param add_connections: additional connections to add
        :param mapping: replacement dict. ports as keys and replacement ports
        or None as values
        :param inner_connections: connections to add"""

        replace = {k: v for k, v in mapping.items() if not v is None}
        remove = [k for k, v in mapping.items() if v is None]

        nx.relabel_nodes(self, replace, copy=False)
        self.remove_nodes_from(remove)
        self.add_edges_from(inner_connections)
        if add_connections:
            self.add_edges_from(add_connections)

    def get_connections(self):
        """Returns connections between different parent elements"""
        return [edge for edge in self.edges
                if not edge[0].parent is edge[1].parent]

    # def get_nodes(self):
    #     """Returns list of nodes represented by graph"""
    #     return list(self.nodes)

    def plot(self, path=None, ports=False):
        """Plot graph

        if path is provided plot is saved as pdf else it gets displayed"""
        # importing matplotlib is slow and plotting is optional
        import matplotlib.pyplot as plt

        # https://plot.ly/python/network-graphs/
        colors = {
            1: 'green',
            0: 'blue',
            -1: 'red',
            None: 'yellow',
        }

        kwargs = {}
        if ports:
            graph = self
            node_color_map = [colors[port.flow_side] for port in self]
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
                logger.error("Unable to save plot of graph (%s)", ex)
        else:
            plt.show()
        plt.clf()

    def to_serializable(self):
        """Returns a json serializable object"""
        return json_graph.adjacency_data(self)

    @classmethod
    def from_serialized(cls, data):
        """Sets grapg from serialized data"""
        return cls(json_graph.adjacency_graph(data))

    @staticmethod
    def remove_not_wanted_nodes(
            graph,
            wanted: Set[Type[ProductBased]],
            inert: Set[Type[ProductBased]] = None):
        """ removes not wanted and not inert nodes from the given graph."""
        if inert is None:
            inert = set()
        if not all(map(lambda item: issubclass(item, ProductBased), wanted | inert)):
            raise AssertionError("Invalid type")
        _graph = graph.copy()
        # remove blocking nodes
        remove = {node for node in _graph.nodes
                  if type(node) not in wanted | inert}
        _graph.remove_nodes_from(remove)
        return _graph

    @staticmethod
    def get_parallels(
            graph,
            wanted: Set[Type[ProductBased]],
            inert: Set[Type[ProductBased]] = None,
            grouping=None, grp_threshold=None):
        """ Detect parallel occurrences of wanted items.
        All graph nodes not in inert or wanted are counted as blocking.
        Grouping can hold additional arguments like only same size.

        :grouping: dict with parameter to be grouped and condition. e.g. (
        rated_power: equal)
        :grp_threshold: float for minimum group size
        :returns: list of none overlapping subgraphs
        """
        if inert is None:
            inert = set()
        if grouping is None:
            grouping = {}
        _graph = HvacGraph.remove_not_wanted_nodes(graph, wanted, inert)

        # detect simple cycles with at least two wanted nodes
        basis_cycles = nx.cycle_basis(_graph)

        # remove bypasses which prevent correct finding of parallel pump cycles
        graph_changed = False
        for basis_cycle in basis_cycles:
            wanted_guids_cycle = {node.guid for node in
                                  basis_cycle if type(node) in wanted}

            if len(wanted_guids_cycle) < 2:
                edge_elements = [
                    node for node in basis_cycle if len(node.ports) > 2]

                # get direct connections between the edges
                subgraph = _graph.subgraph(basis_cycle)
                dir_connections = HvacGraph.get_dir_paths_between(
                    subgraph, edge_elements)

                # remove strands without wanted items
                for dir_connection in dir_connections:
                    if not any(type(node) is want for want in wanted
                               for node in dir_connection):
                        _graph.remove_nodes_from(
                            [node for node in dir_connection])
                        graph_changed = True
        # get cycles again if graph changed
        if graph_changed:
            basis_cycles = nx.cycle_basis(_graph)

        basis_cycle_sets = [frozenset((node.guid for node in basis_cycle)) for basis_cycle in basis_cycles]  # hashable
        wanted_guids = {node.guid for node in _graph.nodes if type(node) in wanted}

        occurrence_cycles = {}
        cycle_occurrences = {}
        for cycle in basis_cycle_sets:
            wanteds = frozenset(guid_node for guid_node in cycle if guid_node in wanted_guids)
            if len(wanteds) > 1:
                cycle_occurrences[cycle] = wanteds
                for item in wanteds:
                    occurrence_cycles.setdefault(item, []).append(cycle)

        # detect connected cycles
        def related_cycles(item, known):
            sub_cycles = occurrence_cycles[item]
            for cycle in sub_cycles:
                if cycle not in known:
                    known.append(cycle)
                    sub_items = cycle_occurrences[cycle]
                    for sub_item in sub_items:
                        related_cycles(sub_item, known)

        cycle_sets = []
        known_items = set()
        for item in occurrence_cycles:
            if item not in known_items:
                known = []
                related_cycles(item, known)
                cycle_sets.append(known)
                known_items = known_items | {oc for k in known for oc in cycle_occurrences[k]}

        def group_parallels(graph, group_attr, cond, threshold=None):
            """ group a graph of parallel items by conditions. Currently only
            equal grouping is implemented, which will return only parallel
            items with equal group_attr. If a threshold is given, only groups
            with number of elements > this threshold value will be included in
            result.
            """
            if cond != 'equal':
                raise NotImplementedError()

            graphs = []
            nodes = [node for node in graph.nodes if type(node) in
                     wanted]

            # group elements by group_attr
            grouped = {}
            for node in nodes:
                grouped.setdefault(getattr(node, group_attr), []).append(node)

            # check if more than one grouped element exist
            if len(grouped.keys()) == 1:
                graphs.append(graph)
                return graphs

            for parallel_eles in grouped.values():
                # only groups > threshold will be included in result
                if len(parallel_eles) <= threshold:
                    continue
                else:
                    subgraph_nodes = []

                    for parallel_ele in parallel_eles:
                        # get strands with the wanted items
                        strand = HvacGraph.get_path_without_junctions(
                            graph, parallel_ele, True)
                        for node in strand:
                            subgraph_nodes.append(node)
                    graphs.append(graph.subgraph(subgraph_nodes))
            return graphs

        # merge cycles to get multi parallel items
        node_dict = {node.guid: node for node in _graph.nodes}
        graphs = []
        for cycle_set in cycle_sets:
            nodes = [node_dict[guid] for guids in cycle_set for guid in guids]
            _graph = graph.subgraph(nodes)
            # apply filter if used
            if grouping:
                for group_attr, cond in grouping.items():
                    _graphs = group_parallels(_graph, group_attr, cond,
                                              grp_threshold)
                    # filtering might return multiple graphs
                    for _graph in _graphs:
                        graphs.append(_graph)
            else:
                graphs.append(_graph)
        return graphs

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
                logger.error("Conflicting flow_side in %r", port)
                known[port] = None
                return known

        # call neighbours
        for neigh in self.neighbors(port):
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
        for neigh in self.neighbors(port):
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

    @staticmethod
    def get_dir_paths_between(graph, nodes, include_edges=False):
        """ get direct connection between list of nodes in a graph."""
        dir_connections = []

        for node1, node2 in itertools.combinations(nodes, 2):
            all_paths = list(nx.all_simple_paths(graph, node1, node2))

            for path in all_paths:
                if not any(len(ele.ports) > 2 for ele in path[1:-1]):

                    if len(path) > 2:
                        # remove edge items if not wanted
                        if not include_edges:
                            path.pop(0)
                            path.pop(-1)
                        dir_connections.append(path)
                    elif len(path) == 2 and include_edges:
                        dir_connections.append(path)
        return dir_connections

    @staticmethod
    def get_path_without_junctions(graph, root, include_edges=False):
        """Get not orientated list of nodes for paths that includes the
        defined root element. The edges areany junction elements.
        These edges are not included by default.
        Return all nodes in thisde path.
        # todo make this correct!
        :graph =
        :root = element which must be in path
        :include_edges = include edges of path or not"""

        # def create_subgraph(graph, sub_G, start_node):
        #     sub_G.add_node(start_node)
        #     for n in graph.neighbors_iter(start_node):
        #         if n not in sub_G.neighbors(start_node):
        #
        #             sub_G.add_path([start_node, n])
        #             create_subgraph(G, sub_G, n)

        nodes = [root]
        # get direct neighbors
        neighbors_root = nx.all_neighbors(graph, root)
        if not neighbors_root:
            return nodes
        # loop through neighbors until next junction
        for neighbor in neighbors_root:
            while True:
                neighbors = [neighbor for neighbor in
                             nx.all_neighbors(graph, neighbor) if not
                             neighbor in nodes]
                if not neighbors:
                    break
                if len(neighbors) > 1:
                    if include_edges:
                        nodes.append(neighbor)
                    break
                else:
                    nodes.append(neighbor)
                    neighbor = neighbors[0]
        return nodes

    @staticmethod
    def get_connections_between(
            graph,
            wanted: Set[Type[ProductBased]],
            inert: Set[Type[ProductBased]] = set()):
        """Detect simple connections between wanted items.
        All graph nodes not in inert or wanted are counted as blocking
        :returns: list of none overlapping subgraphs
        """
        if not all(map(lambda item: issubclass(item, ProductBased), wanted | inert)):
            raise AssertionError("Invalid type")
        _graph = HvacGraph.remove_not_wanted_nodes(graph, wanted, inert)

        # get connections between the wanted items
        wanted_nodes = {node for node in _graph.nodes
                        if type(node) in wanted}

        cons = HvacGraph.get_dir_paths_between(_graph, wanted_nodes, True)
        graphs = []
        for con in cons:
            subgraph = nx.subgraph(_graph, con)
            graphs.append(subgraph)
        return graphs
