from bim2sim.tasks.base import ITask

import networkx as nx
from pathlib import Path
import json
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.graph_functions import create_graph_nodes, \
    lay_direction, connect_nodes_with_grid, check_graph, add_graphs, save_networkx_json, read_json_graph
from bim2sim.utilities.visualize_graph_functions import visualzation_networkx_3D, visulize_networkx

import matplotlib.pyplot as plt
from scipy.spatial import distance

from networkx.algorithms.components import is_strongly_connected


class CreateHeatingTreeBase(ITask):
    """short docs.

    longs docs.

    Args:
        ...
    Returns:
        ...
    """

    reads = ('building_graph', 'elements')
    touches = ('heating_graph', )
    final = True


    def __init__(self, playground):
        super().__init__(playground)

    def run(self, building_graph, elements: dict):
        if self.playground.sim_settings.bldg_graph_from_json:
            heating_graph = read_json_graph(Path(self.playground.sim_settings.distribution_networkx_path))
        else:
            type_delivery = self.playground.sim_settings.distribution_delivery_nodes
            self.logger.info(f"Create a distribution system with type {type_delivery}")
            self.logger.info(f'Type of delivery nodes: {type_delivery}')
            # Define delivery nodes
            G, delivery_nodes = self.set_delivery_nodes(graph=building_graph, type_delivery=type_delivery)
            # todo: Delivery nodes als cache wie bei den davor?
            start_point = (4.040, 5.990, 0)
            # todo: David sim_setting für tuples
            start_point = (5, 7, 0)
            # Define distributor nodes
            storeys = sorted(filter_elements(elements, 'Storey'), key=lambda obj: obj.position[2])
            G, source_nodes = self.set_distributor_nodes(G, source_pos=start_point, storeys=storeys)
            check_graph(G, type=G.graph["grid_type"])

            # Calculate distribution system with Steiner Baum Tree algorithm:
            heating_graph = self.create_heating_circle(G,
                                                       storeys=storeys,
                                                       source_nodes=source_nodes,
                                                       delivery_nodes=delivery_nodes)
            # Save heating graph in a json file.
            distribution_networkx_file = Path(self.playground.sim_settings.distribution_networkx_path)
            save_networkx_json(heating_graph, file=distribution_networkx_file)

        return heating_graph,




    def reduce_path_nodes(self, G:nx.Graph(),
                          start_nodes: list,
                          end_nodes: list,
                          color: str = "grey",
                          ):
        """

        Args:
            G ():
            start_nodes ():
            end_nodes ():
            color ():

        Returns:

        """
        G = G.copy()
        deleted_nodes = True  # Flag, um die Iteration neu zu starten

        while deleted_nodes:
            deleted_nodes = False
            for start in start_nodes:
                for end in end_nodes:
                    path = nx.shortest_path(G, source=start, target=end)  # Annahme: Pfad ist bereits gegeben
                    restart_inner_loop = False
                    for i in range(1, len(path) - 1):
                        node1 = path[i - 1]
                        node2 = path[i]
                        node3 = path[i + 1]
                        if G.degree(node2) > 2:
                            continue
                        elif self.is_linear_path(G, node1, node2, node3):
                            # Entferne den Knoten node2
                            # Erstelle eine neue Kante zwischen node1 und node3
                            length = abs(distance.euclidean(G.nodes[node1]["pos"], G.nodes[node3]["pos"]))
                            G.add_edge(node1,
                                       node3,
                                       color=color,
                                       edge_type=G.nodes[node1]["direction"],
                                       grid_type=G.nodes[node1]["direction"],
                                       direction=G.nodes[node1]["direction"],
                                       length=length)
                            G.remove_node(node2)
                            deleted_nodes = True  # Setze das Flag auf True, um die Iteration neu zu starten
                            restart_inner_loop = True  # Setze das Flag auf True, um die innere Schleife neu zu starten
                            break  # Beende die innere Schleife
                    if restart_inner_loop:
                        break  # Starte die innere Schleife neu
        return G

    @staticmethod
    def is_linear_path(G: nx.DiGraph(),
                       node1,
                       node2,
                       node3):
        # Check whether the edges are straight
        x1, y1, z1 = G.nodes[node1]["pos"]
        x2, y2, z2 = G.nodes[node2]["pos"]
        x3, y3, z3 = G.nodes[node3]["pos"]
        # Z - Axis
        if x2 == x1 == x3 and y1 == y2 == y3:
            return True
        # X - Axis
        if z2 == z1 == z3 and y1 == y2 == y3:
            return True
        # Y - Axis
        if z2 == z1 == z3 and x1 == x2 == x3:
            return True
        else:
            return False

    def create_heating_circle(self,
                              G: nx.Graph(),
                              storeys: list,
                              source_nodes: list,
                              delivery_nodes: list,
                              one_pump_flag: bool = False) -> nx.Graph():

        """
        Erstelle Endpunkte

        """
        # Same Process for each storey
        steinertree_graphs = []
        for st in storeys:
            storey_nodes = [node for node, data in G.nodes(data=True) \
                            if data['belongs_to_storey'] == st.guid]
            # build storey subgraph
            subgraph = G.subgraph(storey_nodes)
            self.logger.info(f"Calculate distribution system in storey {st} with steinertree algorithm.")
            steinertree_nodes = []
            storey_start_nodes = []
            storey_delivery_nodes = []
            #visulize_networkx(subgraph, type_grid=G.graph["grid_type"])
            for source in source_nodes:
                if G.nodes[source]["belongs_to_storey"] == st.guid:
                    steinertree_nodes.append(source)
                    storey_start_nodes.append(source)
            for delivery in delivery_nodes:
                if G.nodes[delivery]["belongs_to_storey"] == st.guid:
                    steinertree_nodes.append(delivery)
                    storey_delivery_nodes.append(delivery)

            # Steiner Baum Tree: Berechnung des Steinerbaums pro Etage
            steinertree = nx.algorithms.approximation.steinertree.steiner_tree(G=subgraph,
                                                                               weight="length",
                                                                               terminal_nodes=steinertree_nodes,
                                                                               method="kou")

            total_length = sum([edge[2]['length'] for edge in steinertree.edges(data=True)])
            self.logger.info(f"Length of steinertree in storey {st}: {total_length}.")

            # reduce unnecessary nodes
            steinertree = self.reduce_path_nodes(steinertree,
                                                 start_nodes=storey_start_nodes,
                                                 end_nodes=storey_delivery_nodes)

            # Straightening the graph
            steinertree = self.directed_graph(steinertree,
                                              source_nodes=storey_start_nodes[0],
                                              grid_type="supply_line")

            # Check DiGraph
            self.check_directed_graph(steinertree, type_graph=steinertree.graph["grid_type"])
            steinertree_graphs.append(steinertree)


        # Connect different steinertree graph
        dist_supply_graph = add_graphs(steinertree_graphs)

        # Add Rise tube to distribution system
        dist_supply_graph = self.add_rise_tube(graph=dist_supply_graph)

        # Check directed Graph
        self.check_directed_graph(dist_supply_graph, dist_supply_graph.graph["grid_type"])

        # create return direction graph
        dist_return_graph = self.create_return_graph(dist_supply_graph, offset=0.3)
        # Add new attribute "grid_type"
        # todo: bereits in die Graphen einordnen
        nx.set_node_attributes(dist_supply_graph, "supply_line", 'grid_type')
        nx.set_node_attributes(dist_return_graph, 'return_line', 'grid_type' )
        # Connect supply and return Graph
        dist_graph = self.build_distribution_graph(supply_graph=dist_supply_graph,
                                                   return_graph=dist_return_graph)

        # Connect supply and return delivery nodes

        dist_graph = self.connect_supply_return_nodes(dist_graph,
                                                      node_type_list=
                                                            ["delivery_node_supply",
                                                            "delivery_node_return"
                                                            ])
        # todo: Attribute der Knoten und Kanten überschreiben
        #dist_graph = self.update_attributes(dist_graph)
        # Update nodes with Components: node_type
        dist_graph = self.update_node_components(dist_graph)
        # Add Components
        dist_graph = self.add_component_nodes(dist_graph, one_pump_flag=one_pump_flag)
        return dist_graph


        #visulize_networkx(dist_graph, type_grid=dist_graph.graph["grid_type"])
        #plt.show()

    def update_node_components(self,
                               graph: nx.DiGraph()) -> nx.DiGraph():
        """

        Args:
            graph ():

        Returns:

        """
        for node, data in graph.nodes(data=True):
            # bends
            if graph.degree[node] == 2:
                if len(list(graph.successors(node))) == 1 and len(list(graph.predecessors(node))) == 1:
                    delivery_list = ["delivery_node_supply", "delivery_node_return"]
                    if not set(delivery_list) & set(graph.nodes[node]["node_type"]):
                        successor_nodes = list(graph.successors(node))[0]
                        predecessors_node = list(graph.predecessors(node))[0]
                        if self.is_linear_path(G=graph,
                                               node1=successor_nodes,
                                               node2=node,
                                               node3=predecessors_node) is False:
                            graph.nodes[node]["component_type"] = "bends"
            # separator
            if graph.degree[node] == 3:
                successor_nodes = list(graph.successors(node))
                predecessors_nodes = list(graph.predecessors(node))
                if len(successor_nodes) == 2 and len(predecessors_nodes) == 1:
                    graph.nodes[node]["component_type"] = "separator"
            # union
            if graph.degree[node] == 3:
                successor_nodes = list(graph.successors(node))
                predecessors_nodes = list(graph.predecessors(node))
                if len(successor_nodes) == 1 and len(predecessors_nodes) == 2:
                    graph.nodes[node]["component_type"] = "unifier"
            # deaerator
            if "delivery_node_return" in data['node_type']:
                graph.nodes[node]["component_type"] = "deaerator"
        return graph

    @staticmethod
    def connect_supply_return_nodes(graph: nx.DiGraph(),
                                    node_type_list: list,
                                    edge_type: str = "connection",
                                    grid_type: str = "connection",
                                    color: str = "black") -> nx.DiGraph():
        """

        Args:
            graph ():

        Returns:

        """
        element_nodes = {}
        for node, data in graph.nodes(data=True):
            if set(node_type_list) & set(data["node_type"]):
                element = data["ID_element"]
                if element not in element_nodes:
                    element_nodes[element] = []
                element_nodes[element].append(node)
        for element, nodes in element_nodes.items():
            source_supply, source_return = None, None
            for node in nodes:
                if "return_line" == graph.nodes[node]["grid_type"]:
                    source_return = node
                elif "supply_line" == graph.nodes[node]["grid_type"]:
                    source_supply = node
            if source_supply and source_return is not None:
                length = abs(
                        distance.euclidean(graph.nodes[nodes[0]]["pos"], graph.nodes[nodes[1]]["pos"]))
                graph.add_edge(source_supply,
                               source_return,
                               color=color,
                               edge_type=edge_type,
                               grid_type=grid_type,
                               length=length)

        return graph

    def build_distribution_graph(self,
                                 supply_graph: nx.DiGraph(),
                                 return_graph: nx.DiGraph(),
                                 grid_type: str = "heating_circle") -> nx.DiGraph():
        """
        Args:
            supply_graph ():
            return_graph ():
            grid_type ():
        Returns:
        """

        dist_graph = nx.disjoint_union(supply_graph, return_graph)
        dist_graph.graph["grid_type"] = grid_type
        return dist_graph



    @staticmethod
    def update_attributes(graph: nx .DiGraph()) -> nx.DiGraph():
        """

        Args:
            graph ():

        Returns:

        """
        for node, data in graph.nodes(data=True):
            if data["grid_type"] == "supply_line":
                color = "red"
                edge_type = "supply_line"
                grid_type = "supply_line"
                graph.nodes[node]["color"] = "red"
                graph.nodes[node]["edge_type"] = "supply_line"
                graph.nodes[node]["grid_type"] = "supply_line"
            elif data["grid_type"] == "return_line":
                color = "blue"
                edge_type = "return_line"
                grid_type = "return_line"
            else:
                color = "orange"
                edge_type = "connection_line"
                grid_type = "connection_line"
        return graph


    def add_component_nodes(self,
                            graph: nx.DiGraph(),
                            one_pump_flag: bool = True) -> nx.DiGraph():
        """
        Args:
            graph ():

        Returns:

        """
        # todo: Mischventil mit anschließend verbinden
        # todo: Doku der Komponenten
        # todo: node_type als str: soll als feste Komponenten festglegt werden
        for node, data in graph.nodes(data=True):
            # supply line
            if data["grid_type"] == "supply_line":
                color = "red"
                edge_type = "supply_line"
                grid_type = "supply_line"
                if one_pump_flag is False:
                    type_list = ["distributor"]
                    if set(type_list).issubset(set(data['node_type'])):
                        l_rules = "pump"
                        successors_nodes = list(graph.successors(node))
                        graph = self.add_components_on_graph(G=graph,
                                                             node=node,
                                                             l_rules=l_rules,
                                                             z_direction=False,
                                                             neighbors=successors_nodes)
                node_list = ["distributor", "source"]
                if set(node_list).issubset(set(data['node_type'])):
                    l_rules = "gravity_break"
                    successors_nodes = list(graph.successors(node))
                    graph = self.add_components_on_graph(G=graph,
                                                         node=node,
                                                         l_rules=l_rules,
                                                         z_direction=True,
                                                         x_direction=False,
                                                         y_direction=False,
                                                         neighbors=successors_nodes)
                if "delivery_node_supply" in data['node_type']:
                    l_rules = "thermostatic_valve"
                    predecessors_nodes = list(graph.predecessors(node))
                    graph = self.add_components_on_graph(G=graph,
                                                         node=node,
                                                         l_rules=l_rules,
                                                         z_direction=True,
                                                         x_direction=False,
                                                         y_direction=False,
                                                         neighbors=predecessors_nodes)

            # return line
            if data["grid_type"] == "return_line":
                color = "blue"
                edge_type = "return_line"
                grid_type = "return_line"
                node_list = ["sink"]
                if set(node_list) & set(data['node_type']):
                    l_rules = "membrane_expansion_vessel" + "-gate_valve" + "-strainer" + "-gate_valve"
                    predecessors_nodes = list(graph.predecessors(node))
                    graph = self.add_components_on_graph(G=graph,
                                                         node=node,
                                                         l_rules=l_rules,
                                                         z_direction=True,
                                                         x_direction=False,
                                                         y_direction=False,
                                                         lay_from_node=False,
                                                         neighbors=predecessors_nodes)
                if "delivery_node_return" in data['node_type']:
                    l_rules = "backflow_preventer"
                    successors_nodes = list(graph.successors(node))
                    graph = self.add_components_on_graph(G=graph,
                                                         node=node,
                                                         l_rules=l_rules,
                                                         z_direction=True,
                                                         x_direction=False,
                                                         y_direction=False,
                                                         neighbors=successors_nodes)
            else:
                color = "orange"
                edge_type = "connection_line"
                grid_type = "connection_line"
                # Connection
                type_list = ["source"]
                if set(type_list).issubset(set(data['node_type'])):
                    # Fall eine Pumpe
                    if one_pump_flag is True:
                        l_rules = "heat_source" + "-pump-" + "safety_valve"
                    else:
                        l_rules = "heat_source"
                    predecessors_node = list(graph.predecessors(node))
                    graph = self.add_components_on_graph(G=graph,
                                                         node=node,
                                                         l_rules=l_rules,
                                                         z_direction=False,
                                                         color=color,
                                                         lay_from_node=False,
                                                         edge_type=edge_type,
                                                         neighbors=predecessors_node,
                                                         grid_type=grid_type,
                                                         source_flag=True)
        return graph

    @staticmethod
    def create_directed_edges(graph: nx.DiGraph(),
                              node_list: list,
                              edge_type: str,
                              grid_type: str,
                              color: str = "grey") -> nx.DiGraph():
        """

        Args:
            graph ():
            node_list ():
            color ():
            edge_type ():
            grid_type ():

        Returns:

        """
        for i in range(len(node_list) - 1):
            length = abs(distance.euclidean(graph.nodes[node_list[i]]["pos"], graph.nodes[node_list[i + 1]]["pos"]))
            graph.add_edge(node_list[i],
                           node_list[i + 1],
                           color=color,
                           edge_type=edge_type,
                           grid_type=grid_type,
                           length=length)

        return graph

    def add_components_on_graph(self,
                                G: nx.DiGraph(),
                                node,
                                l_rules: str,
                                neighbors,
                                grid_type: str = None,
                                edge_type: str = None,
                                color: str = "black",
                                lay_from_node: bool = True,
                                source_flag: bool = False,
                                tol_value: float = 0.0,
                                z_direction: bool = True,
                                x_direction: bool = True,
                                y_direction: bool = True):
        """
        Fügt Komponenten auf den Graphen hinzu.
        Args:
            node ():
            l_rules ():
            neighbors ():
            grid_type ():
            edge_type ():
            color ():
            lay_from_node ():
            source_flag ():
            tol_value ():
            z_direction ():
            x_direction ():
            y_direction ():
            G ():
        """
        str_chain = l_rules.split("-")
        G = G.copy()
        for k, neighbor in enumerate(neighbors):
            node_list = []
            if set(str_chain) & set(G.nodes[node]["node_type"]) or set(str_chain) & set(G.nodes[neighbor]["node_type"]):
                continue
            if lay_from_node:
                x2, y2, z2 = G.nodes[neighbor]["pos"]
                x1, y1, z1 = G.nodes[node]["pos"]
            else:
                x1, y1, z1 = G.nodes[neighbor]["pos"]
                x2, y2, z2 = G.nodes[node]["pos"]
            # todo: Weiter kürzen
            # todo: Farben abhängig von supply und return
            # Z Axis
            if source_flag is True:
                diff_x = (x1 - x2)
                comp_diff_x = diff_x / (len(str_chain) + 1)
                diff_y = (y1 - y2)
                comp_diff_y = diff_y / (len(str_chain) + 1)
                for i in range(0, len(str_chain)):

                    x = x1 - (i + 1) * comp_diff_x
                    y = y1 - (i + 1) * comp_diff_y
                    pos = (x, y, z1)
                    G, node_name = create_graph_nodes(G,
                                                      points_list=[pos],
                                                      component_type=str_chain[i],
                                                      grid_type=G.nodes[node]["grid_type"],
                                                      color=G.nodes[node]["color"],
                                                      ID_element=G.nodes[node]["ID_element"],
                                                      element_type=G.nodes[node]["element_type"],
                                                      node_type=G.nodes[node]["node_type"],
                                                      belongs_to_element=G.nodes[node]["belongs_to_element"],
                                                      belongs_to_room=G.nodes[node]["belongs_to_room"],
                                                      belongs_to_storey=G.nodes[node]["belongs_to_storey"],
                                                      direction=G.nodes[node]["direction"])
                    node_list = list(set(node_list + node_name))
            if z_direction:
                if abs(x1 - x2) <= tol_value and abs(y1 - y2) <= tol_value:
                    diff_z = (z1 - z2)
                    comp_diff = diff_z / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        z = z1 - (i + 1) * comp_diff
                        pos = (x1, y1, z)
                        G, node_name = create_graph_nodes(G,
                                                          points_list=[pos],
                                                          grid_type=G.nodes[node]["grid_type"],
                                                          component_type=str_chain[i],
                                                          color=G.nodes[node]["color"],
                                                          ID_element=G.nodes[node]["ID_element"],
                                                          element_type=G.nodes[node]["element_type"],
                                                          node_type=G.nodes[node]["node_type"],
                                                          belongs_to_element=G.nodes[node]["belongs_to_element"],
                                                          belongs_to_room=G.nodes[node]["belongs_to_room"],
                                                          belongs_to_storey=G.nodes[node]["belongs_to_storey"],
                                                          direction=G.nodes[node]["direction"])
                        node_list = list(set(node_list + node_name))
            # X Achse
            if x_direction:
                if abs(z1 - z2) <= tol_value and abs(y1 - y2) <= tol_value:
                    diff_x = (x1 - x2)
                    comp_diff = diff_x / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        x = x1 - (i + 1) * comp_diff
                        pos = (x, y1, z1)
                        G, node_name = create_graph_nodes(G,
                                                          points_list=[pos],
                                                          grid_type=G.nodes[node]["grid_type"],
                                                          color=G.nodes[node]["color"],
                                                          component_type=str_chain[i],
                                                          ID_element=G.nodes[node]["ID_element"],
                                                          element_type=G.nodes[node]["element_type"],
                                                          node_type=G.nodes[node]["node_type"],
                                                          belongs_to_element=G.nodes[node]["belongs_to_element"],
                                                          belongs_to_room=G.nodes[node]["belongs_to_room"],
                                                          belongs_to_storey=G.nodes[node]["belongs_to_storey"],
                                                          direction=G.nodes[node]["direction"])
                        node_list = list(set(node_list + node_name))
            # Y Achse
            if y_direction is True:
                if abs(z1 - z2) <= tol_value and abs(x1 - x2) <= tol_value:
                    diff_y = (y1 - y2)
                    comp_diff = diff_y / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        y = y1 - (i + 1) * comp_diff
                        pos = (x1, y, z1)
                        G, node_name = create_graph_nodes(G,
                                                          points_list=[pos],
                                                          grid_type=G.nodes[node]["grid_type"],
                                                          color=G.nodes[node]["color"],
                                                          component_type=str_chain[i],
                                                          ID_element=G.nodes[node]["ID_element"],
                                                          element_type=G.nodes[node]["element_type"],
                                                          node_type=G.nodes[node]["node_type"],
                                                          belongs_to_element=G.nodes[node]["belongs_to_element"],
                                                          belongs_to_room=G.nodes[node]["belongs_to_room"],
                                                          belongs_to_storey=G.nodes[node]["belongs_to_storey"],
                                                          direction=G.nodes[node]["direction"] )
                        node_list = list(set(node_list + node_name))
            if G.has_edge(neighbor, node):
                G.remove_edge(neighbor, node)
                node_list.insert(0, neighbor)
                node_list.append(node)
            if G.has_edge(node, neighbor):
                G.remove_edge(node, neighbor)
                node_list.insert(0, node)
                node_list.append(neighbor)
            G = self.create_directed_edges(graph=G,
                                           node_list=node_list,
                                           color=color,
                                           edge_type=edge_type,
                                           grid_type=grid_type)

        return G

    def update_graph(self, G, grid_type: str, color: str):
        for node in G.nodes():
            G.nodes[node]["color"] = color
            G.nodes[node]["grid_type"] = grid_type
        for edge in G.edges():
            G.edges[edge]["color"] = color
        return G



    def create_return_graph(self,
                            G: nx.DiGraph(),
                            offset: float = 0.1,
                            color: str = "blue")\
            -> nx.DiGraph():
        """

        Args:
            color ():
            G ():
            grid_type ():
            offset ():
        Returns:
        """

        G_reversed = G.reverse()
        G_reversed.graph["grid_type"] = "return_line"
        # Offset für die Knotenpositionen berechnen
        node_positions = nx.get_node_attributes(G, "pos")
        node_offset = {node: (pos[0] + offset, pos[1] + offset, pos[2]) for node, pos in node_positions.items()}
        nx.set_node_attributes(G_reversed, node_offset, "pos")
        for node, data in G_reversed.nodes(data=True):
            if "delivery_node_supply" in data["node_type"]:
                G_reversed.nodes[node]['node_type'] = ["delivery_node_return"]
            if "source" in data["node_type"]:
                G_reversed.nodes[node]['node_type'] = ["sink", "coupling"]
            if "distributor" in data["node_type"]:
                G_reversed.nodes[node]['node_type'] = ["coupling"]
        # Farbe der Kanten ändern
        edge_attributes = {(u, v): {"color": color} for u, v in G_reversed.edges()}
        nx.set_edge_attributes(G_reversed, edge_attributes)
        return G_reversed


    def add_rise_tube(self,
                      graph: nx.DiGraph(),
                      color: str = "red",
                      edge_type: str="rise_tube",
                      grid_type: str = "supply_line") -> nx.DiGraph():
        """
        Args:
            color ():
            edge_type ():
            grid_type ():
            graph ():
        Returns:
        """
        source_dict = {}
        for node, data in graph.nodes(data=True):
            if "distributor" in set(graph.nodes[node]["element_type"]):
                source_dict[node] = data["pos"][2]
        sorted_dict = dict(sorted(source_dict.items(), key=lambda x: x[1]))
        keys = list(sorted_dict.keys())
        for source, target in zip(keys, keys[1:]):
            length = abs(distance.euclidean(graph.nodes[source]["pos"], graph.nodes[target]["pos"]))
            graph.add_edge(source,
                           target,
                           color=color,
                           edge_type=edge_type,
                           grid_type=grid_type,
                           direction="z",
                           length=length)
        return graph


    def directed_graph(self,
                       graph: nx.Graph(),
                       source_nodes,
                       edge_type: str = "supply_line",
                       grid_type: str = "supply_line",
                       color: str = "red"):
        """
        Args:
            graph ():
            source_nodes ():
        Returns:
        """

        D = nx.DiGraph(grid_type=grid_type)
        D.add_nodes_from(graph.nodes(data=True))
        T = nx.bfs_tree(graph, source_nodes)
        for edges in T.edges():
            length = abs(distance.euclidean(graph.nodes[edges[0]]["pos"], graph.nodes[edges[1]]["pos"]))
            D.add_edge(edges[0],
                       edges[1],
                       edge_type=edge_type,
                       grid_type=grid_type,
                       length=length,
                       color=color)
        D.graph["grid_type"] = grid_type
        return D



    def check_directed_graph(self,
                             G:nx.DiGraph(),
                             type_graph:str):
        """
        Args:
            G ():
            type_graph ():
        """
        # Überprüfen, ob der Graph vollständig verbunden ist
        is_connected = is_strongly_connected(G)
        if is_connected:
            self.logger.info(f"The graph {type_graph} is fully connected.")
        else:
            self.logger.warning(f"The graph {type_graph} is not fully connected.")
            isolated_nodes = [node for node in G.nodes if G.in_degree(node) == 0 and G.out_degree(node) == 0]
            self.logger.warning(f"Isolated nodes are {isolated_nodes}.")



    def set_distributor_nodes(self,
                              graph: nx.Graph(),
                              source_pos: tuple,
                              storeys: list):
        """

        Args:
            graph ():
            source_pos ():
            storeys ():

        Returns:

        """
        source_nodes = []
        for i, st in enumerate(storeys):
            if i == 0:
                node_type = ["source", "distributor"]
            else:
                node_type = "distributor"
            positions = (source_pos[0], source_pos[1], st.position[2])
            self.logger.info(f"Set source node in storey {st} position in {positions}")
            # Create nodes
            graph, created_nodes = create_graph_nodes(graph,
                               points_list=[positions],
                               ID_element=st.guid,
                               element_type="distributor",
                               direction=lay_direction([positions]),
                               node_type=node_type,
                               belongs_to_room=st.guid,
                               belongs_to_element=st.guid,
                               belongs_to_storey=st.guid,
                               grid_type="supply_line")
            source_nodes = source_nodes + created_nodes
        # create edges
        graph = connect_nodes_with_grid(graph,
                                        node_type="snapped",
                                        pos_x_flag=True,
                                        neg_x_flag=True,
                                        pos_y_flag=True,
                                        neg_y_flag=True,
                                        node_list=source_nodes,
                                        all_edges_flag=True,
                                        collision_flag=False,
                                        no_neighbour_collision_flag=True)
        return graph, source_nodes


    def set_delivery_nodes(self,
                           graph: nx.Graph(),
                           component_delivery: str = "radiator",
                           type_delivery: list = ["IfcWindow"]) -> tuple[nx.Graph(), list]:
        """

        Args:
            graph ():
            type_delivery ():

        Returns:

        """
        self.logger.info(f"Type of delivery nodes: {type_delivery}")
        delivery_dict = {}
        delivery_nodes = []
        # Return nodes with specific element_type and sort with ID_element
        for node, data in graph.nodes(data=True):
            if set(data["element_type"]) & set(type_delivery):
                if data["ID_element"] not in delivery_dict:
                    delivery_dict[data["ID_element"]] = []
                delivery_dict[data["ID_element"]].append(node)
        remove_node_list = []
        # take one node of the delivery node with the same element_ID. Build a list with the other nodes.
        for element in delivery_dict:
            delivery_node = self.get_bottom_left_node(graph, delivery_dict[element])
            nx.set_node_attributes(graph, {delivery_node: {"node_type": ["delivery_node_supply"]}})

            nx.set_node_attributes(graph, {delivery_node: {"component_type": component_delivery}})
            delivery_nodes.append(delivery_node)
            for node in delivery_dict[element]:
                if node != delivery_node:
                    remove_node_list.append(node)
        # todo: Überflüssige Nodes entfernen
        # Delete the nodes in the list.
        #graph.remove_nodes_from(remove_node_list)
        return graph, delivery_nodes

    def get_bottom_left_node(self, graph: nx.Graph(), nodes):
        """

        Args:
            graph ():
            nodes ():

        Returns:

        """
        positions = nx.get_node_attributes(graph, 'pos')
        # find nodes with lowest z coordinate
        z_values = {node: positions[node][2] for node in nodes}
        min_z_values = sorted(z_values.items(), key=lambda x: x[1])[:2]
        node1, z1 = min_z_values[0]
        node2, z2 = min_z_values[1]
        # Überprüfe, ob sich die Knoten in x- oder y-Richtung unterscheiden
        diff_x = positions[node1][0] - positions[node2][0]
        diff_y = positions[node1][1] - positions[node2][1]
        if diff_x > 0:
            supply_node = node2
        elif diff_y > 0:
            supply_node = node2
        else:
            supply_node = node1
        return supply_node


    def steiner_tree(self, graph: nx.Graph(), term_points, grid_type: str = "supply_line", color: str = "red"):
        """
        Args:
            graph ():
            circulation_direction ():
            floor_height ():
        # term_points = sorted([n for n, data in graph.nodes(data=True) if data["type"] in {"radiator", "source"} ])
        Returns:
        """
        steinerbaum = nx.algorithms.approximation.steinertree.steiner_tree(G=graph,
                                                                           weight="length",
                                                                           terminal_nodes=term_points,
                                                                           method="kou")
        total_length = sum([edge[2]['length'] for edge in steinerbaum.edges(data=True)])
        self.logger.info(f"Steiner Tree: {grid_type} {total_length}")
        steinerbaum.graph["grid_type"] = grid_type
        # Farbe der Kanten ändern
        edge_attributes = {(u, v): {"color": color} for u, v in graph.edges()}
        nx.set_edge_attributes(graph, edge_attributes)

        return steinerbaum, total_length





