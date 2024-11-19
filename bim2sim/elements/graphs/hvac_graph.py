""" This module represents the elements of a HVAC system in form of a network
graph where each node represents a hvac-component.
"""
from __future__ import annotations

import itertools
import logging
import os
import shutil
from pathlib import Path
from typing import Set, Iterable, Type, List, Union
import json

import networkx as nx
from networkx import json_graph

from bim2sim.elements.base_elements import ProductBased, ElementEncoder
from bim2sim.utilities.types import FlowSide, FlowDirection

logger = logging.getLogger(__name__)


class HvacGraph(nx.Graph):
    """HVAC related graph manipulations based on ports."""
    # TODO 246 HvacGraph init should only be called one based on IFC as it works
    #  with port.connection and therefore is not reliable after changes are made
    #  to the graph
    def __init__(self, elements=None, **attr):
        super().__init__(incoming_graph_data=None, **attr)
        if elements:
            self._update_from_elements(elements)

    def _update_from_elements(self, elements):
        """
        Update graph based on ports of elements.
        """

        nodes = [port for instance in elements for port in instance.ports
                 if port.connection]
        inner_edges = [connection for instance in elements
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
        logger.info("Contracted the ports into node elements, this"
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
        cycles = [cycle for cycle in base_cycles if len(
            {port.parent for port in cycle}) > 1]
        logger.info("Found %d cycles", len(cycles))
        return cycles

    # TODO #246 delete because not needed anymore
    @staticmethod
    def get_type_chains(
            element_graph: nx.Graph,
            types: Iterable[Type[ProductBased]],
            include_singles: bool = False):
        """Get lists of consecutive elements of the given types. Elements are
        ordered in the same way as they are connected.

        Args:
            element_graph: Graph object with elements as nodes.
            types: Items the chains are built of.
            include_singles:

        Returns:
            chain_lists: Lists of consecutive elements.
        """

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
            # TODO more efficient
            elements = nx.shortest_path(subgraph, *end_nodes)
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

    def plot(self, path: Path = None, ports: bool = False, dpi: int = 400,
             use_pyvis=False):
        """Plot graph and either display or save as pdf file.

        Args:
            path: If provided, the graph is saved there as pdf file or html
             if use_pyvis=True.
            ports: If True, the port graph is plotted, else the element graph.
            dpi: dots per inch, increase for higher quality (takes longer to
             render)
            use_pyvis: exports graph to interactive html
        """
        # importing matplotlib is slow and plotting is optional
        import matplotlib.pyplot as plt
        from pyvis.network import Network

        # https://plot.ly/python/network-graphs/
        edge_colors_flow_side = {
            FlowSide.supply_flow: dict(edge_color='red'),
            FlowSide.return_flow: dict(edge_color='blue'),
            FlowSide.unknown: dict(edge_color='grey'),
        }
        node_colors_flow_direction = {
            FlowDirection.source: dict(node_color='white', edgecolors='blue'),
            FlowDirection.sink: dict(node_color='blue', edgecolors='black'),
            FlowDirection.sink_and_source: dict(node_color='grey', edgecolors='black'),
            FlowDirection.unknown: dict(node_color='grey', edgecolors='black'),
        }

        kwargs = {}
        if ports:
            # set port (nodes) colors based on flow direction
            graph = self
            kwargs['node_color'] = [
                node_colors_flow_direction[
                    port.flow_direction]['node_color'] for port in self]
            kwargs['edgecolors'] = [
                node_colors_flow_direction[
                    port.flow_direction]['edgecolors'] for port in self]
            kwargs['edge_color'] = 'grey'
        else:
            kwargs['node_color'] = 'blue'
            kwargs['edgecolors'] = 'black'
            # set connection colors (edges) based on flow side
            graph = self.element_graph
            edge_color_map = []
            for edge in graph.edges:
                sides0 = {port.flow_side for port in edge[0].ports}
                sides1 = {port.flow_side for port in edge[1].ports}
                side = None
                # element with multiple sides is usually a consumer / generator
                # (or result of conflicts) hence side of definite element is
                # used
                if len(sides0) == 1:
                    side = sides0.pop()
                elif len(sides1) == 1:
                    side = sides1.pop()
                edge_color_map.append(edge_colors_flow_side[side]['edge_color'])
            kwargs['edge_color'] = edge_color_map
        if use_pyvis:
            # convert all edges to strings to use dynamic plotting via pyvis
            graph_cp = graph.copy()
            nodes = graph_cp.nodes()
            replace = {}
            for node in nodes.keys():
                # use guid because str must be unique to prevent overrides
                replace[node] = str(node) + ' ' + str(node.guid)

            # Todo Remove temp code. This is for Abschlussbericht Plotting only!
            # start of temp plotting code
            bypass_nodes_guids = []
            small_pump_guids = []
            parallel_pump_guids = []
            for node in nodes:
                try:
                    if node.length.m == 34:
                        bypass_nodes_guids.append(node.guid)
                except AttributeError:
                    pass
                try:
                    if node.rated_power.m == 0.6:
                        small_pump_guids.append(node.guid)
                except AttributeError:
                    pass
                try:
                    if node.rated_power.m == 1:
                        parallel_pump_guids.append(node.guid)
                except AttributeError:
                    pass
            # end of temp plotting code

            nx.relabel_nodes(graph_cp, replace, copy=False)
            net = Network(height='1000', width='1000', notebook=False,
                          bgcolor='white', font_color='black', layout=False)
            net.barnes_hut(gravity=-17000, spring_length=55)
            # net.show_buttons()
            pyvis_json = Path(__file__).parent.parent.parent / \
                'assets/configs/pyvis/pyvis_options.json'
            f = open(pyvis_json)
            net.options = json.load(f)

            net.from_nx(graph_cp, default_node_size=50)
            for node in net.nodes:
                try:
                    node['label'] = node['label'].split('<')[1]
                except:
                    pass
                # TODO #633 use is_generator(), is_consumer() etc.
                node['label'] = node['label'].split('(ports')[0]
                if 'agg' in node['label'].lower():
                    node['label'] = node['label'].split('Agg0')[0]
                if 'storage' in node['label'].lower():
                    node['color'] = 'purple'
                if 'distributor' in node['label'].lower():
                    node['color'] = 'gray'
                if 'pump' in node['label'].lower():
                    node['color'] = 'blue'
                if 'spaceheater' in node['label'].lower():
                    node['color'] = 'purple'
                if 'pipestrand' in node['label'].lower():
                    node['color'] = 'blue'
                if any([ele in node['label'].lower() for ele in [
                    'parallelpump',
                    'boiler',
                    'generatoronefluid',
                    'heatpump',
                ]]):
                    node['color'] = 'yellow'
                # bypass color for parallelpump test
                if node['id'].split('> ')[-1] in bypass_nodes_guids:
                    node['color'] = 'green'
                if node['id'].split('> ')[-1] in small_pump_guids:
                    node['color'] = 'purple'
                if node['id'].split('> ')[-1] in parallel_pump_guids:
                    node['color'] = 'red'

        else:
            plt.figure(dpi=dpi)
            nx.draw(graph, node_size=10, font_size=5, linewidths=0.5, alpha=0.7,
                    with_labels=True, **kwargs)
            plt.draw()
        if path:
            if use_pyvis:
                name = "%s_graph_pyvis.html" % ("port" if ports else "element")
                try:
                    net.save_graph(name)
                    shutil.move(name, path)
                except Exception as ex:
                    logger.error("Unable to save plot of graph (%s)", ex)
            else:
                name = "%s_graph.pdf" % ("port" if ports else "element")
                try:
                    plt.savefig(
                        os.path.join(path, name),
                        bbox_inches='tight')
                except IOError as ex:
                    logger.error("Unable to save plot of graph (%s)", ex)
        else:
            if use_pyvis:
                name = "graph.html"
                try:
                    net.show(name)
                except Exception as ex:
                    logger.error("Unable to show plot of graph (%s)", ex)
            else:
                plt.show()
        plt.clf()

    def dump_to_cytoscape_json(self, path: Path, ports: bool = True):
        """Dumps the current state of the graph to a json file in cytoscape
        format.

        Args:
            path: Pathlib path to where to dump the JSON file.
            ports: if True the ports graph will be serialized, else the
            element_graph.
        """
        if ports:
            export_graph = self
            name = 'port_graph_cytoscape.json'
        else:
            export_graph = self.element_graph
            name = 'element_graph_cytoscape.json'
        with open(path / name, 'w') as fp:
            json.dump(json_graph.cytoscape_data(export_graph), fp,
                      cls=ElementEncoder)

    def to_serializable(self):
        """Returns a json serializable object"""
        return json_graph.adjacency_data(self)

    @classmethod
    def from_serialized(cls, data):
        """Sets grapg from serialized data"""
        return cls(json_graph.adjacency_graph(data))

    @staticmethod
    def remove_not_wanted_nodes(
            graph: element_graph,
            wanted: Set[Type[ProductBased]],
            inert: Set[Type[ProductBased]] = None):
        """Removes not wanted and not inert nodes from the given graph.

        Args:
            graph: element_graph
            wanted: set of all elements that are wanted and should persist in
                graph
            inert: set all inert elements. Are treated the same as wanted.
        """
        if inert is None:
            inert = set()
        if not all(map(
                lambda item: issubclass(item, ProductBased), wanted | inert)):
            raise AssertionError("Invalid type")
        _graph = graph.copy()
        # remove blocking nodes
        remove = {node for node in _graph.nodes
                  if type(node) not in wanted | inert}
        _graph.remove_nodes_from(remove)
        return _graph

    @staticmethod
    def find_bypasses_in_cycle(graph: nx.Graph, cycle, wanted):
        """ Detects bypasses in the given cycle of the given graph.

        Bypasses are any direct connections between edge elements which don't
        hold wanted elements.

        Args:
            graph: The graph in which the cycle belongs.
            cycle: A list of nodes representing a cycle in the graph.
            wanted: A list of classes of the desired node type.

        Returns:
            List: A list of bypasses, where each bypass is a list of elements in
            the bypass.

        Raises:
            None
        """
        bypasses = []
        # get wanted guids in the cycle
        wanted_guids_cycle = {node.guid for node in
                              cycle if type(node) in wanted}

        # check that it's not a parallel connection of wanted elements
        if len(wanted_guids_cycle) < 2:
            # get edge_elements
            edge_elements = [
                node for node in cycle if len(node.ports) > 2]

            # get direct connections between the edges
            subgraph = graph.subgraph(cycle)
            dir_connections = HvacGraph.get_dir_paths_between(
                subgraph, edge_elements)

            # remove strands without wanted items
            for dir_connection in dir_connections:
                if not any(type(node) == want for want in wanted
                           for node in dir_connection):
                    bypasses.append(dir_connection)
        return bypasses

    @staticmethod
    def get_all_cycles_with_wanted(graph, wanted):
        """Returns a list of cycles with wanted element in it."""
        # todo how to handle cascaded boilers

        directed = graph.to_directed()
        simple_cycles = list(nx.simple_cycles(directed))
        # filter cycles:
        cycles = [cycle for cycle in simple_cycles for node in cycle if
                  type(node) in wanted and len(cycle) > 2]

        # remove duplicate cycles with only different orientation
        cycles_sorted = cycles.copy()
        # sort copy by guid
        for i, my_list in enumerate(cycles_sorted):
            cycles_sorted[i] = sorted(my_list, key=lambda x: x.guid,
                                      reverse=True)
        # remove duplicates
        unique_cycles = [list(x) for x in set(tuple(x) for x in cycles_sorted)]

        # group cycles by wanted elements
        wanted_elements = [node for node in graph.nodes if type(node) in wanted]
        cycles_dict = {}
        for wanted_element in wanted_elements:
            cycles_dict[wanted_element] = []
            for cycle in unique_cycles:
                if wanted_element in cycle:
                    cycles_dict[wanted_element].append(cycle)

        return cycles_dict

    @staticmethod
    def detect_bypasses_to_wanted(graph, wanted, inert, blockers):
        """
        Returns a list of nodes which build a bypass to the wanted elements
        and blockers. E.g. used to find bypasses between generator and
        distributor.
        :returns: list of nodes
        """
        # todo currently not working, this might be reused later
        raise NotImplementedError
        pot_edge_elements = inert - blockers - wanted

        cycles = HvacGraph.get_all_cycles_with_wanted(graph, wanted)

        # get cycle with blocker (can't hold bypass if has wanted and blocker)
        blocker_cycles = [cycle for cycle in cycles
                          if any(type(node) == block for block in
                                 blockers for node in cycle)]
        for blocker_cycle in blocker_cycles:
            cycles.remove(blocker_cycle)

        pot_bypass_nodes = []
        for cycle in cycles:
            # get edge_elements
            edge_elements = [node for node in cycle if
                             len(list(nx.all_neighbors(graph, node))) > 2 and
                             type(node) in pot_edge_elements]
            # get direct connections between edge_elements
            dir_connections = HvacGraph.get_dir_paths_between(
                graph, edge_elements)
            # filter connections, that has no wanted nodes
            for dir_connection in dir_connections:
                if not any(type(node) == want for want in wanted for node in
                           dir_connection):
                    pot_bypass_nodes.extend(dir_connection)
        # filter the potential bypass nodes for the once not in blocker cycles
        bypass_nodes = [pot_bypass_node
                        for pot_bypass_node in pot_bypass_nodes
                        for blocker_cycle in blocker_cycles
                        if pot_bypass_node not in blocker_cycle]
        # remove duplicates
        bypass_nodes = list(set(bypass_nodes))

        return bypass_nodes

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

        # detect simple cycles
        basis_cycles = nx.cycle_basis(_graph)
        graph_changed = False
        # remove bypasses which prevent correct finding of parallel pump cycles
        for basis_cycle in basis_cycles:
            bypasses = HvacGraph.find_bypasses_in_cycle(
                _graph, basis_cycle, wanted)
            if bypasses:
                graph_changed = True
                for bypass in bypasses:
                    _graph.remove_nodes_from([node for node in bypass])

        if graph_changed:
            # update graph after removing bypasses
            basis_cycles = nx.cycle_basis(_graph)

        basis_cycle_sets = [frozenset((node.guid for node in basis_cycle))
                            for basis_cycle in basis_cycles]  # hashable
        wanted_guids = {node.guid
                        for node in _graph.nodes if type(node) in wanted}

        occurrence_cycles = {}
        cycle_occurrences = {}
        for cycle in basis_cycle_sets:
            wanteds = frozenset(
                guid_node for guid_node in cycle if guid_node in wanted_guids)
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
                known_items = known_items | {
                    oc for k in known for oc in cycle_occurrences[k]}

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
        if not all(map(lambda item: issubclass(
                item, ProductBased), wanted | inert)):
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

    def subgraph_from_elements(self, elements: list):
        """ Returns a subgraph of the current graph containing only the ports
            associated with the provided elements.

        Args:
            elements: A list of elements to include in the subgraph.

        Returns:
            A subgraph of the current graph that contains only the ports
            associated with the provided elements.

        Raises:
            AssertionError: If the provided elements are not part of the graph.

        """
        if not set(elements).issubset(set(self.elements)):
            raise AssertionError('The elements %s are not part of this graph.',
                                 elements)
        return self.subgraph((port for ele in elements for port in ele.ports))

    @staticmethod
    def remove_classes_from(graph: nx.Graph,
                            classes_to_remove: Set[Type[ProductBased]]
                            ) -> Union[nx.Graph, HvacGraph]:
        """ Removes nodes from a given graph based on their class.

            Args:
                graph: The graph to remove nodes from.
                classes_to_remove: A set of classes to remove from the graph.

            Returns:
                The modified graph as a new instance.
        """
        _graph = graph.copy()
        if not isinstance(_graph, HvacGraph):
            nodes_to_remove = {node for node in _graph.nodes if
                               node.__class__ in classes_to_remove}
        else:
            elements_to_remove = {ele for ele in _graph.elements if
                                  ele.__class__ in classes_to_remove}
            nodes_to_remove = [port for ele in elements_to_remove
                               for port in ele.ports]
        _graph.remove_nodes_from(nodes_to_remove)
        return _graph
