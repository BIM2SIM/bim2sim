from bim2sim.tasks.base import ITask

import networkx as nx
from pathlib import Path
import json
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.graph_functions import create_graph_nodes, \
    lay_direction, connect_nodes_with_grid, check_graph, add_graphs
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



    def run(self, building_graph, elements: dict):
        type_delivery: list = ["IfcWindow"]
        building_graph.graph["grid_type"] = "heating_graph"
        # Define delivery nodes
        G, delivery_nodes = self.set_delivery_nodes(graph=building_graph, type_delivery=type_delivery)
        start_point = (4.040, 5.990, 0)
        start_point = (5, 7, 0)
        #visulize_networkx(G, type_grid=G.graph["grid_type"])
        #plt.show()
        # Define distributor nodes
        storeys = sorted(filter_elements(elements, 'Storey'), key=lambda obj: obj.position[2])
        G, source_nodes = self.set_distributor_nodes(G, source_pos=start_point, storeys=storeys)
        check_graph(G, type=G.graph["grid_type"])

        # Calculate distribution system with Steiner Baum Tree algorithm:
        heating_graph = self.create_heating_circle(G,
                                                   storeys=storeys,
                                                   source_nodes=source_nodes,
                                                   delivery_nodes=delivery_nodes)

        return heating_graph,




    def reduce_path_nodes(self, G:nx.Graph(),
                          start_nodes: list,
                          end_nodes: list,
                          color:str ="grey",
                          ):
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

    def is_linear_path(self, G, node1, node2, node3):
        # Überprüfe, ob die Kanten gradlinig verlaufen
        x1, y1, z1 = G.nodes[node1]["pos"]
        x2, y2, z2 = G.nodes[node2]["pos"]
        x3, y3, z3 = G.nodes[node3]["pos"]
        # Z - Achse
        if x2 == x1 == x3 and y1 == y2 == y3:
            return True
        # X - Achse
        if z2 == z1 == z3 and y1 == y2 == y3:
            return True
        # Y - Achse
        if z2 == z1 == z3 and x1 == x2 == x3:
            return True
        else:
            return False

    def create_heating_circle(self,
                              G: nx.Graph(),
                              storeys: list,
                              source_nodes: list,
                              delivery_nodes: list,
                              one_pump_flag: bool = False):

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
            #visulize_networkx(subgraph, type_grid=G.graph["grid_type"])
            self.logger.info(f"Calculate distribution system in storey {st} with steinertree algorithm.")
            steinertree_nodes = []
            storey_start_nodes = []
            storey_delivery_nodes = []
            visulize_networkx(subgraph, type_grid=G.graph["grid_type"])
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
                                              grid_type="forward")

            # Check DiGraph
            self.check_directed_graph(steinertree, type_graph=steinertree.graph["grid_type"])
            steinertree_graphs.append(steinertree)

        # Creates a complete graph from subgraphs
        distributions_forward_graph = add_graphs(steinertree_graphs)
        self.add_rise_tube(graph=distributions_forward_graph)




    def add_rise_tube(self,
                      graph: nx.Graph(),
                      color: str = "red"):
        """
        Args:
            graph ():
            circulation_direction ():
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
                           type="rise_tube",
                           grid_type="forward",
                           direction="z",
                           length=length)
        return graph


    def directed_graph(self,
                       graph: nx.Graph(),
                       source_nodes,
                       edge_type: str = "forward",
                       grid_type: str = "forward",
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
            D.add_edge(edges[0], edges[1], type=edge_type, grid_type=grid_type, length=length, color=color)
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

        source_nodes = []
        for st in storeys:
            positions = (source_pos[0], source_pos[1], st.position[2])
            self.logger.info(f"Set source node in storey {st} position in {positions}")
            # Create nodes
            graph, created_nodes = create_graph_nodes(graph,
                               points_list=[positions],
                               ID_element=st.guid,
                               element_type="distributor",
                               direction=lay_direction([positions]),
                               node_type="distributor",
                               belongs_to_room=st.guid,
                               belongs_to_element=st.guid,
                               belongs_to_storey=st.guid)
            source_nodes = source_nodes + created_nodes
        # create edges
        graph = connect_nodes_with_grid(graph,
                                    #bottom_z_flag=True,
                                    #top_z_flag= True,
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
        for node, data in graph.nodes(data=True):
            if set(data["element_type"]) & set(type_delivery):
                if data["ID_element"] not in delivery_dict:
                    delivery_dict[data["ID_element"]] = []
                delivery_dict[data["ID_element"]].append(node)
        remove_node_list = []
        for element in delivery_dict:
            delivery_node = self.get_bottom_left_node(graph, delivery_dict[element])
            nx.set_node_attributes(graph, {delivery_node: {"element_type": ["delivery_node"]}})
            delivery_nodes.append(delivery_node)
            for node in delivery_dict[element]:
                if node != delivery_node:
                    remove_node_list.append(node)
        # todo: Überflüssige Nodes entfernen
        #graph.remove_nodes_from(remove_node_list)
        return graph, delivery_nodes

    def get_bottom_left_node(self, G: nx.Graph(), nodes):
        positions = nx.get_node_attributes(G, 'pos')
        # find nodes with lowest z coordinate
        z_values = {node: positions[node][2] for node in nodes}
        min_z_values = sorted(z_values.items(), key=lambda x: x[1])[:2]
        node1, z1 = min_z_values[0]
        node2, z2 = min_z_values[1]
        # Überprüfe, ob sich die Knoten in x- oder y-Richtung unterscheiden
        diff_x = positions[node1][0] - positions[node2][0]
        diff_y = positions[node1][1] - positions[node2][1]
        if diff_x > 0:
            forward_node = node2
            backward_node = node1
        elif diff_y > 0:
            forward_node = node2
            backward_node = node1
        else:
            # forward_node = node2
            # backward_node = node1
            forward_node = node1
            backward_node = node2
        return forward_node


    def steiner_tree(self, graph: nx.Graph(), term_points, grid_type: str = "forward", color: str = "red"):
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
        print(f"Steiner Tree: {grid_type} {total_length}")
        steinerbaum.graph["grid_type"] = grid_type
        # Farbe der Kanten ändern
        edge_attributes = {(u, v): {"color": color} for u, v in graph.edges()}
        nx.set_edge_attributes(graph, edge_attributes)

        return steinerbaum, total_length





    def check_graph(self, G, type):
        if nx.is_connected(G) is True:
            print(f"{Fore.BLACK + Back.GREEN} {type} Graph is connected.")
            return G
        else:
            print(f"{Fore.BLACK + Back.RED} {type} Graph is not connected.")
            GeometryBuildingsNetworkx.visulize_networkx(G=G,
                                                        type_grid=type)
            for node in G.nodes():
                if nx.is_isolate(G, node) is True:
                    print("node", node, "is not connected.")
                    print(f'{G.nodes[node]["pos"]} with type {G.nodes[node]["type"]}')
            # Bestimme die verbundenen Komponenten
            components = list(nx.connected_components(G))
            # Gib die nicht miteinander verbundenen Komponenten aus
            print("Not Conntected Components")
            G = self.kit_grid(G=G)
            if nx.is_connected(G) is True:
                print(f"{Fore.BLACK + Back.GREEN} {type} Graph is connected.")
                GeometryBuildingsNetworkx.visulize_networkx(G=G, type_grid=type)
                # plt.show()
                return G
            else:
                print(f"{Fore.BLACK + Back.RED} {type} Graph is not connected.")
                GeometryBuildingsNetworkx.visulize_networkx(G=G, type_grid=type)
                plt.show()
                exit(1)