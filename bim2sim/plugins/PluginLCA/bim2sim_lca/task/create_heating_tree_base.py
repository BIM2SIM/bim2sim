from bim2sim.tasks.base import ITask

import networkx as nx
from pathlib import Path
import json
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.graph_functions import create_graph_nodes, \
    lay_direction, snapp_nodes_to_grid, check_graph, add_graphs, save_networkx_json, read_json_graph, remove_edges_from_node
from bim2sim.utilities.visualize_graph_functions import visualzation_networkx_3D, visulize_networkx

import matplotlib.pyplot as plt
from scipy.spatial import distance

from networkx.algorithms.components import is_strongly_connected


class CreateHeatingTreeBase(ITask):
    """
    Creates a distribution system from the start to the end nodes using the steinerbaum algorithm.

    The end nodes are defined first. These are the windows, doors or the centre of the room in each room.
    The end nodes are defined using sim_settings.distribution_delivery_nodes.
    In the next step, the start nodes are defined for each floor and only differ on the z-coordinate
    of the respective floor.


    Args:
        ...
    Returns:
        ...
    """

    reads = ('building_graph', 'elements', 'node_type', 'snapped_node_type', 'snapped_edge_type')
    touches = ('heating_graph', )
    final = True


    def __init__(self, playground):
        super().__init__(playground)
        #self.start_point = (4.040, 5.990, 0)
        # todo: David sim_setting für tuples zur Setzung des Startpunktes
        self.start_point = (5, 7, 0)

    def check_overlap(self, graph: nx.Graph(), node):
        pos = graph.nodes[node]['pos']
        overlapping_nodes = [n for n, data in graph.nodes(data=True) if n != node and data['pos'] == pos]
        #graph.remove_nodes_from(overlapping_nodes)
        #return graph

    def run(self, building_graph,
            elements: dict,
            node_type: str,
            snapped_node_type: str,
            snapped_edge_type: str):
        start_point = self.start_point
        if self.playground.sim_settings.heating_graph_from_json:
            heating_graph = read_json_graph(Path(self.playground.sim_settings.distribution_networkx_path))
        else:
            type_delivery = self.playground.sim_settings.distribution_delivery_nodes
            self.logger.info(f"Create a distribution system with type {type_delivery}")
            self.logger.info(f'Type of delivery nodes: {type_delivery}')
            # Define delivery nodes
            storeys = sorted(filter_elements(elements, 'Storey'), key=lambda obj: obj.position[2])
            heating_graph, delivery_nodes = self.set_delivery_nodes(graph=building_graph,
                                                                    node_type=node_type,
                                                                    type_delivery=type_delivery,
                                                                    component_type=self.playground.sim_settings.distribution_system_type)

            # Define distributor nodes


            heating_graph, source_nodes = self.set_distributor_nodes(heating_graph,
                                                                     source_pos=start_point,
                                                                     storeys=storeys)

            #heating_graph = check_graph(heating_graph, type=heating_graph.graph["grid_type"])
            # Calculate distribution system with Steiner Baum Tree algorithm:
            heating_supply_graph = self.create_heating_circle_with_steinertree(heating_graph,
                                                                            storeys=storeys,
                                                                            source_nodes=source_nodes,
                                                                            delivery_nodes=delivery_nodes)

            # Add Rise tube to distribution system
            heating_supply_graph = self.add_rise_tube(graph=heating_supply_graph)
            # Check directed Graph
            self.check_directed_graph(heating_supply_graph, heating_supply_graph.graph["grid_type"])
            # create return direction graph
            heating_return_graph = self.create_return_graph(heating_supply_graph,
                                                            offset=0.3,
                                                            component_type=self.playground.sim_settings.distribution_system_type)


            nx.set_node_attributes(heating_supply_graph, "supply_line", 'grid_type')
            nx.set_node_attributes(heating_return_graph, 'return_line', 'grid_type')
            # Connect supply and return Graph
            distribution_heating_graph = self.build_distribution_graph(supply_graph=heating_supply_graph,
                                                       return_graph=heating_return_graph)

            # Connect supply and return delivery nodes
            distribution_heating_graph = self.connect_supply_return_nodes(distribution_heating_graph,
                                                          node_type_list=
                                                          ["delivery_node_supply",
                                                           "delivery_node_return",
                                                           "source",
                                                           "sink"])
            # dist_graph = self.update_attributes(dist_graph)
            # Update nodes with Components: node_type
            distribution_heating_graph = self.update_node_components(distribution_heating_graph)
            # Add Components
            heating_graph = self.add_heating_distribution_component(distribution_heating_graph, one_pump_flag=self.playground.sim_settings.one_pump_distribution_system)
            #visulize_networkx(heating_graph, heating_graph.graph["grid_type"])
            #plt.show()
            # Save heating graph in a json file.
            distribution_networkx_file = Path(self.playground.sim_settings.distribution_networkx_path)
            save_networkx_json(heating_graph, file=distribution_networkx_file)
        #visulize_networkx(heating_graph, heating_graph.graph["grid_type"])
        return heating_graph,




    def reduce_path_nodes(self,
                          graph: nx.Graph() or nx.DiGraph(),
                          start_nodes: list,
                          end_nodes: list,
                          color: str = "grey",
                          ) -> nx.Graph() or nx.DiGraph():
        """

        Args:
            graph ():
            start_nodes ():
            end_nodes ():
            color ():

        Returns:

        """
        graph = graph.copy()
        deleted_nodes = True  # Flag, um die Iteration neu zu starten
        while deleted_nodes:
            deleted_nodes = False
            for start in start_nodes:
                for end in end_nodes:
                    path = nx.shortest_path(graph, source=start, target=end)  # Annahme: Pfad ist bereits gegeben
                    restart_inner_loop = False
                    for i in range(1, len(path) - 1):
                        node1 = path[i - 1]
                        node2 = path[i]
                        node3 = path[i + 1]
                        if graph.degree(node2) > 2:
                            continue
                        elif self.is_linear_path(graph, node1, node2, node3):
                            # Entferne den Knoten node2
                            # Erstelle eine neue Kante zwischen node1 und node3
                            length = abs(distance.euclidean(graph.nodes[node1]["pos"], graph.nodes[node3]["pos"]))
                            graph.add_edge(node1,
                                           node3,
                                           color=color,
                                           edge_type=graph.nodes[node1]["direction"],
                                           grid_type=graph.nodes[node1]["direction"],
                                           direction=graph.nodes[node1]["direction"],
                                           length=length)
                            graph.remove_node(node2)
                            deleted_nodes = True  # Setze das Flag auf True, um die Iteration neu zu starten
                            restart_inner_loop = True  # Setze das Flag auf True, um die innere Schleife neu zu starten
                            break  # Beende die innere Schleife
                    if restart_inner_loop:
                        break  # Starte die innere Schleife neu
        return graph

    @staticmethod
    def is_linear_path(G: nx.DiGraph(),
                       node1: str ,
                       node2: str,
                       node3: str):
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

    def create_heating_circle_with_steinertree(self,
                                               graph: nx.Graph(),
                                               storeys: list,
                                               source_nodes: list,
                                               delivery_nodes: list) -> nx.Graph():

        """
        Erstelle Endpunkte

        """
        # Same Process for each storey
        steinertree_graphs = []
        for st in storeys:
            storey_nodes = [node for node, data in graph.nodes(data=True) \
                            if data['belongs_to_storey'] == st.guid]
            # build storey subgraph
            subgraph = graph.subgraph(storey_nodes)
            self.logger.info(f"Calculate distribution system in storey {st} with steinertree algorithm.")
            steinertree_nodes = []
            storey_start_nodes = []
            storey_delivery_nodes = []
            #subgraph = check_graph(subgraph, type=subgraph.graph["grid_type"])
            for source in source_nodes:
                if graph.nodes[source]["belongs_to_storey"] == st.guid:
                    steinertree_nodes.append(source)
                    storey_start_nodes.append(source)
            for delivery in delivery_nodes:
                if graph.nodes[delivery]["belongs_to_storey"] == st.guid:
                    steinertree_nodes.append(delivery)
                    storey_delivery_nodes.append(delivery)
            # Steiner Baum Tree: Berechnung des Steinerbaums pro Etage
            steinertree = nx.algorithms.approximation.steinertree.steiner_tree(G=subgraph,
                                                                               weight="length",
                                                                               terminal_nodes=steinertree_nodes,
                                                                               method="kou")
            total_length = sum([edge[2]['length'] for edge in steinertree.edges(data=True)])
            self.logger.info(f"Length of steinertree in storey {st}: {total_length} meter.")
            # reduce unnecessary nodes
            if total_length != 0 and total_length is not None:
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
        return dist_supply_graph

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
                    if not graph.nodes[node]["node_type"] in delivery_list:
                        successor_nodes = list(graph.successors(node))[0]
                        predecessors_node = list(graph.predecessors(node))[0]
                        if self.is_linear_path(G=graph,
                                               node1=successor_nodes,
                                               node2=node,
                                               node3=predecessors_node) is False:
                            graph.nodes[node]["component_type"] = "bends"

            if graph.degree[node] == 3 and graph.nodes[node]["component_type"] != "distributor":
                successor_nodes = list(graph.successors(node))
                predecessors_nodes = list(graph.predecessors(node))
                # separator
                if len(successor_nodes) == 2 and len(predecessors_nodes) == 1:
                    graph.nodes[node]["component_type"] = "separator"
                # union
                if len(successor_nodes) == 1 and len(predecessors_nodes) == 2:
                    graph.nodes[node]["component_type"] = "unifier"



            # deaerator
            if "delivery_node_return" == data['node_type']:
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
            if data["node_type"] in node_type_list:
                element_nodes.setdefault(data["ID_element"], []).append(node)
        for element, nodes in element_nodes.items():
            source_supply, source_return = None, None
            for node in nodes:
                if graph.nodes[node]["node_type"] in ["delivery_node_supply", "delivery_node_return"]:
                    if "return_line" == graph.nodes[node]["grid_type"]:
                        source_return = node
                    elif "supply_line" == graph.nodes[node]["grid_type"]:
                        source_supply = node
                if graph.nodes[node]["node_type"] in ["source", "sink"]:
                    if "supply_line" == graph.nodes[node]["grid_type"]:
                        source_return = node
                    elif "return_line" == graph.nodes[node]["grid_type"]:
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


    def add_heating_distribution_component(self,
                                           graph: nx.DiGraph(),
                                           one_pump_flag: bool = True) -> nx.DiGraph():
        """
        Args:
            graph ():

        Returns:

        """
        self.logger.info("Adding heating distribution components.")
        for node, data in graph.nodes(data=True):
            # supply line
            if data["grid_type"] == "supply_line":
                if not one_pump_flag:
                    if "distributor" == data['component_type']:
                        l_rules = "pump"
                        successors_nodes = list(graph.successors(node))
                        graph = self.add_components_on_graph(G=graph,
                                                             node=node,
                                                             l_rules=l_rules,
                                                             z_direction=False,
                                                             neighbors=successors_nodes)
                if "source" == data['node_type']:
                    l_rules = "gravity_break"
                    successors_nodes = list(graph.successors(node))
                    graph = self.add_components_on_graph(G=graph,
                                                         node=node,
                                                         l_rules=l_rules,
                                                         z_direction=True,
                                                         x_direction=False,
                                                         y_direction=False,
                                                         neighbors=successors_nodes)
                    if one_pump_flag is True:
                        l_rules = "heat_source" + "-pump-" + "safety_valve"
                    else:
                        l_rules = "heat_source"

                    predecessors_node = list(graph.predecessors(node))
                    graph = self.add_components_on_graph(G=graph,
                                                         node=node,
                                                         l_rules=l_rules,
                                                         z_direction=False,
                                                         lay_from_node=False,
                                                         neighbors=predecessors_node,
                                                         source_flag=True)
                if "delivery_node_supply" == data['node_type']:
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
                if "sink" == data['node_type']:
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
                if "delivery_node_return" == data['node_type']:
                    l_rules = "backflow_preventer"
                    successors_nodes = list(graph.successors(node))
                    graph = self.add_components_on_graph(G=graph,
                                                         node=node,
                                                         l_rules=l_rules,
                                                         z_direction=True,
                                                         x_direction=False,
                                                         y_direction=False,
                                                         neighbors=successors_nodes)


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
        """
                Fügt Komponenten auf den Graphen hinzu.
                Args:
                    G ():
                    str_chain ():
                """
        G = G.copy()
        str_chain = l_rules.split("-")
        for k, neighbor in enumerate(neighbors):

            node_list = []
            if G.nodes[node]["component_type"] in  str_chain:
                print(G.nodes[node]["component_type"])
                continue
            if lay_from_node is True:
                x2, y2, z2 = G.nodes[neighbor]["pos"]
                x1, y1, z1 = G.nodes[node]["pos"]
            else:
                x1, y1, z1 = G.nodes[neighbor]["pos"]
                x2, y2, z2 = G.nodes[node]["pos"]

            if source_flag:

                # if 'start_node' in set(G.nodes[neighbor]["type"]):
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
                                                      node_type=str_chain[i],
                                                      belongs_to_element=G.nodes[node]["belongs_to_element"],
                                                      belongs_to_room=G.nodes[node]["belongs_to_room"],
                                                      belongs_to_storey=G.nodes[node]["belongs_to_storey"],
                                                      direction=G.nodes[node]["direction"])


                    node_list.append(node_name[0])
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
                                               color=G.nodes[node]["color"],
                                               edge_type=edge_type,
                                               grid_type=grid_type)
            # Z Achse
            if z_direction is True:

                if abs(x1 - x2) <= tol_value and abs(y1 - y2) <= tol_value:
                    diff_z = (z1 - z2)
                    comp_diff = diff_z / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        #
                        z = z1 - (i + 1) * comp_diff
                        pos = (x1, y1, z)
                        G, node_name = create_graph_nodes(G,
                                                          points_list=[pos],
                                                          component_type=str_chain[i],
                                                          grid_type=G.nodes[node]["grid_type"],
                                                          color=G.nodes[node]["color"],
                                                          ID_element=G.nodes[node]["ID_element"],
                                                          element_type=G.nodes[node]["element_type"],
                                                          node_type=str_chain[i],
                                                          belongs_to_element=G.nodes[node]["belongs_to_element"],
                                                          belongs_to_room=G.nodes[node]["belongs_to_room"],
                                                          belongs_to_storey=G.nodes[node]["belongs_to_storey"],
                                                          direction=G.nodes[node]["direction"])
                        node_list.append(node_name[0])
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
                                                   color=G.nodes[node]["color"],
                                                   edge_type=edge_type,
                                                   grid_type=grid_type)

            # X Achse
            if x_direction is True:
                if abs(z1 - z2) <= tol_value and abs(y1 - y2) <= tol_value:
                    diff_x = (x1 - x2)
                    comp_diff = diff_x / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        x = x1 - (i + 1) * comp_diff
                        pos = (x, y1, z1)
                        G, node_name = create_graph_nodes(G,
                                                          points_list=[pos],
                                                          component_type=str_chain[i],
                                                          grid_type=G.nodes[node]["grid_type"],
                                                          color=G.nodes[node]["color"],
                                                          ID_element=G.nodes[node]["ID_element"],
                                                          element_type=G.nodes[node]["element_type"],
                                                          node_type=str_chain[i],
                                                          belongs_to_element=G.nodes[node]["belongs_to_element"],
                                                          belongs_to_room=G.nodes[node]["belongs_to_room"],
                                                          belongs_to_storey=G.nodes[node]["belongs_to_storey"],
                                                          direction=G.nodes[node]["direction"])
                        node_list.append(node_name[0])

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
                                                   color=G.nodes[node]["color"],
                                                   edge_type=edge_type,
                                                   grid_type=grid_type)

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
                                                          component_type=str_chain[i],
                                                          grid_type=G.nodes[node]["grid_type"],
                                                          color=G.nodes[node]["color"],
                                                          ID_element=G.nodes[node]["ID_element"],
                                                          element_type=G.nodes[node]["element_type"],
                                                          node_type=str_chain[i],
                                                          belongs_to_element=G.nodes[node]["belongs_to_element"],
                                                          belongs_to_room=G.nodes[node]["belongs_to_room"],
                                                          belongs_to_storey=G.nodes[node]["belongs_to_storey"],
                                                          direction=G.nodes[node]["direction"])
                        node_list.append(node_name[0])
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
                                                   color=G.nodes[node]["color"],
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
                            component_type: str,
                            offset: float = 0.1,
                            color: str = "blue",
                             )\
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

            if "delivery_node_supply" == data["node_type"]:
                G_reversed.nodes[node]['node_type'] = "delivery_node_return"
                G_reversed.nodes[node]['component_type'] = component_type
            if "source" == data["node_type"]:
                G_reversed.nodes[node]['node_type'] = "sink"
                G_reversed.nodes[node]['component_type'] = "coupling"
            if "distributor" == data["node_type"]:
                G_reversed.nodes[node]['node_type'] = "coupling"
                G_reversed.nodes[node]['component_type'] = "coupling"
        # Farbe der Kanten änder
        edge_attributes = {(u, v): {"color": color} for u, v in G_reversed.edges()}
        nx.set_edge_attributes(G_reversed, edge_attributes)
        return G_reversed


    def add_rise_tube(self,
                      graph: nx.DiGraph(),
                      color: str = "red",
                      edge_type: str= "rise_tube",
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
            if graph.nodes[node]["component_type"] == "distributor":
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
                              storeys: list) -> tuple[nx.Graph(), list]:
        """

        Args:
            graph ():
            source_pos ():
            storeys ():

        Returns:

        """
        source_nodes = []
        component_type = "distributor"
        grid_type = "supply_line"
        for i, st in enumerate(storeys):
            if i == 0:
                node_type = "source"
                color = "green"
            else:
                node_type = "distributor"
                color = "blue"

            positions = (source_pos[0], source_pos[1], st.position[2])
            self.logger.info(f"Set source node in storey {st} position in {positions}")
            # Create nodes
            graph, created_nodes = create_graph_nodes(graph,
                               points_list=[positions],
                               ID_element=st.guid,
                               color=color,
                               element_type="heating_element",
                               component_type=component_type,
                               direction=lay_direction([positions]),
                               node_type=node_type,
                               belongs_to_room=st.guid,
                               belongs_to_element=st.guid,
                               belongs_to_storey=st.guid,
                               grid_type=grid_type)
            source_nodes = source_nodes + created_nodes
        # create edges
        graph = snapp_nodes_to_grid(graph,
                                    pos_x_flag=True,
                                    neg_x_flag=True,
                                    pos_y_flag=True,
                                    neg_y_flag=True,
                                    color="red",
                                    filter_edge_node_element_type=["IfcWallStandardCase",
                                                                   "IfcWindow",
                                                                   "IfcDoor"],
                                    element_type="IfcWallStandardCase",
                                    edge_same_element_type_flag=False,
                                    edge_same_belongs_to_storey_flag=True,
                                    node_list=source_nodes,
                                    collision_space_flag=False,
                                    no_neighbour_collision_flag=False)
        return graph, source_nodes


    def set_delivery_nodes(self,
                           graph: nx.Graph(),
                           node_type: str = "ifc_element_node",
                           component_type: str = "radiator",
                           type_delivery: list = None) -> tuple[nx.Graph(), list]:
        """

        Args:
            node_type (): attribute node type of nodes
            component_type ():
            graph (): nx.Graph()
            type_delivery ():

        Returns:

        """
        type_delivery = type_delivery or ["IfcWindow"]
        self.logger.info(f"Type of delivery nodes: {type_delivery}")
        delivery_dict = {}
        delivery_nodes = []
        room_id_list = []
        # Return nodes with specific element_type and sort with ID_element
        for node, data in graph.nodes(data=True):
            if data["element_type"] in type_delivery and data["node_type"] == node_type:
                delivery_dict.setdefault(data["ID_element"], []).append(node)
        # Check if every room has a delivery node
        for data, data in graph.nodes(data=True):
            if data["belongs_to_room"][0] not in room_id_list:
                room_id_list.append(data["belongs_to_room"][0])
        rooms_with_delivery_node = set()
        for ID_element, nodes in delivery_dict.items():
            for node in nodes:
                if "belongs_to_room" in graph.nodes[node]:
                    rooms_with_delivery_node.add(graph.nodes[node]["belongs_to_room"][0])
        rooms_without_delivery_node = set(room_id_list) - rooms_with_delivery_node
        new_delivery_nodes = {}
        for room_id in rooms_without_delivery_node:
            found_delivery_node = False
            for node, data in graph.nodes(data=True):
                if not found_delivery_node:
                    #if "IfcDoor" in data.get("element_type", []) and room_id in data.get("belongs_to_room", []):
                    if "IfcDoor" == data["element_type"] and room_id in data.get("belongs_to_room", []):
                        new_delivery_nodes.setdefault(data["ID_element"], []).append(node)
                        found_delivery_node = True
        delivery_dict.update(new_delivery_nodes)
        # take one node of the delivery node with the same element_ID. Build a list with the other nodes.
        remove_node_list = []
        for element in delivery_dict:
            if len(delivery_dict[element]) == 1:
                delivery_node = delivery_dict[element][0]
            else:
                delivery_node = self.get_bottom_left_node(graph, delivery_dict[element])
            nx.set_node_attributes(graph, {delivery_node: {"node_type": "delivery_node_supply"}})
            nx.set_node_attributes(graph, {delivery_node: {"component_type": component_type}})
            nx.set_node_attributes(graph, {delivery_node: {"color": "red"}})
            delivery_nodes.append(delivery_node)
            for node in delivery_dict[element]:
                if node != delivery_node:
                    remove_node_list.append(node)
        # Delete the nodes in the list.
        graph.remove_nodes_from(remove_node_list)
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






