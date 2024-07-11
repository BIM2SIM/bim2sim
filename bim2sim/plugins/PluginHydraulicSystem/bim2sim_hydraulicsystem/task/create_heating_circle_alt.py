from pathlib import Path
import json
import numpy as np
import networkx as nx
from networkx.readwrite import json_graph
from networkx.algorithms.components import is_strongly_connected
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, Point, LineString
from scipy.spatial import distance
from colorama import *
from pint import Quantity

from bim2sim.kernel.units import ureg
from bim2sim.task.base import ITask



class GetBuildingGeometry():
    """Creates a heating circle out of an ifc model"""
    def __init__(self,
                 network_building_json: Path,
                 network_heating_json: Path,
                 working_path: str,
                 ifc_model: str,
                 one_pump_flag: bool,
                 source_data,
                 create_new_graph,
                 create_heating_circle_flag,
                 ):
        self.create_new_graph = create_new_graph
        self.create_heating_circle_flag = create_heating_circle_flag
        self.network_building_json = network_building_json
        self.network_heating_json = network_heating_json
        self.working_path = working_path
        self.ifc_model = ifc_model
        self.source_data = source_data
        self.one_pump_flag = one_pump_flag

        self.building_data = self.read_buildings_json(file=ifc_building_json)
        self.delivery_data = self.read_buildings_json(file=ifc_delivery_json)
        self.floor_data = [self.building_data[floor]["height"] for floor in self.building_data]

    def run(self, G=None):

        print("Create Buildings network")
        if self.create_new_graph:
            G = self.create_building_nx_network(floor_dict_data=self.building_data,
                                                grid_type="building",
                                                color="black",
                                                tol_value=0.0)
        # Delivery points
        if G is None:
            G = self.read_json_graph(file=self.network_building_json)
        # GeometryBuildingsNetworkx.visulize_networkx(G=G, type_grid=self.ifc_model)
        # plt.show()
        if self.create_heating_circle_flag:
            forward_graph = self.create_heating_circle(G=G,
                                                       type_delivery=["window"],
                                                       grid_type="forward",
                                                       one_pump_flag=self.one_pump_flag)
            # TODO @Sven Hartmann: here you can add the call to create the
            #  ventilation system
            return forward_graph

    @staticmethod
    def read_buildings_json(file: Path = Path("buildings_json.json")):
        with open(file, "r") as datei:
            data = json.load(datei)
        return data

    @staticmethod
    def floor_heating_pipe(
            # G: nx.Graph(),
            leg_distance: float = 0.5,
            pipe_diameter: float = 0.1):
        """G = nx.Graph()
                room_coordinates = [(0, 0, 0), (5, 0, 0), (5, 3, 0), (0, 3, 0)]  # Beispiel-Koordinaten
                G.add_node(1, pos=(0, 0, 0))
                G.add_node(2, pos= (5, 0, 0))
                G.add_node(3, pos=(5, 3, 0))
                G.add_node(4, pos=(0, 3, 0))
                G.add_edge(1, 2, color="red")
                G.add_edge(2, 3, color="red")
                G.add_edge(3, 4, color="red")
                G.add_edge(4, 1, color="red")

                min_x = min([coord[0] for coord in room_coordinates])
                max_x = max([coord[0] for coord in room_coordinates])
                min_y = min([coord[1] for coord in room_coordinates])
                max_y = max([coord[1] for coord in room_coordinates])
                num_horizontal_pipes = int((max_x - min_x) / leg_distance) + 1
                print("num_horizontal_pipes", num_horizontal_pipes)
                num_vertical_pipes = int((max_y - min_y) / leg_distance) + 1
                print("num_vertical_pipes", num_vertical_pipes)
                for i in range(num_horizontal_pipes):
                    for j in range(num_vertical_pipes):
                        x = min_x + i * leg_distance

                        y = min_y + j * leg_distance
                        #print("x", x)
                        #print("y", y)
                        pos = (x,y,0)
                        G.add_node(f"{i}_pipe",pos=pos )
                        # Berechnen Sie die Länge des Rohres entsprechend der Raumgeometrie
                        length = ...  # Implementieren Sie hier die Berechnung der Rohrlänge
                        # Platzieren Sie das Rohr mit den berechneten Koordinaten und der Länge
                        # place_pipe(x, y, length)"""

        room_coordinates = {
            '1': (0, 0, 0),
            '2': (5, 0, 0),
            '3': (5, 3, 0),
            '4': (0, 3, 0),
        }

        # Verlegeabstand
        verlegeabstand = 6.5

        # Erstelle den Raumgraphen
        G = nx.Graph()
        G.add_node(1, pos=(0, 0, 0))
        G.add_node(2, pos=(5, 0, 0))
        G.add_node(3, pos=(5, 3, 0))
        G.add_node(4, pos=(0, 3, 0))
        G.add_edge(1, 2, color="red")
        G.add_edge(2, 3, color="red")
        G.add_edge(3, 4, color="red")
        G.add_edge(4, 1, color="red")
        # Füge Knoten (Raumkoordinaten) zum Graphen hinzu
        # G.add_nodes_from(room_coordinates)
        # Füge Kanten (Verlegeabstände) zwischen benachbarten Knoten hinzu
        # verlegeabstand = 0.3
        for u, attr1 in G.nodes(data=True):
            for v, attr2 in G.nodes(data=True):
                if u != v:
                    dist = ((attr1["pos"][0] - attr2["pos"][0]) ** 2 +
                            (attr1["pos"][1] - attr2["pos"][1]) ** 2) ** 0.5
                    print(dist)
                    if dist <= verlegeabstand:
                        print(dist)
                        G.add_edge(u, v, weight=dist, color="red")

        # Berechne den minimalen Spannbau
        min_spannbaum = nx.minimum_spanning_tree(G)

        # Füge Schlaufen hinzu, um den Raum abzudecken
        for u in G:
            if u not in min_spannbaum:
                # Schlaufe erstellen mit der gewünschten Länge (basierend auf dem Verlegeabstand)
                loop = [(u, v) for v in G if v != u and
                        ((room_coordinates[u][0] - room_coordinates[v][0]) ** 2 +
                         (room_coordinates[u][1] - room_coordinates[v][1]) ** 2) ** 0.5 <= verlegeabstand]
                G.add_edges_from(loop, color="blue")

        # Ausgabe des Rohrnetzwerks
        print("Rohrnetzwerk:")
        print(G.edges())

        return G

    def check_directed_graph(self, G, type_graph):
        """
                Args:
                    G ():
                    type_graph ():
                """
        # Überprüfen, ob der Graph vollständig verbunden ist
        is_connected = is_strongly_connected(G)
        if is_connected:
            print(f"Der Graph {type_graph} ist vollständig verbunden.")
        else:
            print(f"Der Graph {type_graph} ist nicht vollständig verbunden.")
            isolated_nodes = [node for node in G.nodes if G.in_degree(node) == 0 and G.out_degree(node) == 0]

    def reduce_path_nodes(self, G, color, start_nodes: list, end_nodes: list):
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
                                       type=G.nodes[node1]["direction"],
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

    def remove_nodes_from_graph(self, G, nodes_remove):
        G_copy = G.copy()
        for node in nodes_remove:
            G_copy.remove_node(node)
        if nx.is_connected(G_copy) is True:
            print("Grid is conntected.")
        else:
            print("Error: Grid is not conntected.")
            G_copy = self.kit_grid(G_copy)
        return G_copy

    def get_delivery_nodes(self,
                           G,
                           type_delivery: list = ["window"]):
        delivery_forward_points = []
        delivery_backward_points = []
        delivery_dict = self.get_type_node(G=G,
                                           type_node=type_delivery)
        edge_list = []
        # Erstelle eine Liste mit den IDs, die den Element-IDs zugeordnet sind
        for element in delivery_dict:
            forward_node, backward_node = self.get_bottom_left_node(G=G, nodes=delivery_dict[element])
            delivery_forward_points.append(forward_node)
            delivery_backward_points.append(backward_node)
            edge_list.append((forward_node, backward_node))
            nx.set_node_attributes(G, {forward_node: {'type': ['radiator_forward']}})
            nx.set_node_attributes(G, {forward_node: {'color': 'orange'}})
            nx.set_node_attributes(G, {backward_node: {'type': ['radiator_backward']}})
            nx.set_node_attributes(G, {backward_node: {'color': 'orange'}})
        return delivery_forward_points, delivery_backward_points, edge_list

    def check_neighbour_nodes_collision(self,
                                        G: nx.Graph(),
                                        edge_point_A: tuple,
                                        edge_point_B: tuple,
                                        neighbor_nodes_collision_type: list,
                                        no_neighbour_collision_flag: bool = True,
                                        same_type_flag: bool = True):
        """
                Args:
                    neighbor_nodes_collision_type (): Typ des Knotens
                    G (): Networkx Graph
                    edge_point_A (): Knoten der verbunden werden soll
                    edge_point_B (): Gesnappter Knoten an nächste Wand
                Returns:
                """
        if no_neighbour_collision_flag is False:
            return False
        for neighbor, attr in G.nodes(data=True):
            # Koordinaten eines Knotens
            point = attr["pos"]
            if point != edge_point_A:
                if set(neighbor_nodes_collision_type) & set(attr["type"]):
                    # z - Richtung
                    if edge_point_A[2] == edge_point_B[2] == point[2]:
                        p = Point(point[0], point[1])
                        line = LineString([(edge_point_A[0], edge_point_A[1]), (edge_point_B[0], edge_point_B[1])])
                        if p.intersects(line) is True:
                            return p.intersects(line)
                    # y - Richtung
                    if edge_point_A[1] == edge_point_B[1] == point[1]:
                        p = Point(point[0], point[2])
                        line = LineString([(edge_point_A[0], edge_point_A[2]), (edge_point_B[0], edge_point_B[2])])
                        if p.intersects(line) is True:
                            return p.intersects(line)
                    # X - Richtung
                    if edge_point_A[0] == edge_point_B[0] == point[0]:
                        p = Point(point[1], point[2])
                        line = LineString([(edge_point_A[1], edge_point_A[2]), (edge_point_B[1], edge_point_B[2])])
                        if p.intersects(line) is True:
                            return p.intersects(line)
        return False

    def point_on_edge(self, G, node, edges):
        """ Beispiel 3D-Punkt und 3D-Linie
                    point = Point(1, 2, 3)
                    line = LineString([(0, 0, 0), (2, 2, 2)])
                    # Überprüfung, ob der Punkt die Linie schneidet
                    if point.intersects(line):
                """
        point = G.nodes[node]['pos']
        edge_point_A = G.nodes[edges[0]]['pos']
        edge_point_B = G.nodes[edges[1]]['pos']
        # z - Richtung
        if G.has_edge(node, edges[0]) or G.has_edge(node, edges[1]) or G.has_edge(edges[0], node) or G.has_edge(
                edges[1], node):
            return False
        # z-Richtung
        if edge_point_A[2] == edge_point_B[2] == point[2]:
            p = Point(point[0], point[1])
            line = LineString([(edge_point_A[0], edge_point_A[1]), (edge_point_B[0], edge_point_B[1])])
            return p.intersects(line)
        # y - Richtung
        if edge_point_A[1] == edge_point_B[1] == point[1]:
            p = Point(point[0], point[2])
            line = LineString([(edge_point_A[0], edge_point_A[2]), (edge_point_B[0], edge_point_B[2])])
            return p.intersects(line)
        # X - Richtung
        if edge_point_A[0] == edge_point_B[0] == point[0]:
            p = Point(point[1], point[2])
            line = LineString([(edge_point_A[1], edge_point_A[2]), (edge_point_B[1], edge_point_B[2])])
            return p.intersects(line)

    def define_source_node_per_floor(self,
                                     floor_dict,
                                     color: str,
                                     type_node: str,
                                     start_source_point: tuple):
        source_dict = {}
        # print(self.source_data)
        # print(floor_dict)
        for i, floor in enumerate(floor_dict):
            _dict = {}
            pos = (start_source_point[0], start_source_point[1], floor_dict[floor]["height"])
            _dict["pos"] = pos
            _dict["type_node"] = [type_node]
            _dict["element"] = f"source_{floor}"
            _dict["color"] = color
            _dict["belongs_to"] = floor
            source_dict[floor] = _dict

            if self.source_data == pos:
                _dict["type_node"] = [type_node, "start_node"]

        return source_dict

    def get_source_nodes(self,
                         G: nx.Graph(),
                         points,
                         floor_dict: dict,
                         type,
                         connect_type_edges: list,
                         type_connect_node: list,
                         neighbor_nodes_collision_type: list,
                         edge_snapped_node_type: str,
                         remove_type_node: list,
                         grid_type: str,
                         new_edge_type: str,
                         same_type_flag: bool = True,
                         element_belongs_to_flag: bool = False
                         ):
        """
                # Source Points
                # start_point = ((4.040, 5.990, 0), (4.040, 5.990, 2.7))
                Args:
                    G ():
                    points ():
                    delivery_forward_points ():
                Returns:
                """
        # Pro Etage Source Knoten definieren
        print("Add Source Nodes")
        source_list = []
        source_dict = self.define_source_node_per_floor(floor_dict=floor_dict,
                                                        color="green",
                                                        type_node=type,
                                                        start_source_point=points)
        G = G.copy()
        # Erstellen der Source Knoten

        for floor in source_dict:
            pos = source_dict[floor]["pos"]
            color = source_dict[floor]["color"]
            type = source_dict[floor]["type_node"]
            element = source_dict[floor]["type_node"]
            G, source_node = self.create_nodes(G=G,
                                               points=pos,
                                               color="red",
                                               grid_type=grid_type,
                                               type_node=type,
                                               element=element,
                                               belongs_to=floor,
                                               direction="y",
                                               update_node=True,
                                               floor_belongs_to=floor)
            source_list.append(source_node)

        G, nodes = self.connect_nodes_with_grid(  # General
            G=G,
            node_list=source_list,
            color="grey",
            # filter_edges
            all_edges_flag=False,
            all_edges_floor_flag=False,
            same_type_flag=same_type_flag,
            belongs_to_floor=None,
            element_belongs_to_flag=element_belongs_to_flag,
            connect_type_edges=connect_type_edges,
            # nearest_edges
            top_z_flag=False,
            bottom_z_flag=False,
            pos_x_flag=True,
            neg_x_flag=True,
            pos_y_flag=True,
            neg_y_flag=True,
            tol_value=0.0,
            # create_snapped_nodes
            update_node=True,
            # check_collision
            disjoint_flag=False,
            intersects_flag=True,
            within_flag=False,
            col_tolerance=0.1,
            collision_type_node=["space"],
            collision_flag=False,
            # check_neighbour_nodes_collision
            type_node=type_connect_node,
            no_neighbour_collision_flag=False,
            neighbor_nodes_collision_type=neighbor_nodes_collision_type,
            # create_edge_snapped_nodes
            edge_snapped_node_type=edge_snapped_node_type,
            remove_type_node=remove_type_node,
            grid_type=grid_type,
            new_edge_type=new_edge_type,
            create_snapped_edge_flag=True)
        self.check_graph(G=G, type=type)
        return G, source_list

    def remove_attributes(self, G: nx.Graph(), attributes: list):
        print("Delete unnecessary attributes.")
        for node, data in G.nodes(data=True):
            if set(attributes) & set(data["type"]):
                for attr in attributes:
                    if attr in data["type"]:
                        data["type"].remove(attr)
        return G

    @staticmethod
    def connect_sources(G: nx.Graph(),
                        type_edge: str,
                        grid_type: str,
                        color: str,
                        type_units: bool = False):
        """

                Args:
                    G ():

                Returns:

                """
        element_nodes = {}
        for node, data in G.nodes(data=True):
            node_list = ["start_node", "end_node"]
            """if "Verteiler" in set(data["type"]):
                        print(data["type"])"""
            if set(node_list) & set(data["type"]):
                element = data["floor_belongs_to"]
                if element not in element_nodes:
                    element_nodes[element] = []
                element_nodes[element].append(node)
        for element, nodes in element_nodes.items():
            source_backward = nodes[0]
            source_forward = nodes[1]
            for node in nodes:
                if "backward" == G.nodes[node]["grid_type"]:
                    source_backward = node
                else:
                    source_forward = node
            if type_units is True:
                length = abs(
                    distance.euclidean(G.nodes[nodes[0]]["pos"], G.nodes[nodes[1]]["pos"])) * ureg.meter
            else:
                length = abs(
                    distance.euclidean(G.nodes[nodes[0]]["pos"], G.nodes[nodes[1]]["pos"]))

            G.add_edge(source_backward,
                       source_forward,
                       color=color,
                       type=type_edge,
                       grid_type=grid_type,
                       length=length,
                       flow_rate=0.0,
                       resistance=2.0)

        return G

    def create_heating_circle(self,
                              G: nx.Graph(),
                              grid_type: str,
                              type_delivery: list = ["window"],
                              one_pump_flag: bool = False):

        """
                Erstelle Endpunkte

                """

        delivery_forward_nodes, delivery_backward_nodes, forward_backward_edge = self.get_delivery_nodes(G=G,
                                                                                                         type_delivery=type_delivery)
        """
                Erstelle Anfangspunkte und verbinde mit Graph

                """
        nodes_forward = ["center_wall_forward",
                         "snapped_nodes",
                         "window",
                         "radiator_forward",
                         "Verteiler",
                         "door"]
        subgraph_nodes_forward = [node for node, data in G.nodes(data=True) if set(data["type"]) & set(nodes_forward)]
        forward_graph = G.subgraph(subgraph_nodes_forward)
        self.check_graph(G=forward_graph, type="forward_graph")
        forward_graph, source_forward_list = self.get_source_nodes(G=forward_graph,
                                                                   points=self.source_data,
                                                                   floor_dict=self.building_data,
                                                                   type="Verteiler",
                                                                   connect_type_edges=["center_wall_forward"],
                                                                   type_connect_node=["center_wall_forward"],
                                                                   neighbor_nodes_collision_type=[
                                                                       "center_wall_forward"],
                                                                   edge_snapped_node_type="center_wall_forward",
                                                                   remove_type_node=["center_wall_forward"],
                                                                   grid_type="forward",
                                                                   new_edge_type="center_wall_forward",
                                                                   same_type_flag=True,
                                                                   element_belongs_to_flag=False)
        self.save_networkx_json(G=forward_graph,
                                type_grid=f"delivery_points",
                                file=Path(self.working_path, self.ifc_model,
                                          f"heating_circle_floor_delivery_points.json"))
        #self.visulize_networkx(G=forward_graph, type_grid="sources")
        # plt.show()
        self.check_graph(G=forward_graph, type="forward_graph")
        ff_graph_list = []
        # pro Etage
        for i, floor in enumerate(self.building_data):
            print(f"Calculate steiner tree {floor}_{i}")
            # Pro Delivery Point pro Etage
            element_nodes_forward = []
            element_nodes_backward = []
            for delivery_node in delivery_forward_nodes:
                if forward_graph.nodes[delivery_node]["floor_belongs_to"] == floor:
                    element_nodes_forward.append(delivery_node)
            for source_node in source_forward_list:
                if forward_graph.nodes[source_node]["floor_belongs_to"] == floor:
                    element_nodes_forward.append(source_node)

            f_st, forward_total_length = self.steiner_tree(graph=forward_graph,
                                                           term_points=element_nodes_forward,
                                                           grid_type="forward")

            if forward_total_length != 0 and forward_total_length is not None:
                end_node = ["radiator_forward"]
                end_nodes = [n for n, attr in f_st.nodes(data=True) if
                             any(t in attr.get("type", []) for t in end_node)]
                f_st = self.reduce_path_nodes(G=f_st,
                                              color="red",
                                              start_nodes=[source_forward_list[i]],
                                              end_nodes=end_nodes)
                self.save_networkx_json(G=f_st,
                                        type_grid=f"heating_circle_floor_{source_forward_list[i]}",
                                        file=Path(self.working_path, self.ifc_model,
                                                  f"heating_circle_floor_{source_forward_list[i]}.json"))
                #self.visulize_networkx(G=forward_graph, type_grid="Building")
                #self.visulize_networkx(G=f_st, title="Steinerbaumpfad von den Start- zu den Endknoten",
                #                       type_grid="Vorlaufkreislauf")
                f_st = self.directed_graph(G=f_st, source_nodes=source_forward_list[i], grid_type=grid_type)
                self.visulize_networkx(G=f_st, title="Gerichterer Graph des Steinerbaumpfad",
                                       type_grid="Vorlaufkreislauf")
                # plt.show()

                self.check_directed_graph(G=f_st, type_graph=grid_type)
                ff_graph_list.append(f_st)

        f_st = self.add_graphs(graph_list=ff_graph_list)
        # Löscht überflüssige Knoten attribute
        f_st = self.remove_attributes(G=f_st, attributes=["center_wall_forward", "snapped_nodes"])
        # Add rise tube

        f_st = self.add_rise_tube(G=f_st)
        self.visulize_networkx(G=f_st, title="Vollständiger Vorkreislauf des Heizungsystems",
                               type_grid="Vorlaufkreislauf")
        self.check_graph(G=f_st, type="forward")
        # Richte Forward Graphen
        f_st = self.directed_graph(G=f_st, source_nodes=source_forward_list[0], grid_type=grid_type)
        f_st = self.update_graph(G=f_st, grid_type="forward", color="red")
        f_st = self.index_strang(G=f_st)
        # Erstelle Backward Circle
        b_st = self.create_backward(G=f_st, grid_type="backward", offset=1.0, color="blue")

        # Füge Komponenten hinzu
        composed_graph = nx.disjoint_union(f_st, b_st)
        self.visulize_networkx(G=composed_graph, title="Vollständiger Vor- und Rückkreislauf des Heizungsystems",
                               type_grid="Vorlaufkreislauf")
        composed_graph = self.connect_sources(G=composed_graph,
                                              type_edge="source",
                                              grid_type="connection",
                                              color="orange")
        composed_graph = self.connect_forward_backward(G=composed_graph,
                                                       color="orange",
                                                       edge_type="radiator",
                                                       grid_type="connection",
                                                       type_delivery=["radiator_forward", "radiator_backward"])

        self.visulize_networkx(G=composed_graph, title="Geschlossener Heizkreislauf des Heizungsystems",
                               type_grid="Vorlaufkreislauf")
        # composed_graph = f_st

        composed_graph = self.add_component_nodes(G=composed_graph, one_pump_flag=one_pump_flag)

        self.visulize_networkx(G=composed_graph, title="Geschlossener Heizkreislauf mit Komponenten des Heizungsystems",
                               type_grid="Vorlaufkreislauf")
        #CalculateDistributionSystem.plot_attributes_nodes(G=composed_graph,
        #                                                  title="Geschlossener Heizkreislauf mit Komponenten des Heizungsystems",
        #                                                  attribute=None)
        # self.visulize_networkx(G=composed_graph, type_grid="Kreislauf")
        self.save_networkx_json(G=composed_graph, file=self.network_heating_json, type_grid="heating_circle")
        # plt.show()

        return composed_graph

    def index_strang(self, G):
        """

                Args:
                    G ():
                """
        k = 0
        for node in list(nx.topological_sort(G)):
            if "Verteiler" in G.nodes[node]["type"] and G.nodes[node]["grid_type"] == "forward":
                successors = list(G.successors(node))
                for i, succ in enumerate(successors):
                    # strang = f'{i}_{node}'
                    strang = f'{k}_strang'
                    G.nodes[succ]["strang"] = strang
                    k = k + 1
            elif "Verteiler" in G.nodes[node]["type"] and G.nodes[node]["grid_type"] == "backward":
                continue
            else:
                strang = G.nodes[node]["strang"]
                successors = list(G.successors(node))
                for i, succ in enumerate(successors):
                    G.nodes[succ]["strang"] = strang
        return G

    @staticmethod
    def connect_forward_backward(G,
                                 type_delivery: list,
                                 color: str,
                                 grid_type: str,
                                 edge_type: str,
                                 type_units: float = False):
        element_nodes = {}
        for node, data in G.nodes(data=True):
            if set(type_delivery) & set(data["type"]):
                element = data["element"]
                for ele in element:
                    if ele not in element_nodes:
                        element_nodes[ele] = []
                    element_nodes[ele].append(node)
        for element, nodes in element_nodes.items():
            source_backward = nodes[0]
            source_forward = nodes[1]
            for node in nodes:
                if "backward" == G.nodes[node]["grid_type"]:
                    source_backward = node
                else:
                    source_forward = node
            length = abs(
                distance.euclidean(G.nodes[nodes[0]]["pos"], G.nodes[nodes[1]]["pos"]))  # * ureg.meter
            if type_units is True:
                length = length * ureg.meter

            G.add_edge(source_forward,
                       source_backward,
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       length=length,
                       flow_rate=0.0,
                       resistance=2.0)

        return G

    @staticmethod
    def read_json_graph(file: Path):
        print(f"Read Building Graph from file {file}")
        with open(file, "r") as file:
            json_data = json.load(file)
            G = nx.node_link_graph(json_data)
        return G

    def visualize_node_order(self, G, type_grid):
        """

                Args:
                    G ():
                """
        # Knotenpositionen
        plt.figure(figsize=(10, 8))
        # Anfangs- und Endknoten farblich markieren
        node_color = [
            'red' if "radiator_forward" in set(G.nodes[node]['type']) else 'g' if 'Verteiler' in G.nodes[node][
                'type'] else 'b'
            for node in G.nodes()]
        # Graph zeichnen
        t = nx.get_node_attributes(G, "pos")
        new_dict = {key: (x, y) for key, (x, y, z) in t.items()}
        nx.draw_networkx(G,
                         pos=new_dict,
                         node_color=node_color,
                         node_shape='o',
                         node_size=10,
                         font_size=12,
                         with_labels=False)
        plt.title(f'Graphennetzwerk vom Typ {type_grid}')
        plt.tight_layout()

    def get_bottom_left_node(self, G, nodes):
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
        return forward_node, backward_node

    def nearest_polygon_in_space(self, G, node, room_global_points, floor_flag: bool = True):
        """
                Finde die nächste Raum ebene des Punktes/Knoten.
                Args:
                    G ():
                    node ():

                Returns:
                """
        point = Point(G.nodes[node]["pos"])
        direction = G.nodes[node]["direction"]
        point_array = np.array([point.x, point.y, point.z])
        coords = np.array(room_global_points)
        poly_dict = {}
        coords_x = coords[coords[:, 0].argsort()]
        coords_y = coords[coords[:, 1].argsort()]
        coords_z = coords[coords[:, 2].argsort()]
        poly_dict["floor"] = Polygon(coords_z[4:])
        poly_dict["roof"] = Polygon(coords_z[:4])
        poly_dict["wall_x_pos"] = Polygon(coords_x[:4])
        poly_dict["wall_x_neg"] = Polygon(coords_x[4:])
        poly_dict["wall_y_pos"] = Polygon(coords_y[:4])
        poly_dict["wall_y_neg"] = Polygon(coords_y[4:])
        poly_list = []
        poly_distance_dict = {}

        for poly in poly_dict:
            # z richtung
            if floor_flag is True:
                if direction == "z":
                    if poly == "floor":
                        polygon_2d = Polygon([(point[0], point[1]) for point in Polygon(coords_z[3:]).exterior.coords])
                        minx, miny, maxx, maxy = polygon_2d.bounds
                        if point.x >= minx and point.x <= maxx and point.y >= miny and point.y <= maxy:
                            distance_z = abs(
                                point.z - poly_dict[poly].exterior.interpolate(
                                    poly_dict[poly].exterior.project(point)).z)
                            poly_list.append(poly_dict[poly])
                            poly_distance_dict[poly_dict[poly]] = distance_z
                    if poly == "roof":
                        polygon_2d = Polygon([(point[0], point[1]) for point in Polygon(coords_z[:3]).exterior.coords])
                        minx, miny, maxx, maxy = polygon_2d.bounds
                        if point.x >= minx and point.x <= maxx and point.y >= miny and point.y <= maxy:
                            distance_z = abs(
                                point.z - poly_dict[poly].exterior.interpolate(
                                    poly_dict[poly].exterior.project(point)).z)
                            poly_list.append(poly_dict[poly])
                            poly_distance_dict[poly_dict[poly]] = distance_z
            if direction == "y":
                if poly == "wall_x_pos":
                    polygon_2d = Polygon([(point[1], point[2]) for point in Polygon(coords_x[:3]).exterior.coords])
                    miny, minz, maxy, maxz = polygon_2d.bounds
                    if point.y >= miny and point.y <= maxy and point.z >= minz and point.z <= maxz:
                        distance_x = abs(
                            point.x - poly_dict[poly].exterior.interpolate(poly_dict[poly].exterior.project(point)).x)
                        poly_list.append(poly_dict[poly])
                        poly_distance_dict[poly_dict[poly]] = distance_x
                if poly == "wall_x_neg":
                    polygon_2d = Polygon([(point[1], point[2]) for point in Polygon(coords_x[3:]).exterior.coords])
                    miny, minz, maxy, maxz = polygon_2d.bounds
                    if point.y >= miny and point.y <= maxy and point.z >= minz and point.z <= maxz:
                        distance_x = abs(
                            point.x - poly_dict[poly].exterior.interpolate(poly_dict[poly].exterior.project(point)).x)
                        poly_list.append(poly_dict[poly])
                        poly_distance_dict[poly_dict[poly]] = distance_x
            if direction == "x":
                if poly == "wall_y_pos":
                    # x , z , y:konst
                    polygon_2d = Polygon([(point[0], point[2]) for point in Polygon(coords_y[:4]).exterior.coords])
                    minx, minz, maxx, maxz = polygon_2d.bounds
                    if point.x >= minx and point.x <= maxx and point.z >= minz and point.z <= maxz:
                        distance_y = abs(
                            point.y - poly_dict[poly].exterior.interpolate(poly_dict[poly].exterior.project(point)).y)
                        poly_list.append(poly_dict[poly])
                        poly_distance_dict[poly_dict[poly]] = distance_y
                if poly == "wall_y_neg":
                    polygon_2d = Polygon([(point[0], point[2]) for point in Polygon(coords_y[4:]).exterior.coords])
                    minx, minz, maxx, maxz = polygon_2d.bounds
                    if point.x >= minx and point.x <= maxx and point.z >= minz and point.z <= maxz:
                        distance_y = abs(
                            point.y - poly_dict[poly].exterior.interpolate(poly_dict[poly].exterior.project(point)).y)
                        poly_list.append(poly_dict[poly])
                        poly_distance_dict[poly_dict[poly]] = distance_y

        # rectangles_array = np.array([np.array(rectangle.exterior.coords) for rectangle in poly_list])
        # distances = np.linalg.norm(rectangles_array.mean(axis=1) - point_array, axis=1)
        # nearest_rectangle = poly_list[np.argmin(distances)]
        projected_point = None
        try:
            nearest_rectangle = min(poly_distance_dict, key=poly_distance_dict.get)
        except ValueError:
            return None
        projected_point_on_boundary = nearest_rectangle.exterior.interpolate(nearest_rectangle.exterior.project(point))

        for poly_key, poly_val in poly_dict.items():
            if nearest_rectangle == poly_val:
                if poly_key == "wall_x_pos" or poly_key == "wall_x_neg":
                    projected_point = Point(projected_point_on_boundary.x, point.y, point.z)
                if poly_key == "wall_y_pos" or poly_key == "wall_y_neg":
                    projected_point = Point(point.x, projected_point_on_boundary.y, point.z)
                if poly_key == "floor" or poly_key == "roof":
                    projected_point = Point(point.x, point.y, projected_point_on_boundary.z)

        return projected_point.coords[0]

    def sort_edge_direction(self,
                            G: nx.Graph(),
                            direction: str,
                            node: nx.Graph().nodes(),
                            tol_value: float,
                            neighbor: nx.Graph().nodes(),
                            pos_neighbors: list,
                            neg_neighbors: list):
        """
                Zieht Grade Kanten in eine Richtung X, Y oder Z Richtung.
                Args:
                    direction (): Sucht Kanten in X ,Y oder Z Richtung
                    node_pos (): Position des Knoten, der verbunden werden soll.
                    tol_value (): Toleranz bei kleinen Abweichungen in X,Y oder Z Richtungen
                    neighbor (): Potentieller benachbarter Knoten
                    pos_neighbors (): Liste von benachbarten Knoten in positiver Richtung
                    neg_neighbors (): Liste von benachbarten Knoten in negativer Richtung
                Returns:
                    pos_neighbors (): Liste von benachbarten Knoten in positiver Richtung
                    neg_neighbors (): Liste von benachbarten Knoten in negativer Richtung

                """

        neighbor_pos = G.nodes[neighbor]["pos"]
        neighbor_pos = tuple(round(coord, 2) for coord in neighbor_pos)
        node_pos = G.nodes[node]["pos"]
        node_pos = tuple(round(coord, 2) for coord in node_pos)
        # Zieht Kanten nur in X-Richtung (negativ und positiv)
        if direction == "x":
            if (neighbor_pos[0] - node_pos[0]) < 0 and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and abs(
                    neighbor_pos[2] - node_pos[2]) <= tol_value:
                pos_neighbors.append(neighbor)
            if (neighbor_pos[0] - node_pos[0]) > 0 and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and abs(
                    neighbor_pos[2] - node_pos[2]) <= tol_value:
                neg_neighbors.append(neighbor)
        # Zieht Kanten nur in Y-Richtung (negativ und positiv)
        if direction == "y":
            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and (neighbor_pos[1] - node_pos[1]) < 0 and abs(
                    neighbor_pos[2] - node_pos[2]) <= tol_value:
                pos_neighbors.append(neighbor)
            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and (neighbor_pos[1] - node_pos[1]) > 0 and abs(
                    neighbor_pos[2] - node_pos[2]) <= tol_value:
                neg_neighbors.append(neighbor)
        # Zieht Kanten nur in Z-Richtung (negativ und positiv)
        if direction == "z":
            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and (
                    neighbor_pos[2] - node_pos[2]) < 0:
                pos_neighbors.append(neighbor)
            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and (
                    neighbor_pos[2] - node_pos[2]) > 0:
                neg_neighbors.append(neighbor)
        return neg_neighbors, pos_neighbors

    def check_graph(self, G, type):
        if nx.is_connected(G) is True:
            print(f"{Fore.BLACK + Back.GREEN} {type} Graph is connected.")
            return G
        else:
            print(f"{Fore.BLACK + Back.RED} {type} Graph is not connected.")
            self.visulize_networkx(G=G,
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
                self.visulize_networkx(G=G, type_grid=type)
                # plt.show()
                return G
            else:
                print(f"{Fore.BLACK + Back.RED} {type} Graph is not connected.")
                self.visulize_networkx(G=G, type_grid=type)
                plt.show()
                exit(1)
            """for component in disconnected_components:
                        for c in component:
                            print("node", c, "is not connected.")
                            print(f'{G.nodes[c]["pos"]} with type {G.nodes[c]["type"]}')"""

            """# Erhalte die Teilgraphen
                    subgraphs = list(nx.connected_component_subgraphs(G))

                    # Sortiere die Teilgraphen basierend auf ihrer Größe
                    sorted_subgraphs = sorted(subgraphs, key=lambda x: x.number_of_nodes() + x.number_of_edges())

                    # Lösche den kleinsten Teilgraphen, wenn es mehr als einen Teilgraphen gibt
                    if len(sorted_subgraphs) > 1:
                        smallest_subgraph = sorted_subgraphs[0]
                        G.remove_nodes_from(smallest_subgraph)

                    # Überprüfe, ob der Graph komplett verbunden ist
                    is_connected = nx.is_connected(G)

                    # Gib das Ergebnis aus
                    print("Ist der Graph komplett verbunden?", is_connected)"""

    def nearest_neighbour_edge(self,
                               G: nx.Graph(),
                               node: nx.Graph().nodes(),
                               edge_type: str,
                               direction: str,
                               color: str,
                               grid_type: str,
                               tol_value: float = 0.0,
                               connect_node_list: list = None,
                               node_type: list = None,
                               connect_types: bool = False,
                               connect_node_flag: bool = False,
                               connect_element_together: bool = False,
                               nearest_node_flag: bool = True,
                               connect_floor_spaces_together: bool = False,
                               connect_types_element: bool = False,
                               disjoint_flag: bool = False,
                               intersects_flag: bool = False,
                               within_flag: bool = False,
                               col_tol: float = 0.1,
                               collision_type_node: list = ["space"],
                               all_node_flag: bool = False,
                               collision_flag: bool = True,
                               neighbor_nodes_collision_type: list = None,
                               no_neighbour_collision_flag: bool = False) -> nx.Graph():
        """
                Args:
                    G ():
                    node ():
                    edge_type ():
                    direction ():
                    color ():
                    grid_type ():
                    tol_value ():
                    connect_node_list ():
                    node_type ():
                    connect_types ():
                    connect_node_flag ():
                    connect_element_together ():
                    nearest_node_flag ():
                    connect_floor_spaces_together ():
                    disjoint_flag ():
                    intersects_flag ():
                    within_flag ():
                    col_tol ():
                    collision_type_node ():
                    all_node_flag ():
                    collision_flag ():

                Returns:
                """
        pos_neighbors = []
        neg_neighbors = []

        if connect_node_flag is True:
            for connect_node in connect_node_list:
                if connect_node != node:
                    neg_neighbors, pos_neighbors = self.sort_edge_direction(G=G,
                                                                            direction=direction,
                                                                            node=node,
                                                                            tol_value=tol_value,
                                                                            neighbor=connect_node,
                                                                            pos_neighbors=pos_neighbors,
                                                                            neg_neighbors=neg_neighbors)
        elif nearest_node_flag is True:
            for neighbor, data in G.nodes(data=True):
                if neighbor != node:
                    neighbor_pos = data["pos"]
                    if connect_element_together is True:
                        if set(G.nodes[node]["element"]) & set(data["element"]):
                            neg_neighbors, pos_neighbors = self.sort_edge_direction(G=G,
                                                                                    direction=direction,
                                                                                    node=node,
                                                                                    tol_value=tol_value,
                                                                                    neighbor=neighbor,
                                                                                    pos_neighbors=pos_neighbors,
                                                                                    neg_neighbors=neg_neighbors)
                    if connect_floor_spaces_together is True:
                        if node_type is None:
                            print(f"Define node_type {node_type}.")
                            exit(1)
                        if set(node_type) & set(G.nodes[node]["type"]) and set(node_type) & set(data["type"]):
                            if G.nodes[node]["floor_belongs_to"] == data["floor_belongs_to"]:
                                if set(G.nodes[node]["element"]).isdisjoint(set(data["element"])):
                                    neg_neighbors, pos_neighbors = self.sort_edge_direction(G=G,
                                                                                            direction=direction,
                                                                                            node=node,
                                                                                            tol_value=tol_value,
                                                                                            neighbor=neighbor,
                                                                                            pos_neighbors=pos_neighbors,
                                                                                            neg_neighbors=neg_neighbors)
                    if connect_types is True:
                        if set(node_type) & set(data["type"]):
                            neg_neighbors, pos_neighbors = self.sort_edge_direction(G=G,
                                                                                    direction=direction,
                                                                                    node=node,
                                                                                    tol_value=tol_value,
                                                                                    neighbor=neighbor,
                                                                                    pos_neighbors=pos_neighbors,
                                                                                    neg_neighbors=neg_neighbors)
                    if connect_types_element is True:
                        if set(node_type) & set(data["type"]) and set(G.nodes[node]["element"]) & set(data["element"]):
                            neg_neighbors, pos_neighbors = self.sort_edge_direction(G=G,
                                                                                    direction=direction,
                                                                                    node=node,
                                                                                    tol_value=tol_value,
                                                                                    neighbor=neighbor,
                                                                                    pos_neighbors=pos_neighbors,
                                                                                    neg_neighbors=neg_neighbors)

                    if all_node_flag is True:
                        neg_neighbors, pos_neighbors = self.sort_edge_direction(G=G,
                                                                                direction=direction,
                                                                                node=node,
                                                                                tol_value=tol_value,
                                                                                neighbor=neighbor,
                                                                                pos_neighbors=pos_neighbors,
                                                                                neg_neighbors=neg_neighbors)

        node_pos = G.nodes[node]["pos"]
        if pos_neighbors:
            nearest_neighbour = sorted(pos_neighbors, key=lambda p: distance.euclidean(G.nodes[p]["pos"], node_pos))[0]
            if nearest_neighbour is not None:
                if not G.has_edge(node, nearest_neighbour) and not G.has_edge(node, nearest_neighbour):
                    if self.check_collision(G=G,
                                            edge_point_A=G.nodes[node]["pos"],
                                            edge_point_B=G.nodes[nearest_neighbour]["pos"],
                                            disjoint_flag=disjoint_flag,
                                            collision_flag=collision_flag,
                                            intersects_flag=intersects_flag,
                                            within_flag=within_flag,
                                            tolerance=col_tol) is False:
                        if self.check_neighbour_nodes_collision(G=G,
                                                                edge_point_A=G.nodes[node]["pos"],
                                                                edge_point_B=G.nodes[nearest_neighbour]["pos"],
                                                                neighbor_nodes_collision_type=neighbor_nodes_collision_type,
                                                                no_neighbour_collision_flag=no_neighbour_collision_flag) is False:
                            length = abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos))
                            G.add_edge(node,
                                       nearest_neighbour,
                                       color=color,
                                       type=edge_type,
                                       direction=direction,
                                       grid_type=grid_type,
                                       length=length)
        if neg_neighbors:
            nearest_neighbour = sorted(neg_neighbors, key=lambda p: distance.euclidean(G.nodes[p]["pos"], node_pos))[0]
            if nearest_neighbour is not None:
                if not G.has_edge(node, nearest_neighbour) and not G.has_edge(node, nearest_neighbour):
                    if self.check_collision(G=G,
                                            edge_point_A=G.nodes[node]["pos"],
                                            edge_point_B=G.nodes[nearest_neighbour]["pos"],
                                            disjoint_flag=disjoint_flag,
                                            intersects_flag=intersects_flag,
                                            within_flag=within_flag,
                                            tolerance=col_tol,
                                            collision_flag=collision_flag,
                                            collision_type_node=collision_type_node) is False:
                        if self.check_neighbour_nodes_collision(G=G,
                                                                edge_point_A=G.nodes[node]["pos"],
                                                                edge_point_B=G.nodes[nearest_neighbour]["pos"],
                                                                neighbor_nodes_collision_type=neighbor_nodes_collision_type,
                                                                no_neighbour_collision_flag=no_neighbour_collision_flag) is False:
                            length = abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos))
                            G.add_edge(node,
                                       nearest_neighbour,
                                       color=color,
                                       type=edge_type,
                                       direction=direction,
                                       grid_type=grid_type,
                                       length=length)
        return G

    def snapped_point_on_edges(self,
                               points,
                               x_neg_lines,
                               x_pos_lines,
                               y_neg_lines,
                               y_pos_lines,
                               z_pos_lines,
                               z_neg_lines):
        """
                Args:
                    points ():
                    x_neg_lines ():
                    x_pos_lines ():
                    y_neg_lines ():
                    y_pos_lines ():
                    z_pos_lines ():
                    z_neg_lines ():
                Returns:
                """
        point = Point(points)

        nearest_pos_x_lines = min(x_pos_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][0] - point.x)) if x_pos_lines else {}

        nearest_neg_x_lines = min(x_neg_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][0] - point.x)) if x_neg_lines else {}

        nearest_pos_y_lines = min(y_pos_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][1] - point.y)) if y_pos_lines else {}
        nearest_neg_y_lines = min(y_neg_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][1] - point.y)) if y_neg_lines else {}
        nearest_pos_z_lines = min(z_pos_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][2] - point.z)) if z_pos_lines else {}

        nearest_neg_z_lines = min(z_neg_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][2] - point.z)) if z_neg_lines else {}

        new_node_neg_x = new_node_pos_x = new_node_neg_y = new_node_pos_y = new_node_neg_z = new_node_pos_z = None

        # x line: y1 = y2 , z1 = z2
        if nearest_pos_x_lines:
            # x line: y1 = y2 , z1 = z2
            new_node_pos_x = (nearest_pos_x_lines[1].coords[0][0], points[1], points[2])
        if nearest_neg_x_lines:
            new_node_neg_x = (nearest_neg_x_lines[1].coords[0][0], points[1], points[2])
        # y line: x1=x2 und z1 = z2
        if nearest_pos_y_lines:
            new_node_pos_y = (points[0], nearest_pos_y_lines[1].coords[0][1], points[2])
        if nearest_neg_y_lines:
            new_node_neg_y = (points[0], nearest_neg_y_lines[1].coords[0][1], points[2])
        # z line: x1 = x2 und y1 = y2
        if nearest_pos_z_lines:
            new_node_pos_z = (points[0], points[1], nearest_pos_z_lines[1].coords[0][2])
        if nearest_neg_z_lines:
            new_node_neg_z = (points[0], points[1], nearest_neg_z_lines[1].coords[0][2])
        return new_node_neg_x, new_node_pos_x, new_node_neg_y, new_node_pos_y, new_node_neg_z, new_node_pos_z, \
            nearest_pos_x_lines, nearest_neg_x_lines, nearest_pos_y_lines, nearest_neg_y_lines, nearest_pos_z_lines, \
            nearest_neg_z_lines

    def get_type_node(self, G, type_node, ):
        _dict = {}
        for node, data in G.nodes(data=True):
            if set(type_node) & set(data["type"]):
                for ele in data["element"]:
                    if ele in _dict:
                        _dict[ele].append(node)
                    else:
                        _dict[ele] = [node]
        return _dict

    def get_type_node_attr(self, G, type_node, attr: str = "pos"):
        ergebnis_dict = {}
        for space_node, data in G.nodes(data=True):
            if set(type_node) & set(data["type"]):
                for ele in data["element"]:
                    if ele in ergebnis_dict:
                        ergebnis_dict[ele].append(data[attr])
                    else:
                        ergebnis_dict[ele] = [data[attr]]
        return ergebnis_dict

    def check_collision(self,
                        G,
                        edge_point_A,
                        edge_point_B,
                        collision_flag: bool = True,
                        disjoint_flag: bool = False,
                        intersects_flag: bool = False,
                        within_flag: bool = False,
                        tolerance: float = 0.1,
                        collision_type_node: list = ["space"]):
        """
                Args:
                    edge_point_A ():
                    edge_point_B ():
                    disjoint_flag ():
                    intersects_flag ():
                    within_flag ():
                    tolerance ():
                    collision_type_node ():
                    G ():
                    node ():
                """
        # Definiere eine Wand als Polygon
        # Reihenfolge: belongs_to der wall_center: sind Spaces
        # alle spaces mit belongs_to durchlaufen.
        # LineString bilden
        # Kollsion über intersec ts
        if collision_flag is False:
            return False
        if disjoint_flag is False and intersects_flag is False and within_flag is False:
            return False
        ele_dict = self.get_type_node_attr(G=G,
                                           type_node=collision_type_node,
                                           attr="pos")
        room_point_dict = {}
        for i, floor_id in enumerate(self.building_data):
            for room in self.building_data[floor_id]["rooms"]:
                room_data = self.building_data[floor_id]["rooms"][room]
                room_global_corners = room_data["global_corners"]
                room_point_dict[room] = room_global_corners
        polygons = []
        for element in room_point_dict:
            points = room_point_dict[element]
            coords = np.array(points)
            if len(coords) == 8:
                coords_z = coords[coords[:, 2].argsort()]
                # Bestimme maximale und minimale Y- und X-Koordinaten
                max_y = np.max(coords_z[:, 1]) - tolerance
                min_y = np.min(coords_z[:, 1]) + tolerance
                max_x = np.max(coords_z[:, 0]) - tolerance
                min_x = np.min(coords_z[:, 0]) + tolerance
                polygon_2d = Polygon([(max_x, max_y), (min_x, max_y), (max_x, min_y), (min_x, min_y)])
                polygons.append(polygon_2d)
        snapped_line = LineString([(edge_point_A[0], edge_point_A[1]), (edge_point_B[0], edge_point_B[1])])
        snapped_line_with_tolerance = snapped_line
        for poly in polygons:
            if disjoint_flag is True:
                if snapped_line_with_tolerance.disjoint(poly):
                    return True
            elif intersects_flag is True:
                if snapped_line_with_tolerance.crosses(poly):
                    return True
                # if snapped_line_with_tolerance.intersects(poly):
                #    return True
                # if snapped_line_with_tolerance.overlaps(poly):
                #    return True
            elif within_flag is True:
                if snapped_line_with_tolerance.within(poly):
                    return True
        return False

    def center_space(self, G, tolerance: float = 0.0):
        """

                """
        room_point_dict = {}
        for i, floor_id in enumerate(self.building_data):
            for room in self.building_data[floor_id]["rooms"]:
                room_data = self.building_data[floor_id]["rooms"][room]
                room_global_corners = room_data["global_corners"]
                room_point_dict[room] = room_global_corners
        for element in room_point_dict:
            points = room_point_dict[element]
            coords = np.array(points)
            if len(coords) == 8:
                coords_z = coords[coords[:, 2].argsort()]
                # Bestimme maximale und minimale Y- und X-Koordinaten

                max_y = np.max(coords_z[:, 1]) - tolerance
                min_y = np.min(coords_z[:, 1]) + tolerance
                max_x = np.max(coords_z[:, 0]) - tolerance
                min_x = np.min(coords_z[:, 0]) + tolerance
                y = (max_y - min_y)
                x = (max_x - min_x)

    def nearest_edges(self,
                      G: nx.Graph(),
                      node: nx.Graph().nodes(),
                      points: tuple,
                      edges: list,
                      tol_value: float = 0.0,
                      bottom_z_flag: bool = False,
                      top_z_flag: bool = False,
                      pos_x_flag: bool = False,
                      neg_x_flag: bool = False,
                      pos_y_flag: bool = False,
                      neg_y_flag: bool = False):
        """
                Finde die nächste Kante für alle Rchtung in x,y,z coordinates.  Hier werden erstmal alle Kanten nach deren Richtung sortiert
                Args:
                    floors_flag ():
                    points (): Punktkoordinaten
                    z_flag (): Falls True, such auch in Z Richtung nach Kanten
                    x_flag (): Falls True, such auch in X Richtung nach Kanten
                    y_flag (): Falls True, such auch in Y Richtung nach Kanten
                    tol_value ():
                    bottom_z_flag (): Falls False, Sucht nur in negativer z richtung
                    edges (): Ausgewählte Kanten für den Punkt
                Returns:
                """

        lines_dict = {}
        for edge in edges:
            (x1, y1, z1) = G.nodes[edge[0]]["pos"]
            (x2, y2, z2) = G.nodes[edge[1]]["pos"]
            if edge[0] != node and edge[1] != node:
                if (x1, y1, z1) == (points[0], points[1], points[2]) or (x2, y2, z2) == (
                        points[0], points[1], points[2]):
                    continue
                # x line: y1 = y2 , z1 = z2
                if abs(y1 - y2) <= tol_value and abs(z1 - z2) <= tol_value:
                    # if x1 <= points[0] <= x2 or x2 <= points[0] <= x1:
                    if x1 < points[0] < x2 or x2 < points[0] < x1:
                        # Rechts und Links Kante: z1 = z2 = pz
                        if abs(z1 - points[2]) <= tol_value:
                            # left side
                            if pos_y_flag is True:
                                if points[1] > y1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                            # right side
                            if neg_y_flag is True:
                                if points[1] < y1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                        # Vertikale Kante
                        # y1 = py
                        if abs(y1 - points[1]) <= tol_value:
                            if bottom_z_flag is True:
                                if points[2] > z1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                            if top_z_flag is True:
                                if points[2] < z1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                # y line: x1 = x2 und z1 = z2
                if abs(x1 - x2) <= tol_value and abs(z1 - z2) <= tol_value:
                    # z1 = pz
                    # if y1 <= points[1] <= y2 or y2 <= points[1] <= y1:
                    if y1 < points[1] < y2 or y2 < points[1] < y1:
                        if abs(z1 - points[2]) <= tol_value:
                            # left side
                            if pos_x_flag is True:
                                if points[0] > x1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                            # right side
                            if neg_x_flag is True:
                                if points[0] < x1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                        # x1 = px
                        if abs(x1 - points[0]) <= tol_value:
                            if bottom_z_flag is True:
                                if points[2] > z1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                            if top_z_flag is True:
                                if points[2] < z1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                # z line: x1 = x2 und y1 = y2
                if abs(x1 - x2) <= tol_value and abs(y1 - y2) <= tol_value:
                    # x1 = px
                    # if z1 <= points[2] <= z2 or z2 <= points[2] <= z1:
                    if z1 < points[2] < z2 or z2 < points[2] < z1:
                        if abs(x1 - points[0]) <= tol_value:
                            if pos_y_flag is True:
                                # left side
                                if points[1] > y1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                            if neg_y_flag is True:
                                # right side
                                if points[1] < y1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                        # y1 = py
                        if abs(y1 - points[1]) <= tol_value:
                            if pos_x_flag is True:
                                # left side
                                if points[0] > x1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                            if neg_x_flag is True:
                                # right side
                                if points[0] < x1:
                                    lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
        point = Point(points)
        nearest_lines = None
        new_node_pos = None
        if pos_x_flag or neg_x_flag:
            nearest_lines = min(lines_dict.items(),
                                key=lambda item: abs(item[1].coords[0][0] - point.x)) if lines_dict else {}
            if nearest_lines:
                new_node_pos = (nearest_lines[1].coords[0][0], points[1], points[2])
        elif pos_y_flag or neg_y_flag:
            nearest_lines = min(lines_dict.items(),
                                key=lambda item: abs(item[1].coords[0][1] - point.y)) if lines_dict else {}
            if nearest_lines:
                new_node_pos = (points[0], nearest_lines[1].coords[0][1], points[2])
        elif top_z_flag or bottom_z_flag:
            nearest_lines = min(lines_dict.items(),
                                key=lambda item: abs(item[1].coords[0][2] - point.z)) if lines_dict else {}
            if nearest_lines:
                new_node_pos = (points[0], points[1], nearest_lines[1].coords[0][2])
        return nearest_lines, new_node_pos

    def add_rise_tube(self,
                      G: nx.Graph(),
                      color: str = "red"):
        """
                Args:
                    G ():
                    circulation_direction ():
                Returns:
                """
        source_dict = {}
        for node, data in G.nodes(data=True):
            if "Verteiler" in set(G.nodes[node]["type"]):
                source_dict[node] = data["pos"][2]
        sorted_dict = dict(sorted(source_dict.items(), key=lambda x: x[1]))
        keys = list(sorted_dict.keys())
        for source, target in zip(keys, keys[1:]):
            length = abs(distance.euclidean(G.nodes[source]["pos"], G.nodes[target]["pos"]))
            G.add_edge(source,
                       target,
                       color=color,
                       type="rise_tube",
                       grid_type="forward",
                       direction="z",
                       length=length)
        return G

    def delete_duplicate_nodes(self,
                               G: nx.Graph(),
                               duplicated_nodes: list):
        """
                Set der Knoten, die entfernt werden sollen, Dict zur Speicherung des Knotens mit der jeweiligen Position
                Entfernt Knoten aus einem networkx-Graphen, die dieselbe Position haben, außer einem.
                Durchlaufen Sie alle Knoten und suchen Sie nach Duplikaten
                Args:
                    G ():
                    duplicated_nodes ():
                """
        nodes_to_remove = set()
        pos_to_node = {}

        for node in duplicated_nodes:
            pos = G.nodes[node]["pos"]
            if pos in pos_to_node:
                nodes_to_remove.add(node)
            else:
                pos_to_node[pos] = node

        G.remove_nodes_from(nodes_to_remove)
        remaining_nodes = [node for node in duplicated_nodes if node in G]
        return G, remaining_nodes

    def check_point_between_edge_and_point(self, point, edge_start, edge_end):
        edge = LineString([edge_start, edge_end])
        point_distance = edge.distance(point)
        edge_length = edge.length
        if point_distance < edge_length:
            return True
        return False

    def add_new_component_nodes(self,
                                G: nx.Graph(),
                                frozen_graph,
                                node,
                                str_chain):
        """

                Args:
                    G ():
                    frozen_graph ():
                    node ():
                    str_chain ():

                Returns:

                """
        direction_flow = None
        node_dictionary = {}
        neighbors = list(G.neighbors(node))
        edges_with_node = list(G.edges(node))
        for edge in edges_with_node:
            v = G.nodes[edge[0]]['pos']
            u = G.nodes[edge[1]]['pos']
            ux = (u[0] - v[0]) / len(str_chain)
            uy = (u[1] - v[1]) / len(str_chain)
            uz = (u[2] - v[2]) / len(str_chain)
            if ux != 0:
                direction_flow = "x"
            if uy != 0:
                direction_flow = "y"
            if uz != 0:
                direction_flow = "z"
            for i in range(0, len(str_chain)):
                x = v[0] + i * ux
                y = v[1] + i * uy
                z = v[2] + i * uz
                node_dictionary[f"{edge[0]}_{str_chain[i]}_{i}"] = {"direction_flow": direction_flow},
                i = i + 1

        return node_dictionary

    def add_components_on_graph(self,
                                G,
                                node,
                                str_chain,
                                neighbors,
                                color: str,
                                grid_type: str,
                                edge_type: str,
                                strang: str,
                                lay_from_node: bool = True,
                                source_flag: bool = False,
                                tol_value: float = 0.0,
                                z_direction: bool = True,
                                x_direction: bool = True,
                                y_direction: bool = True):
        """
                Fügt Komponenten auf den Graphen hinzu.
                Args:
                    G ():
                    str_chain ():
                """
        G = G.copy()
        # Pro Strang des Knotens
        for k, neighbor in enumerate(neighbors):
            node_list = []
            if set(str_chain) & set(G.nodes[node]["type"]) or set(str_chain) & set(G.nodes[neighbor]["type"]):
                continue
            strang = G.nodes[neighbor]["strang"]
            if lay_from_node is True:
                x2, y2, z2 = G.nodes[neighbor]["pos"]
                x1, y1, z1 = G.nodes[node]["pos"]
            else:
                x1, y1, z1 = G.nodes[neighbor]["pos"]
                x2, y2, z2 = G.nodes[node]["pos"]
            # Z Achse
            if source_flag is True:
                # if 'start_node' in set(G.nodes[neighbor]["type"]):
                diff_x = (x1 - x2)
                comp_diff_x = diff_x / (len(str_chain) + 1)
                diff_y = (y1 - y2)
                comp_diff_y = diff_y / (len(str_chain) + 1)
                for i in range(0, len(str_chain)):
                    x = x1 - (i + 1) * comp_diff_x
                    y = y1 - (i + 1) * comp_diff_y
                    pos = (x, y, z1)
                    G, node_name = self.create_nodes(G=G,
                                                     points=pos,
                                                     grid_type=G.nodes[node]["grid_type"],
                                                     color=G.nodes[node]["color"],
                                                     type_node=str_chain[i],
                                                     direction=G.nodes[node]["direction"],
                                                     update_node=True,
                                                     element=G.nodes[node]["element"],
                                                     belongs_to=G.nodes[node]["belongs_to"],
                                                     strang=strang,
                                                     floor_belongs_to=G.nodes[node]["floor_belongs_to"])

                    node_list.append(node_name)
                if G.has_edge(neighbor, node):
                    G.remove_edge(neighbor, node)
                    node_list.insert(0, neighbor)
                    node_list.append(node)
                if G.has_edge(node, neighbor):
                    G.remove_edge(node, neighbor)
                    node_list.insert(0, node)
                    node_list.append(neighbor)
                G = self.create_directed_edges(G=G,
                                               node_list=node_list,
                                               color=color,
                                               edge_type=edge_type,
                                               grid_type=grid_type)
            if z_direction is True:
                if abs(x1 - x2) <= tol_value and abs(y1 - y2) <= tol_value:
                    diff_z = (z1 - z2)
                    comp_diff = diff_z / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        z = z1 - (i + 1) * comp_diff
                        pos = (x1, y1, z)
                        G, node_name = self.create_nodes(G=G,
                                                         points=pos,
                                                         grid_type=G.nodes[node]["grid_type"],
                                                         color=G.nodes[node]["color"],
                                                         type_node=str_chain[i],
                                                         direction=G.nodes[node]["direction"],
                                                         update_node=True,
                                                         element=G.nodes[node]["element"],
                                                         belongs_to=G.nodes[node]["belongs_to"],
                                                         strang=strang,
                                                         floor_belongs_to=G.nodes[node]["floor_belongs_to"])
                        node_list.append(node_name)
                    if G.has_edge(neighbor, node):
                        G.remove_edge(neighbor, node)
                        node_list.insert(0, neighbor)
                        node_list.append(node)
                    if G.has_edge(node, neighbor):
                        G.remove_edge(node, neighbor)
                        node_list.insert(0, node)
                        node_list.append(neighbor)
                    G = self.create_directed_edges(G=G,
                                                   node_list=node_list,
                                                   color=color,
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
                        G, node_name = self.create_nodes(G=G,
                                                         points=pos,
                                                         grid_type=G.nodes[node]["grid_type"],
                                                         color=G.nodes[node]["color"],
                                                         type_node=str_chain[i],
                                                         direction=G.nodes[node]["direction"],
                                                         update_node=True,
                                                         element=G.nodes[node]["element"],
                                                         strang=strang,
                                                         belongs_to=G.nodes[node]["belongs_to"],
                                                         floor_belongs_to=G.nodes[node]["floor_belongs_to"])
                        node_list.append(node_name)

                    if G.has_edge(neighbor, node):
                        G.remove_edge(neighbor, node)
                        node_list.insert(0, neighbor)
                        node_list.append(node)
                    if G.has_edge(node, neighbor):
                        G.remove_edge(node, neighbor)
                        node_list.insert(0, node)
                        node_list.append(neighbor)
                    G = self.create_directed_edges(G=G,
                                                   node_list=node_list,
                                                   color=color,
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
                        G, node_name = self.create_nodes(G=G,
                                                         grid_type=G.nodes[node]["grid_type"],
                                                         points=pos,
                                                         color=G.nodes[node]["color"],
                                                         type_node=str_chain[i],
                                                         direction=G.nodes[node]["direction"],
                                                         update_node=True,
                                                         strang=strang,
                                                         element=G.nodes[node]["element"],
                                                         belongs_to=G.nodes[node]["belongs_to"],
                                                         floor_belongs_to=G.nodes[node]["floor_belongs_to"])
                        node_list.append(node_name)
                    if G.has_edge(neighbor, node):
                        G.remove_edge(neighbor, node)
                        node_list.insert(0, neighbor)
                        node_list.append(node)
                    if G.has_edge(node, neighbor):
                        G.remove_edge(node, neighbor)
                        node_list.insert(0, node)
                        node_list.append(neighbor)
                    G = self.create_directed_edges(G=G, node_list=node_list,
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

    def add_component_nodes(self,
                            G: nx.Graph(),
                            one_pump_flag: bool = True):
        """
                Args:
                    G ():
                    color ():
                    edge_type ():
                    start_node ():
                    grid_type ():

                Returns:

                """
        grid_type = "heating_circle"
        radiator_dict = {}
        source_dict = {}
        source_nodes = None
        radiator_nodes = None
        # todo: Mischventil mit anschließend verbinden
        for node, data in G.nodes(data=True):
            if data["grid_type"] == "forward":
                color = "red"
                edge_type = "forward"
                grid_type = "forward"
            elif data["grid_type"] == "backward":
                color = "blue"
                edge_type = "backward"
                grid_type = "backward"
            else:
                color = "orange"
                edge_type = "connection"
                grid_type = "connection"
            # Update Knoten
            if G.degree[node] == 2:
                if len(list(G.successors(node))) == 1 and len(list(G.predecessors(node))) == 1:
                    radiator_list = ["radiator_backward", "radiator_forward"]
                    if not set(radiator_list) & set(G.nodes[node]["type"]):
                        in_edge = list(G.successors(node))[0]
                        out_edges = list(G.predecessors(node))[0]
                        if self.is_linear_path(G=G,
                                               node1=in_edge,
                                               node2=node,
                                               node3=out_edges) is False:
                            if "Krümmer" not in G.nodes[node]["type"]:
                                if len(G.nodes[node]["type"]) == 0:
                                    G.nodes[node]["type"] = ["Krümmer"]
                                else:
                                    G.nodes[node]["type"].append("Krümmer")

            if G.degree[node] == 3 and "Verteiler" not in G.nodes[node]["type"]:
                in_edge = list(G.successors(node))
                out_edge = list(G.predecessors(node))
                if len(in_edge) == 2 and len(out_edge) == 1:
                    if "Trennung" not in G.nodes[node]["type"]:
                        if len(G.nodes[node]["type"]) == 0:
                            G.nodes[node]["type"] = ["Trennung"]
                        else:
                            G.nodes[node]["type"].append("Trennung")
            if G.degree[node] == 3 and "Verteiler" not in G.nodes[node]["type"]:
                in_edge = list(G.successors(node))
                out_edge = list(G.predecessors(node))
                if len(in_edge) == 1 and len(out_edge) == 2:
                    if "Vereinigung" not in G.nodes[node]["type"]:
                        if len(G.nodes[node]["type"]) == 0:
                            G.nodes[node]["type"] = ["Vereinigung"]
                        else:
                            G.nodes[node]["type"].append("Vereinigung")
            if "radiator_backward" in data['type']:
                if "Entlüfter" not in G.nodes[node]["type"]:
                    G.nodes[node]["type"].append("Entlüfter")
            # Erweitere Knoten L-System
            # Forward
            strang = data["strang"]
            if one_pump_flag is False:
                type_list = ["Verteiler"]
                if set(type_list).issubset(set(data['type'])):
                    l_rules = "Pumpe"
                    str_chain = l_rules.split("-")

                    in_edge = list(G.successors(node))
                    out_edge = list(G.predecessors(node))
                    G = self.add_components_on_graph(G=G,
                                                     node=node,
                                                     str_chain=str_chain,
                                                     z_direction=False,
                                                     color=color,
                                                     edge_type=edge_type,
                                                     neighbors=in_edge,
                                                     grid_type=grid_type,
                                                     strang=strang)
            node_list = ["Verteiler", "start_node"]
            if set(node_list).issubset(set(data['type'])):
                l_rules = "Schwerkraftbremse"
                str_chain = l_rules.split("-")
                in_edge = list(G.successors(node))
                out_edge = list(G.predecessors(node))
                G = self.add_components_on_graph(G=G,
                                                 node=node,
                                                 str_chain=str_chain,
                                                 z_direction=True,
                                                 x_direction=False,
                                                 y_direction=False,
                                                 color=color,
                                                 edge_type=edge_type,
                                                 neighbors=in_edge,
                                                 grid_type=grid_type,
                                                 strang=strang)
            if "radiator_forward" in data['type']:
                l_rules = "Thermostatventil"
                str_chain = l_rules.split("-")
                in_edge = list(G.successors(node))
                out_edge = list(G.predecessors(node))
                G = self.add_components_on_graph(G=G,
                                                 node=node,
                                                 edge_type=edge_type,
                                                 str_chain=str_chain,
                                                 color=color,
                                                 z_direction=True,
                                                 x_direction=False,
                                                 y_direction=False,
                                                 neighbors=out_edge,
                                                 grid_type=grid_type,
                                                 strang=strang)
            # Backward
            node_list = ["end_node"]
            if set(node_list) & set(data['type']):
                l_rules = "Membranausdehnunggefäß" + "-Absperrschieber" + "-Schmutzfänger" + "-Absperrschieber"
                str_chain = l_rules.split("-")
                in_edge = list(G.successors(node))
                out_edge = list(G.predecessors(node))
                G = self.add_components_on_graph(G=G,
                                                 node=node,
                                                 str_chain=str_chain,
                                                 z_direction=True,
                                                 x_direction=False,
                                                 y_direction=False,
                                                 color=color,
                                                 lay_from_node=False,
                                                 edge_type=edge_type,
                                                 neighbors=out_edge,
                                                 grid_type=grid_type,
                                                 strang=strang)
            if "radiator_backward" in data['type']:
                l_rules = "Rücklaufabsperrung"
                str_chain = l_rules.split("-")
                in_edge = list(G.successors(node))
                out_edge = list(G.predecessors(node))
                G = self.add_components_on_graph(G=G,
                                                 node=node,
                                                 str_chain=str_chain,
                                                 color=color,
                                                 edge_type=edge_type,
                                                 z_direction=True,
                                                 x_direction=False,
                                                 y_direction=False,
                                                 neighbors=in_edge,
                                                 grid_type=grid_type,
                                                 strang=strang)
            # Connection
            # type_list = ["end_node"]
            type_list = ["start_node"]
            if set(type_list).issubset(set(data['type'])):
                color = "orange"
                edge_type = "connection"
                grid_type = "connection"
                # Fall eine Pumpe
                if one_pump_flag is True:
                    l_rules = "heat_source" + "-Pumpe-" + "Sicherheitsventil"
                else:
                    l_rules = "heat_source"
                str_chain = l_rules.split("-")
                in_edge = list(G.successors(node))
                out_edge = list(G.predecessors(node))
                G = self.add_components_on_graph(G=G,
                                                 node=node,
                                                 str_chain=str_chain,
                                                 z_direction=False,
                                                 color=color,
                                                 lay_from_node=False,
                                                 edge_type=edge_type,
                                                 neighbors=out_edge,
                                                 grid_type=grid_type,
                                                 source_flag=True,
                                                 strang=strang)

        return G

    def add_node_if_not_exists(self,
                               G: nx.Graph(),
                               point):
        """
                Args:
                    G ():
                    point ():
                Returns:
                """

        for n in G.nodes():
            if G.nodes[n]['pos'] == point:
                return n
        else:
            return False

    def is_node_element_on_space_path(self,
                                      G: nx.Graph(),
                                      node,
                                      node_type_on_path):
        """
                Args:
                    G ():
                    # Überprüfen, ob ein Fensterknoten eine Verbindung zu einem Spaceknoten hat
                    circulation_direction ():
                Returns:
                """
        for neighbor in G.neighbors(node):
            if G.nodes[neighbor]['type'] == node_type_on_path:
                return True
        return False

    def project_nodes_on_building(self, G: nx.Graph(), grid_type: str, node_list: list, color: str):
        """
                Projeziert Knoten die außerhalb des Gebäudes sind, auf die Gebäude Ebene und löscht den Ursprünglichen Knoten
                Args:
                    G ():
                    node_list ():
                    color ():
                    grid_type ():
                Returns:
                """
        projected_nodes = []
        room_global_points = []
        poly_nodes = self.get_space_nodes(G=G,
                                          element=G.nodes[node_list[0]]["belongs_to"],
                                          type=["space"])
        for poly in poly_nodes:
            room_global_points.append(G.nodes[poly]["pos"])
        if len(node_list) > 0 and node_list is not None:
            for i, node in enumerate(node_list):
                projected_window_point = self.nearest_polygon_in_space(G=G,
                                                                       node=node,
                                                                       room_global_points=room_global_points)

                if projected_window_point is not None:
                    type_node = G.nodes[node]["type"]
                    element = G.nodes[node]["element"]
                    belongs_to = G.nodes[node]["belongs_to"]
                    floor_id = G.nodes[node]["floor_belongs_to"]
                    direction = G.nodes[node]["direction"]
                    G, project_node = self.create_nodes(G=G,
                                                        points=projected_window_point,
                                                        color=color,
                                                        grid_type=grid_type,
                                                        direction=direction,
                                                        type_node=type_node,
                                                        element=element,
                                                        belongs_to=belongs_to,
                                                        update_node=False,
                                                        floor_belongs_to=floor_id)
                    if project_node not in projected_nodes:
                        projected_nodes.append(project_node)
                if node in G.nodes():
                    G.remove_node(node)
        return G, projected_nodes

    def create_edges(self,
                     G: nx.Graph(),
                     node_list: list,
                     edge_type: str,
                     color: str,
                     grid_type: str,
                     direction_x: bool = True,
                     direction_y: bool = True,
                     direction_z: bool = True,
                     tol_value: float = 0.0,
                     connect_floor_spaces_together: bool = False,
                     connect_types: bool = False,
                     connect_types_element: bool = False,
                     connect_element_together: bool = False,
                     nearest_node_flag: bool = True,
                     node_type: list = None,
                     connect_node_flag: bool = False,
                     connect_node_list: list = None,
                     disjoint_flag: bool = False,
                     intersects_flag: bool = True,
                     within_flag: bool = False,
                     all_node_flag: bool = False,
                     col_tol: float = 0.1,
                     collision_type_node: list = ["space"],
                     collision_flag: bool = True,
                     neighbor_nodes_collision_type: list = None,
                     no_neighbour_collision_flag: bool = False
                     ):
        """
                Args:
                    color ():
                    connect_floor_spaces_together ():
                    connect_types ():
                    connect_grid ():
                    connect_elements ():  if G.nodes[node]["element"] == data["element"]:
                    connect_element_together ():
                    nearest_node_flag ():
                    connect_all ():
                    G ():
                    node_list ():
                    edge_type ():
                    grid_type ():
                    direction_x ():
                    direction_y ():
                    direction_z ():
                    tol_value ():
                Returns:
                """
        direction_list = [direction_x, direction_y, direction_z]
        if len(node_list) > 0 or node_list is not None:
            for node in node_list:
                for i, direction in enumerate(direction_list):
                    if direction is True:
                        if i == 0:
                            direction = "x"
                        if i == 1:
                            direction = "y"
                        if i == 2:
                            direction = "z"

                        G = self.nearest_neighbour_edge(G=G,
                                                        edge_type=edge_type,
                                                        node=node,
                                                        direction=direction,
                                                        grid_type=grid_type,
                                                        tol_value=tol_value,
                                                        color=color,
                                                        connect_element_together=connect_element_together,
                                                        connect_floor_spaces_together=connect_floor_spaces_together,
                                                        connect_types=connect_types,
                                                        node_type=node_type,
                                                        connect_types_element=connect_types_element,
                                                        connect_node_flag=connect_node_flag,
                                                        connect_node_list=connect_node_list,
                                                        nearest_node_flag=nearest_node_flag,
                                                        disjoint_flag=disjoint_flag,
                                                        intersects_flag=intersects_flag,
                                                        within_flag=within_flag,
                                                        col_tol=col_tol,
                                                        collision_type_node=collision_type_node,
                                                        all_node_flag=all_node_flag,
                                                        collision_flag=collision_flag,
                                                        neighbor_nodes_collision_type=neighbor_nodes_collision_type,
                                                        no_neighbour_collision_flag=no_neighbour_collision_flag)

        return G

    def attr_node_list(self, entry, attr_list: list):
        if isinstance(attr_list, list):
            if isinstance(entry, str):
                if entry not in attr_list:
                    attr_list.append(entry)
            if isinstance(entry, list):
                for item in entry:
                    if item not in attr_list:
                        attr_list.extend(entry)
        return attr_list

    def check_attribute(self, attribute):
        attr = attribute
        if isinstance(attribute, str):
            attr = [attribute]
        if isinstance(attribute, list):
            attr = attribute
        return attr

    def generate_unique_node_id(self, G, floor_id):
        highest_id = -1
        prefix = f"floor{floor_id}_"
        for node in G.nodes:
            try:
                # if node.startswith(prefix):
                if isinstance(node, str) and node.startswith(prefix):
                    node_id = int(node[len(prefix):])
                    highest_id = max(highest_id, node_id)
            except ValueError:
                pass
        new_id = highest_id + 1
        return f"{prefix}{new_id}"

    def create_nodes(self,
                     G: nx.Graph(),
                     points: tuple,
                     color: str,
                     grid_type: str,
                     type_node: str or list,
                     element: str or list,
                     belongs_to: str or list,
                     floor_belongs_to: str,
                     direction: str,
                     tol_value: float = 0.0,
                     strang: str = None,
                     update_node: bool = True):
        """
                Check ob der Knoten auf der Position schon existiert, wenn ja, wird dieser aktualisiert.
                room_points = [room_dict[room]["global_corners"] for room in room_dict]
                room_tup_list = [tuple(p) for points in room_points for p in points]
                building_points = tuple(room_tup_list)
                Args:
                    G (): Networkx Graphen
                    points (): Punkte des Knotens in (x,y,z)
                    color ():  Farbe des Knotens
                    type_node (): Typ des Knotens
                    element (): ID des Elements
                    belongs_to (): Element des Knotens gehört zu (Space)
                    floor_belongs_to (): Element des Knotens gehört zur Etage ID
                    direction (): Richtung des Knotens bzw. des Elements
                    tol_value (): Abweichungen von der Position des Knoten
                    update_node (): Wenn ein Knoten auf der Position bereits existiert, wird dieser aktualisiert.

                Returns:
                """
        node_pos = tuple(round(coord, 2) for coord in points)
        if update_node is True:
            for node in G.nodes():
                if abs(distance.euclidean(G.nodes[node]['pos'], node_pos)) <= tol_value:
                    belongs_to_list = self.attr_node_list(entry=belongs_to,
                                                          attr_list=G.nodes[node]['belongs_to'])
                    element_list = self.attr_node_list(entry=element,
                                                       attr_list=G.nodes[node]['element'])
                    type_list = self.attr_node_list(entry=type_node,
                                                    attr_list=G.nodes[node]['type'])
                    G.nodes[node].update({
                        'element': element_list,
                        'color': color,
                        'type': type_list,
                        'direction': direction,
                        "belongs_to": belongs_to_list,
                        'strang': strang
                        # 'floor_belongs_to': floor_belongs_to
                    })
                    return G, node
        belongs = self.check_attribute(attribute=belongs_to)
        ele = self.check_attribute(attribute=element)
        type = self.check_attribute(attribute=type_node)
        id_name = self.generate_unique_node_id(G=G, floor_id=floor_belongs_to)
        G.add_node(id_name,
                   pos=node_pos,
                   color=color,
                   type=type,
                   grid_type=grid_type,
                   element=ele,
                   belongs_to=belongs,
                   direction=direction,
                   floor_belongs_to=floor_belongs_to,
                   strang=strang)
        return G, id_name

    def filter_edges(self,
                     G: nx.Graph(),
                     node: nx.Graph().nodes(),
                     connect_type_edges: list = None,
                     all_edges_flag: bool = False,
                     all_edges_floor_flag: bool = False,
                     same_type_flag: bool = False,
                     element_belongs_to_flag=False,
                     belongs_to_floor=None):
        """
                Args:
                    exception_type_node (): Beachtet explizit diese Knoten und Kanten nicht.
                    G (): Networkx Graph
                    connect_type_edges ():
                    node (): Knoten, der mit dem Graphen verbunden werden soll.
                    all_edges_flag (): Sucht alle Kanten eines Graphen
                    all_edges_floor_flag (): Sucht alle Kanten einer Etage eines Graphen
                    same_type_flag (): Sucht alle Kanten, die den gleichen Knoten Type haben (bspw. Space)
                    element_belongs_to_flag ():
                    belongs_to_floor (): ID einer Etage

                Returns:
                """
        edge_list = []
        for edge in G.edges(data=True):
            type_edge = nx.get_edge_attributes(G, 'type')[(edge[0], edge[1])]
            if edge[0] != node and edge[1] != node:
                # Beachtet alle Kanten des Graphens.
                if all_edges_flag is True:
                    if (edge[0], edge[1]) not in edge_list:
                        edge_list.append((edge[0], edge[1]))
                # Beachtet alle Kanten der Etage des Graphens.
                elif all_edges_floor_flag is True:
                    if belongs_to_floor == G.nodes[edge[0]]["floor_belongs_to"] == G.nodes[edge[1]]["floor_belongs_to"]:
                        if (edge[0], edge[1]) not in edge_list:
                            edge_list.append((edge[0], edge[1]))
                # Beachtet alle Kanten mit dem gleichen Typknoten des Graphens.
                elif same_type_flag is True:
                    if type_edge in set(connect_type_edges):
                        if (edge[0], edge[1]) not in edge_list:
                            edge_list.append((edge[0], edge[1]))
                elif element_belongs_to_flag is True:
                    if type_edge in set(connect_type_edges):
                        if set(G.nodes[edge[0]]["element"]) & set(G.nodes[edge[1]]["element"]) & set(
                                G.nodes[node]["belongs_to"]):
                            if (edge[0], edge[1]) not in edge_list:
                                edge_list.append((edge[0], edge[1]))
                        if set(G.nodes[edge[0]]["element"]) & set(G.nodes[node]["belongs_to"]) & set(
                                G.nodes[edge[1]]["belongs_to"]):
                            if (edge[0], edge[1]) not in edge_list:
                                edge_list.append((edge[0], edge[1]))
                        if set(G.nodes[edge[1]]["element"]) & set(G.nodes[edge[0]]["belongs_to"]) & set(
                                G.nodes[node]["belongs_to"]):
                            if (edge[0], edge[1]) not in edge_list:
                                edge_list.append((edge[0], edge[1]))
                        if set(G.nodes[edge[0]]["belongs_to"]) & set(G.nodes[node]["belongs_to"]) & set(
                                G.nodes[edge[1]]["belongs_to"]):
                            if (edge[0], edge[1]) not in edge_list:
                                edge_list.append((edge[0], edge[1]))
                        if set(G.nodes[edge[0]]["element"]) & set(G.nodes[node]["element"]) & set(
                                G.nodes[edge[1]]["element"]):
                            if (edge[0], edge[1]) not in edge_list:
                                edge_list.append((edge[0], edge[1]))

        return edge_list

    def filter_nodes(self,
                     G: nx.Graph(),
                     connect_node_flag: bool = False,
                     nearest_node_flag: bool = True,
                     connect_element_together: bool = False,
                     connect_floor_spaces_together: bool = False,
                     connect_types_flag: bool = False,
                     all_node_flag: bool = False):
        pass

    def create_space_grid(self,
                          G: nx.Graph(),
                          room_data,
                          room_ID,
                          color,
                          grid_type,
                          edge_type,
                          floor_belongs_to,
                          tol_value: float,
                          update_node: bool = False,
                          direction_x: bool = True,
                          direction_y: bool = True,
                          direction_z: bool = True,
                          connect_element_together: bool = True,
                          connect_floors: bool = False,
                          nearest_node_flag: bool = True,
                          node_type=None,
                          connect_node_flag: bool = False,
                          disjoint_flag: bool = False,
                          intersects_flag: bool = True,
                          within_flag: bool = False,
                          col_tol: float = 0.1,
                          collision_type_node: list = ["space"]
                          ):
        """

                Args:
                    G ():
                    room_data ():
                    room_ID ():
                    color ():
                    grid_type ():
                    edge_type ():
                    floor_belongs_to ():
                    tol_value ():
                    update_node ():
                    direction_x ():
                    direction_y ():
                    direction_z ():
                    connect_element_together ():
                    connect_floors ():
                    connect_grid ():
                    connect_elements ():
                    nearest_node_flag ():
                    connect_all ():
                    node_type ():
                    connect_node_flag ():

                Returns:

                """

        room_global_corners = room_data["global_corners"]
        room_belong_to = room_data["belongs_to"]
        direction = room_data["direction"]
        type_node = room_data["type"]
        space_nodes = []
        # Erstellt Knoten für einen Space/Wand
        if room_global_corners is not None:
            for i, points in enumerate(room_global_corners):
                G, nodes = self.create_nodes(G=G,
                                             points=points,
                                             grid_type=grid_type,
                                             color=color,
                                             type_node=type_node,
                                             element=room_ID,
                                             direction=direction,
                                             belongs_to=room_belong_to,
                                             update_node=update_node,
                                             floor_belongs_to=floor_belongs_to,
                                             tol_value=tol_value)
                if nodes not in space_nodes:
                    space_nodes.append(nodes)
            # Erstellt Kanten für einen Space
            G = self.create_edges(G=G,
                                  node_list=space_nodes,
                                  edge_type=edge_type,
                                  color=color,
                                  grid_type=grid_type,
                                  direction_x=direction_x,
                                  direction_y=direction_y,
                                  direction_z=direction_z,
                                  tol_value=tol_value,
                                  connect_element_together=connect_element_together,
                                  connect_types=connect_floors,
                                  nearest_node_flag=nearest_node_flag,
                                  node_type=node_type,
                                  connect_node_flag=connect_node_flag,
                                  connect_node_list=space_nodes,
                                  disjoint_flag=disjoint_flag,
                                  intersects_flag=intersects_flag,
                                  within_flag=within_flag,
                                  col_tol=col_tol,
                                  collision_type_node=collision_type_node)
        return G, space_nodes

    def get_space_nodes(self, G, element, type):
        room_nodes = []
        for node, data in G.nodes(data=True):
            if set(element) & set(data["element"]) and set(type) & set(data["type"]):
                room_nodes.append(node)
        return room_nodes

    def create_element_grid(self,
                            G: nx.Graph(),
                            element_data,
                            element_ID,
                            color_nodes: str,
                            color_edges: str,
                            edge_type: str,
                            grid_type: str,
                            tol_value: float,
                            floor_belongs_to,
                            connect_create_flag: bool = True):
        """

                Args:
                    G ():
                    element_data ():
                    element_ID ():
                    color ():
                    grid_type ():
                    tol_value ():
                    floor_belongs_to ():
                    connect_create_flag ():

                Returns:

                """
        element_global_corner = element_data["global_corners"]
        element_belongs_to = element_data["belongs_to"]
        type_node = element_data["type"]
        element_nodes = []
        # Punkte erstellen oder aktualisieren
        for i, points in enumerate(element_global_corner):
            G, nodes = self.create_nodes(G=G,
                                         grid_type=grid_type,
                                         points=points,
                                         color=color_nodes,
                                         type_node=type_node,
                                         element=element_ID,
                                         belongs_to=element_belongs_to,
                                         direction=element_data["direction"],
                                         floor_belongs_to=floor_belongs_to,
                                         update_node=True)
            if nodes not in element_nodes:
                element_nodes.append(nodes)
        # Projiziert Elemente Knoten (Fenster, ) auf Raum Ebene (Erstellt diese auf der Gebäude Ebene)
        G, projected_nodes = self.project_nodes_on_building(G=G,
                                                            grid_type=grid_type,
                                                            node_list=element_nodes,
                                                            color=color_nodes)
        # Löscht Knoten die aufeinander liegen
        if projected_nodes is not None and len(projected_nodes) > 0:
            G, projected_nodes = self.delete_duplicate_nodes(G=G,
                                                             duplicated_nodes=projected_nodes)
            # Erstellt Kanten für Elemente (Fenster nur untereinander)
            if connect_create_flag is True:
                G = self.create_edges(G=G,
                                      node_list=projected_nodes,
                                      edge_type=edge_type,
                                      grid_type=grid_type,
                                      tol_value=tol_value,
                                      color=color_edges,
                                      direction_x=True,
                                      direction_y=True,
                                      direction_z=True,
                                      connect_element_together=True,
                                      intersects_flag=False)
        return G, projected_nodes

    def connect_nodes_with_grid(self,
                                G: nx.Graph(),
                                node_list: list,
                                color: str,
                                type_node: list,
                                grid_type: str,
                                new_edge_type: str,
                                remove_type_node: list,
                                edge_snapped_node_type: str,
                                neighbor_nodes_collision_type: list = None,
                                belongs_to_floor=None,

                                # filter_edges
                                all_edges_flag: bool = False,
                                all_edges_floor_flag: bool = False,
                                same_type_flag: bool = False,
                                element_belongs_to_flag: bool = False,
                                connect_type_edges: list = None,
                                # snapping
                                update_node: bool = True,
                                bottom_z_flag: bool = True,
                                top_z_flag: bool = True,
                                pos_x_flag: bool = True,
                                neg_x_flag: bool = True,
                                pos_y_flag: bool = True,
                                neg_y_flag: bool = True,
                                no_neighbour_collision_flag: bool = True,
                                tol_value: float = 0.0,
                                snapped_not_same_type_flag: bool = False,
                                # collision
                                collision_type_node: list = ["space"],

                                disjoint_flag: bool = False,
                                intersects_flag: bool = False,
                                within_flag: bool = False,
                                collision_flag: bool = True,
                                col_tolerance: float = 0.1,
                                create_snapped_edge_flag: bool = True):
        """
                Args:
                    connect_type_edges (): Typ von Kanten, die betrachtet oder explizit nicht betrachtet werden sollen
                    update_node (): True: Aktualisiert Knoten, erstellt keinen Neuen Knoten, wenn auf der Position schon ein Knoten ist
                    collision_type_node (): Bspw. ["space"]
                    top_z_flag (): Falls False: Sucht nur in negativer z richtung
                    z_flag (): Betrachtet Kanten in Z-Richtung
                    x_flag (): Betrachtet Kanten in X-Richtung
                    y_flag (): Betrachtet Kanten in Y-Richtung
                    G (): Networkx Graph
                    node_list (): Liste von Knoten die mit dem Graphen verbunden werden
                    color (): Farbe der Knoten, die neu erstellt werden
                    type_node (): Typ Art der neu erstellten Knoten

                    Suchen der Kanten, auf die ein neuer Knoten gesnappt werden kann.
                    all_edges_flag (): Betrachtet alle Kanten eines Graphen G
                    all_edges_floor_flag (): Betrachtet alle Kanten der Etage eines Graphen G
                    same_type_flag (): Sucht alle Kanten, die den gleichen Knoten Type haben (bspw. Space)
                    belongs_to_floor ():

                    type_node ():

                    direction_x (): Legt Kanten Richtung X
                    direction_y (): Legt Kanten Richtung Y
                    direction_z (): Legt Kanten Richtung Z
                    disjoint_flag (): bool: Schnittstelle und auf der Kante
                    intersects_flag ():
                    within_flag (): bool. schnittstelle drinnen
                    element_belongs_to_flag ():
                    belongs_to_floor ():
                Returns:
                """

        direction_flags = [top_z_flag, bottom_z_flag, pos_x_flag, neg_x_flag, pos_y_flag, neg_y_flag]
        nodes = []
        print(f"Number of snapped nodes {len(node_list)}")
        for i, node in enumerate(node_list):
            print(f"Number node ({i + 1}/{len(node_list)})")
            # Sucht alle Kanten, auf die ein Knoten gesnappt werden kann.
            for j, direction in enumerate(direction_flags):
                direction_flags = [top_z_flag, bottom_z_flag, pos_x_flag, neg_x_flag, pos_y_flag, neg_y_flag]
                for k, flag in enumerate(direction_flags):
                    if j == k:
                        direction_flags[k] = flag
                        # Setze alle anderen Flags auf False (für jeden anderen Index k außer j)
                    else:
                        direction_flags[k] = False

                if not any(direction_flags):
                    continue
                edge_space_list = self.filter_edges(G=G,
                                                    node=node,
                                                    all_edges_flag=all_edges_flag,
                                                    all_edges_floor_flag=all_edges_floor_flag,
                                                    same_type_flag=same_type_flag,
                                                    belongs_to_floor=belongs_to_floor,
                                                    element_belongs_to_flag=element_belongs_to_flag,
                                                    connect_type_edges=connect_type_edges)
                nearest_lines, new_node_pos = self.nearest_edges(G=G,
                                                                 node=node,
                                                                 points=G.nodes[node]["pos"],
                                                                 edges=edge_space_list,
                                                                 top_z_flag=direction_flags[0],
                                                                 bottom_z_flag=direction_flags[1],
                                                                 pos_x_flag=direction_flags[2],
                                                                 neg_x_flag=direction_flags[3],
                                                                 pos_y_flag=direction_flags[4],
                                                                 neg_y_flag=direction_flags[5],
                                                                 tol_value=tol_value)
                if new_node_pos is not None:
                    direction = G.get_edge_data(nearest_lines[0][0], nearest_lines[0][1])["direction"]
                    G, id_name = self.create_snapped_nodes(G=G,
                                                           node=node,
                                                           new_snapped_node=new_node_pos,
                                                           color=color,
                                                           grid_type=grid_type,
                                                           type_node=type_node,
                                                           element=G.nodes[node]["element"],
                                                           belongs_to=G.nodes[node]["belongs_to"],
                                                           floor_belongs_to=G.nodes[node]["floor_belongs_to"],
                                                           update_node=update_node,
                                                           disjoint_flag=disjoint_flag,
                                                           intersects_flag=intersects_flag,
                                                           within_flag=within_flag,
                                                           collision_type_node=collision_type_node,
                                                           direction=direction,
                                                           col_tolerance=col_tolerance,
                                                           no_neighbour_collision_flag=no_neighbour_collision_flag,
                                                           collision_flag=collision_flag,
                                                           neighbor_nodes_collision_type=neighbor_nodes_collision_type)
                    if create_snapped_edge_flag is True and id_name is not None:
                        nodes.append(id_name)
                        G = self.create_edge_snapped_nodes(G=G,
                                                           node=node,
                                                           edge_type_node=connect_type_edges,
                                                           remove_type_node=remove_type_node,
                                                           id_name=id_name,
                                                           color=color,
                                                           edge_snapped_node_type=edge_snapped_node_type,
                                                           new_edge_type=new_edge_type,
                                                           grid_type=grid_type,
                                                           direction=direction,
                                                           snapped_edge=nearest_lines,
                                                           no_neighbour_collision_flag=no_neighbour_collision_flag,
                                                           neighbor_nodes_collision_type=neighbor_nodes_collision_type,
                                                           snapped_not_same_type_flag=snapped_not_same_type_flag)

        return G, nodes

    def create_overlapped_edge(self,
                               G: nx.Graph(),
                               connected_node: nx.Graph().nodes(),
                               edge_type: str,
                               color: str,
                               edge_1: nx.Graph().edges(),
                               edge_2: nx.Graph().edges(),
                               edge_3: nx.Graph().edges(),
                               edge_4: nx.Graph().edges(),
                               grid_type: str
                               ):
        pos = G.nodes[connected_node]["pos"]
        # edge_1
        if G.has_edge(connected_node, edge_1) is False:  # and G.has_edge(edge_1, connected_node) is False:
            length = abs(distance.euclidean(G.nodes[edge_1]["pos"], pos))
            G.add_edge(connected_node,
                       edge_1,
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       direction=G.nodes[edge_1]["direction"],
                       length=length)
        # edge_2
        if G.has_edge(edge_2, connected_node) is False:  # and G.has_edge(connected_node, edge_2) is False:
            length = abs(distance.euclidean(G.nodes[edge_2]["pos"], pos))
            G.add_edge(edge_2,
                       connected_node,
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       direction=G.nodes[edge_2]["direction"],
                       length=length)
        # edge_3
        if G.has_edge(connected_node, edge_3) is False:  # and G.has_edge(edge_3, connected_node) is False:
            length = abs(distance.euclidean(G.nodes[edge_3]["pos"], pos))
            G.add_edge(connected_node,
                       edge_3,
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       direction=G.nodes[edge_3]["direction"],
                       length=length)
        # edge_4
        if G.has_edge(connected_node, edge_4) is False:  # and G.has_edge(edge_4, connected_node) is False:
            length = abs(distance.euclidean(G.nodes[edge_4]["pos"], pos))
            G.add_edge(connected_node,
                       edge_4,
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       direction=G.nodes[edge_4]["direction"],
                       length=length)
        return G

    def delte_overlapped_edge(self,
                              G: nx.Graph(),
                              edge_1: nx.Graph().edges(),
                              edge_2: nx.Graph().edges(),
                              edge_3: nx.Graph().edges(),
                              edge_4: nx.Graph().edges()):
        """
                Args:
                    G ():
                    edge_1 ():
                    edge_2 ():
                    edge_3 ():
                    edge_4 ():
                Returns:
                """
        # Lösche alte Kanten
        if G.has_edge(edge_1, edge_2):
            G.remove_edge(edge_1, edge_2)
        if G.has_edge(edge_2, edge_1):
            G.remove_edge(edge_2, edge_1)
        if G.has_edge(edge_3, edge_4):
            G.remove_edge(edge_3, edge_4)
        if G.has_edge(edge_4, edge_3):
            G.remove_edge(edge_4, edge_3)

        return G

    def edge_overlap(self,
                     G: nx.Graph(),
                     color: str,
                     type_node: list,
                     edge_type: str,
                     delete_degree: int,
                     grid_type: str):
        """

                Args:
                    G ():
                    color ():
                    type_node ():
                    edge_type ():
                    delete_degree ():
                    grid_type ():

                Returns:

                """
        edges = list(G.edges())
        index = 0
        num_edges_before = len(edges)
        remove_node_list = []
        intersect_node_list = []
        while index < len(edges):
            edge = edges[index]
            G, node_list, intersect_node = self.create_node_on_edge_overlap(G=G,
                                                                            color=color,
                                                                            e1=edge,
                                                                            grid_type=grid_type,
                                                                            type_node=type_node,
                                                                            type_flag=True,
                                                                            edge_type=edge_type)
            if intersect_node is not None and intersect_node not in intersect_node_list:
                intersect_node_list.append(intersect_node)
            for n in node_list:
                if n not in remove_node_list:
                    remove_node_list.append(n)
            index += 1
            num_edges_after = len(G.edges())
            if num_edges_after > num_edges_before:
                # Neue Kanten wurden hinzugefügt
                new_edges = list(set(G.edges()) - set(edges))
                for new in new_edges:
                    edges.append(new)
                # Kanten wurden gelöscht
                """deleted_edges = list(set(edges) - set(G.edges()))
                        for del_edge in deleted_edges:
                            edges.remove(del_edge)"""
            num_edges_before = num_edges_after
        node_list = []
        for node in remove_node_list:
            if G.degree(node) <= delete_degree:
                edge = G.edges(node)
                for e in edge:
                    if G.nodes[e[0]]["pos"][2] == G.nodes[e[1]]["pos"][2]:
                        if G.edges[(e[0], e[1])]["length"] <= 0.3:
                            if node not in node_list:
                                node_list.append(node)
        G.remove_nodes_from(node_list)
        G = self.create_edges(G=G,
                              node_list=intersect_node_list,
                              color=color,
                              edge_type=edge_type,
                              grid_type=grid_type,
                              direction_x=False,
                              direction_y=False,
                              direction_z=True,
                              tol_value=0.0,
                              connect_types_element=False,
                              connect_element_together=False,
                              connect_types=True,
                              nearest_node_flag=True,
                              node_type=type_node,
                              connect_node_flag=False,
                              disjoint_flag=False,
                              intersects_flag=False,
                              within_flag=False
                              )

        return G

    def create_intersect_node(self,
                              G: nx.Graph(),
                              node: nx.Graph().nodes(),
                              color: str,
                              grid_type: str,
                              pos: tuple,
                              type_node: list):

        G, intersect_node = self.create_nodes(G=G,
                                              points=pos,
                                              color=color,
                                              grid_type=grid_type,
                                              type_node=type_node,
                                              element=G.nodes[node]["element"],
                                              belongs_to=G.nodes[node]["belongs_to"],
                                              direction=G.nodes[node]["direction"],
                                              update_node=True,
                                              floor_belongs_to=G.nodes[node][
                                                  "floor_belongs_to"])
        return G, intersect_node

    # def create_building_floor_nx_networkx(self):

    def create_building_nx_network(self,
                                   floor_dict_data: dict,
                                   grid_type: str,
                                   # edge_type: str,
                                   color: str = "red",
                                   laying_guide: str = "center_wall",
                                   tol_value: float = 0.0):
        """
                Args:

                    points ():
                    circulation_direction ():
                    type_node ():
                    **args ():
                Returns:
                """
        print("Creates nodes for each room independently")
        floor_graph_list = []
        for i, floor_id in enumerate(floor_dict_data):
            G = nx.Graph(grid_type="building")
            for room in floor_dict_data[floor_id]["rooms"]:
                room_data = floor_dict_data[floor_id]["rooms"][room]
                room_elements = room_data["room_elements"]
                G, space_nodes = self.create_space_grid(G=G,
                                                        room_data=room_data,
                                                        room_ID=room,
                                                        color="grey",
                                                        tol_value=tol_value,
                                                        edge_type="space",
                                                        grid_type="space",
                                                        floor_belongs_to=floor_id,
                                                        update_node=False,
                                                        direction_x=True,
                                                        direction_y=True,
                                                        direction_z=True,
                                                        connect_element_together=True,
                                                        connect_floors=False,
                                                        nearest_node_flag=True,
                                                        connect_node_flag=False,
                                                        intersects_flag=False)

                """
                        Erstellt Fenster und Tür Element von Raum r
                        """
                for element in room_elements:
                    print(f"Create element structure {element} for floor {floor_id}")
                    if room_elements[element]["type"] == "wall":
                        print(f"Create wall structure {element} for floor {floor_id}")
                        if room_elements[element]["global_corners"] is not None:
                            G, center_wall = self.center_element(G=G,
                                                                 global_corners=room_elements[element][
                                                                     "global_corners"],
                                                                 color_nodes="grey",
                                                                 color_edges="grey",
                                                                 offset=0.75,
                                                                 belongs_to=room_elements[element]["belongs_to"],
                                                                 room_ID=element,
                                                                 edge_type="center_wall_forward",
                                                                 grid_type="center_wall_forward",
                                                                 node_type=["center_wall_forward"],
                                                                 floor_belongs_to=floor_id,
                                                                 tol_value=0.0,
                                                                 update_node=True,
                                                                 direction_x=True,
                                                                 direction_y=True,
                                                                 direction_z=True)

                    if room_elements[element]["type"] == "window":
                        if room_elements[element]["global_corners"] is not None:
                            # Projiziert Knoten auf nächstes Polygon
                            G, projected_nodes = self.create_element_grid(G=G,
                                                                          edge_type="window",
                                                                          element_data=room_elements[element],
                                                                          element_ID=element,
                                                                          tol_value=tol_value,
                                                                          color_nodes="grey",
                                                                          color_edges="orange",
                                                                          grid_type=grid_type,
                                                                          floor_belongs_to=floor_id)
                            # Verbindet Projezierte Knoten über Snapping an die nächste Kante
                            if projected_nodes is not None and len(projected_nodes) > 0:
                                G, snapped_nodes = self.connect_nodes_with_grid(G=G,
                                                                                node_list=projected_nodes,
                                                                                color="grey",
                                                                                # filter_edges
                                                                                all_edges_flag=False,
                                                                                all_edges_floor_flag=False,
                                                                                same_type_flag=False,
                                                                                belongs_to_floor=None,
                                                                                element_belongs_to_flag=True,
                                                                                connect_type_edges=["space"],
                                                                                # nearest_edges
                                                                                top_z_flag=False,
                                                                                bottom_z_flag=True,
                                                                                pos_x_flag=False,
                                                                                neg_x_flag=False,
                                                                                pos_y_flag=False,
                                                                                neg_y_flag=False,
                                                                                tol_value=0.0,
                                                                                # create_snapped_nodes
                                                                                update_node=True,
                                                                                # check_collision
                                                                                disjoint_flag=False,
                                                                                intersects_flag=True,
                                                                                within_flag=False,
                                                                                col_tolerance=0.1,
                                                                                collision_type_node=["space"],
                                                                                collision_flag=True,
                                                                                # check_neighbour_nodes_collision
                                                                                # type_node=["snapped_window_nodes"],
                                                                                type_node=["snapped_nodes"],
                                                                                neighbor_nodes_collision_type=[
                                                                                    "snapped_nodes",
                                                                                    "window"],
                                                                                # create_edge_snapped_nodes
                                                                                # edge_snapped_node_type="construction_edge",
                                                                                edge_snapped_node_type="construction_edge",
                                                                                remove_type_node=["space",
                                                                                                  "snapped_nodes"],
                                                                                grid_type="forward",
                                                                                new_edge_type="space",
                                                                                create_snapped_edge_flag=True)
                    if room_elements[element]["type"] == "door":
                        if room_elements[element]["global_corners"] is not None:
                            # Projiziert Knoten auf nächstes Polygon
                            G, projected_nodes = self.create_element_grid(G=G,
                                                                          edge_type="door",
                                                                          element_data=room_elements[element],
                                                                          element_ID=element,
                                                                          tol_value=tol_value,
                                                                          color_nodes="grey",
                                                                          color_edges="green",
                                                                          grid_type=grid_type,
                                                                          floor_belongs_to=floor_id)
                            # Verbindet projizierte Knoten über Snapping an die nächste Kante
                            if projected_nodes is not None and len(projected_nodes) > 0:
                                G, snapped_nodes = self.connect_nodes_with_grid(  # General
                                    G=G,
                                    node_list=projected_nodes,
                                    color="grey",
                                    # filter_edges
                                    all_edges_flag=False,
                                    all_edges_floor_flag=False,
                                    same_type_flag=False,
                                    belongs_to_floor=None,
                                    element_belongs_to_flag=True,
                                    connect_type_edges=["space"],
                                    # nearest_edges
                                    top_z_flag=False,
                                    bottom_z_flag=True,
                                    pos_x_flag=False,
                                    neg_x_flag=False,
                                    pos_y_flag=False,
                                    neg_y_flag=False,
                                    tol_value=0.1,
                                    # create_snapped_nodes
                                    update_node=True,
                                    # check_collision
                                    disjoint_flag=False,
                                    intersects_flag=True,
                                    within_flag=False,
                                    col_tolerance=0.1,
                                    collision_type_node=["space"],
                                    collision_flag=True,
                                    # check_neighbour_nodes_collision
                                    type_node=["snapped_nodes"],
                                    neighbor_nodes_collision_type=[],
                                    snapped_not_same_type_flag=True,
                                    # create_edge_snapped_nodes
                                    edge_snapped_node_type="construction_edge",
                                    remove_type_node=["space",
                                                      "snapped_nodes"],
                                    grid_type="forward",
                                    new_edge_type="space",
                                    create_snapped_edge_flag=True)

            """
                    Entfernte überschneidene Kanten und erstellt neue
                    """
            print(f"Solve Overlapping edges for floor {floor_id}")
            G = self.edge_overlap(G=G,
                                  delete_degree=3,
                                  color="grey",
                                  type_node=["center_wall_forward"],
                                  edge_type="center_wall_forward",
                                  grid_type="forward")

            """
                    Erstelle neue Hilfsknoten Knoten miteinander
                    """
            nodes = ["center_wall_forward", "snapped_nodes"]
            snapped_nodes = []
            for node, data in G.nodes(data=True):
                if set(data["type"]) & set(nodes) and data["floor_belongs_to"] == floor_id:
                    snapped_nodes.append(node)
            G, nodes = self.connect_nodes_with_grid(G=G,
                                                    node_list=snapped_nodes,
                                                    color="grey",
                                                    # filter_edges
                                                    all_edges_flag=False,
                                                    all_edges_floor_flag=False,
                                                    same_type_flag=True,
                                                    belongs_to_floor=None,
                                                    element_belongs_to_flag=False,
                                                    connect_type_edges=["center_wall_forward"],
                                                    # nearest_edges
                                                    top_z_flag=False,
                                                    bottom_z_flag=False,
                                                    pos_x_flag=True,
                                                    neg_x_flag=True,
                                                    pos_y_flag=True,
                                                    neg_y_flag=True,
                                                    tol_value=0.0,
                                                    # create_snapped_nodes
                                                    update_node=True,
                                                    # type_node=["center_wall_forward"],
                                                    type_node=["center_wall_forward"],
                                                    # type_node=["snapped_window_nodes"],
                                                    # check_collision
                                                    disjoint_flag=False,
                                                    intersects_flag=True,
                                                    within_flag=False,
                                                    col_tolerance=0.1,
                                                    collision_type_node=["space"],
                                                    collision_flag=True,
                                                    # check_neighbour_nodes_collision
                                                    neighbor_nodes_collision_type=["space",
                                                                                   "snapped_nodes"],
                                                    # create_edge_snapped_nodes
                                                    edge_snapped_node_type="center_wall_forward",
                                                    remove_type_node=["center_wall_forward"],
                                                    grid_type="forward",
                                                    new_edge_type="center_wall_forward",
                                                    create_snapped_edge_flag=True)
            """
                    Verbinde neue Hilfsknoten mit Kanten miteinander
                    """
            print(f"Connect elements with center_wall_forward for floor {floor_id}")
            G = self.create_edges(G=G,
                                  node_list=snapped_nodes,
                                  edge_type="center_wall_forward",
                                  grid_type="forward",
                                  tol_value=tol_value,
                                  direction_x=True,
                                  direction_y=True,
                                  direction_z=True,
                                  connect_types=True,
                                  color="grey",
                                  col_tol=0.1,
                                  node_type=["center_wall_forward", "snapped_nodes"],
                                  no_neighbour_collision_flag=True,
                                  neighbor_nodes_collision_type=["space"])

            """
                    Speicher Teilgraphen als Json
                    """
            self.save_networkx_json(G=G,
                                    file=Path(self.working_path, self.ifc_model, f"{floor_id}_floor_space.json"),
                                    type_grid="floor_with_space")

            """
                    Entferne Knoten eines bestimmten Typs, Speichert diese und check anschließend ob Graph zusammenhängend ist
                    """
            nodes = ["center_wall_forward", "snapped_nodes", "door", "window"]
            subgraph_nodes = [n for n, attr in G.nodes(data=True) if any(t in attr.get("type", []) for t in nodes)]
            H = G.subgraph(subgraph_nodes)
            H = H.copy()
            attribute_type_to_remove = 'space'
            edges_to_remove = []
            for u, v, attr in H.edges(data=True):
                if attr.get('type') == attribute_type_to_remove:
                    edges_to_remove.append((u, v))
            H.remove_edges_from(edges_to_remove)
            self.save_networkx_json(G=G,
                                    file=Path(self.working_path, self.ifc_model, f"{floor_id}_floor.json"),
                                    type_grid=f"floor_{floor_id}")

            H = self.check_graph(G=H, type=f"Floor_{i}_forward")
            # GeometryBuildingsNetworkx.visulize_networkx(G=G, type_grid=self.ifc_model)
            # GeometryBuildingsNetworkx.visulize_networkx(G=H, type_grid=self.ifc_model)
            # plt.show()
            floor_graph_list.append(H)
        """
                Erstellt Hauptgraphen aus Teilgraphen
                Verbindet unzusammenhängenden Hauptgraph über zentrierte Wände
                """
        G = self.add_graphs(graph_list=floor_graph_list)
        center_wall_nodes = [n for n, attr in G.nodes(data=True) if
                             any(t in attr.get("type", []) for t in ["center_wall_forward"])]
        G = self.create_edges(G=G,
                              node_list=center_wall_nodes,
                              edge_type="center_wall_forward",
                              grid_type="forward",
                              tol_value=tol_value,
                              direction_x=False,
                              direction_y=False,
                              direction_z=True,
                              connect_types=True,
                              color="grey",
                              col_tol=0.1,
                              node_type=["center_wall_forward"])
        G = self.check_graph(G=G, type=f"Building")
        self.save_networkx_json(G=G,
                                type_grid="Building",
                                file=self.network_building_json)
        # GeometryBuildingsNetworkx.visulize_networkx(G=G, type_grid=self.ifc_model)
        # plt.show()
        return G

    def is_collision(self, point1, point2, existing_edges):
        for edge in existing_edges:
            if (point1 == edge[0] and point2 == edge[1]) or (point1 == edge[1] and point2 == edge[0]):
                return True
        return False

    def create_snapped_nodes(self,
                             G: nx.Graph(),
                             node: nx.Graph().nodes(),
                             grid_type: str,
                             new_snapped_node: tuple,
                             color: str,
                             type_node: list,
                             element: str,
                             belongs_to: str,
                             floor_belongs_to: str,
                             direction: str,
                             neighbor_nodes_collision_type: list,
                             tol_value: float = 0.0,
                             collision_type_node: list = ["space"],
                             update_node: bool = True,
                             disjoint_flag: bool = False,
                             intersects_flag: bool = True,
                             within_flag: bool = False,
                             col_tolerance: float = 0.1,
                             collision_flag: bool = True,
                             no_neighbour_collision_flag: bool = True
                             ):
        """
                Args:
                    G (): Networkx Graphen
                    node (): Knoten, der verbunden werden soll
                    new_snapped_node (): Gesnappter Knoten
                    color (): Farbe des Knoten und der Kante
                    type_node (): Typ des Knotens
                    element (): Element des Knotens
                    grid_type (): Art des Netzes
                    belongs_to (): Knoten gehört zu Hauptelement (Space)
                    floor_belongs_to (): Knoten gehört zu Etage ID
                    snapped_edge (): Linie auf die der gesnappte Knoten gesnappt werden soll
                    edge_type_node ():
                    direction_x ():
                    direction_y ():
                    direction_z ():
                    tol_value ():
                    collision_type_node ():
                    update_node ():
                    disjoint_flag ():
                    intersects_flag ():
                    within_flag ():
                    create_snapped_edge_flag ():
                    col_tolerance ():
                    collision_flag ():

                Returns:
                """
        id_name = None
        if self.check_collision(G=G,
                                edge_point_A=G.nodes[node]["pos"],
                                edge_point_B=new_snapped_node,
                                disjoint_flag=disjoint_flag,
                                intersects_flag=intersects_flag,
                                within_flag=within_flag,
                                tolerance=col_tolerance,
                                collision_type_node=collision_type_node,
                                collision_flag=collision_flag) is False:

            if self.check_neighbour_nodes_collision(G=G,
                                                    edge_point_A=G.nodes[node]["pos"],
                                                    edge_point_B=new_snapped_node,
                                                    neighbor_nodes_collision_type=neighbor_nodes_collision_type,
                                                    no_neighbour_collision_flag=no_neighbour_collision_flag) is False:
                G, id_name = self.create_nodes(G=G,
                                               points=new_snapped_node,
                                               color=color,
                                               grid_type=grid_type,
                                               type_node=type_node,
                                               element=element,
                                               belongs_to=belongs_to,
                                               floor_belongs_to=floor_belongs_to,
                                               direction=direction,
                                               tol_value=tol_value,
                                               update_node=update_node)
        return G, id_name

    def create_edge_snapped_nodes(self,
                                  G: nx.Graph(),
                                  node,
                                  remove_type_node: list,
                                  edge_type_node,
                                  id_name: str,
                                  color: str,
                                  edge_snapped_node_type: str,
                                  new_edge_type,
                                  grid_type,
                                  direction,
                                  snapped_edge,
                                  no_neighbour_collision_flag: bool = True,
                                  neighbor_nodes_collision_type: list = None,
                                  snapped_not_same_type_flag: bool = False,
                                  ):
        """

                Args:
                    G ():
                    node ():
                    edge_type_node ():
                    id_name ():
                    color ():
                    new_edge_type ():
                    grid_type ():
                    direction ():
                    snapped_edge ():

                Returns:

                """
        if G.has_edge(snapped_edge[0][0], snapped_edge[0][1]):
            G.remove_edge(snapped_edge[0][0], snapped_edge[0][1])
        if G.has_edge(snapped_edge[0][1], snapped_edge[0][0]):
            G.remove_edge(snapped_edge[0][1], snapped_edge[0][0])
        if snapped_edge[0][0] != id_name:
            G.add_edge(snapped_edge[0][0],
                       id_name,
                       color=color,
                       type=new_edge_type,
                       grid_type=grid_type,
                       direction=direction,
                       length=abs(
                           distance.euclidean(G.nodes[snapped_edge[0][0]]["pos"], G.nodes[id_name]["pos"])))
        if snapped_edge[0][1] != id_name:
            G.add_edge(id_name,
                       snapped_edge[0][1],
                       color=color,
                       type=new_edge_type,
                       grid_type=grid_type,
                       direction=direction,
                       length=abs(
                           distance.euclidean(G.nodes[snapped_edge[0][1]]["pos"], G.nodes[id_name]["pos"])))
        if snapped_not_same_type_flag is True:
            if not set(G.nodes[id_name]["type"]) & set(G.nodes[node]["type"]):
                if id_name != node:
                    G.add_edge(id_name,
                               node,
                               color=color,
                               type=edge_snapped_node_type,
                               grid_type=grid_type,
                               direction=direction,
                               length=abs(distance.euclidean(G.nodes[node]["pos"], G.nodes[id_name]["pos"])))
        else:
            if id_name != node:
                G.add_edge(id_name,
                           node,
                           color=color,
                           type=edge_snapped_node_type,
                           grid_type=grid_type,
                           direction=direction,
                           length=abs(distance.euclidean(G.nodes[node]["pos"], G.nodes[id_name]["pos"])))

        G = self.create_edges(G=G,
                              node_list=[node],
                              direction_x=True,
                              direction_y=True,
                              nearest_node_flag=True,
                              connect_types=True,
                              node_type=edge_type_node,
                              edge_type=new_edge_type,
                              color=color,
                              grid_type=grid_type,
                              no_neighbour_collision_flag=no_neighbour_collision_flag,
                              neighbor_nodes_collision_type=neighbor_nodes_collision_type)
        G = self.create_edges(G=G,
                              node_list=[id_name],
                              direction_x=True,
                              direction_y=True,
                              nearest_node_flag=True,
                              connect_types=True,
                              node_type=edge_type_node,
                              edge_type=new_edge_type,
                              color=color,
                              grid_type=grid_type,
                              no_neighbour_collision_flag=no_neighbour_collision_flag,
                              neighbor_nodes_collision_type=neighbor_nodes_collision_type
                              )
        node_list = [id_name, node]
        combined_y_list, combined_x_list, combined_z_list = [], [], []
        for node in node_list:
            G, z_list_1, x_list_1, y_list_1 = self.remove_edges_from_node(G=G,
                                                                          node=node)
            combined_y_list.extend(y_list_1)
            combined_x_list.extend(x_list_1)
            combined_z_list.extend(z_list_1)

        G = self.create_edges(G=G,
                              node_list=combined_y_list,
                              direction_x=True,
                              direction_y=True,
                              direction_z=True,
                              nearest_node_flag=True,
                              # all_node_flag=True,
                              connect_types=True,
                              node_type=remove_type_node,
                              edge_type=new_edge_type,
                              color=color,
                              grid_type=grid_type,
                              no_neighbour_collision_flag=no_neighbour_collision_flag,
                              neighbor_nodes_collision_type=neighbor_nodes_collision_type
                              )

        G = self.create_edges(G=G,
                              node_list=combined_x_list,
                              direction_x=True,
                              direction_y=True,
                              direction_z=True,
                              nearest_node_flag=True,
                              # all_node_flag=True,
                              connect_types=True,
                              node_type=remove_type_node,
                              edge_type=new_edge_type,
                              color=color,
                              grid_type=grid_type,
                              no_neighbour_collision_flag=no_neighbour_collision_flag,
                              neighbor_nodes_collision_type=neighbor_nodes_collision_type)

        G = self.create_edges(G=G,
                              node_list=combined_z_list,
                              direction_x=True,
                              direction_y=True,
                              direction_z=True,
                              nearest_node_flag=True,
                              # all_node_flag=True,
                              connect_types=True,
                              node_type=remove_type_node,
                              edge_type=new_edge_type,
                              color=color,
                              grid_type=grid_type,
                              no_neighbour_collision_flag=no_neighbour_collision_flag,
                              neighbor_nodes_collision_type=neighbor_nodes_collision_type
                              )

        return G

    def save_networkx_json(self, G, file, type_grid):
        """

                Args:
                    G ():
                    file ():
                """
        print(f"Save Networkx {G} with type {type_grid} in {file}.")
        data = json_graph.node_link_data(G)
        with open(file, 'w') as f:
            json.dump(data, f)

    def replace_edge_with_node(self,
                               node,
                               G,
                               edge_list: list,
                               color: str = "grey"):
        """
                Args:
                    edge_list ():
                    color ():
                    node ():
                    G ():
                Returns:
                """
        for edges in edge_list:
            if self.point_on_edge(G=G, node=node, edges=edges) is True:
                direction = G.get_edge_data(edges[0], edges[1])["direction"]
                grid_type = G.get_edge_data(edges[0], edges[1])["grid_type"]
                edge_type = G.get_edge_data(edges[0], edges[1])["type"]
                # G.remove_edge(edges[0], edges[1])
                G.add_edge(edges[0],
                           node,
                           color=color,
                           type=edge_type,
                           grid_type=grid_type,
                           direction=direction,
                           length=abs(distance.euclidean(G.nodes[edges[0]]["pos"], G.nodes[node]["pos"])))
                G.add_edge(edges[1],
                           node,
                           color=color,
                           type=edge_type,
                           grid_type=grid_type,
                           direction=direction,
                           length=abs(distance.euclidean(G.nodes[edges[1]]["pos"], G.nodes[node]["pos"])))
                # edge_list.remove((edges[0], edges[1]))
                edge_list.append((edges[0], node))
                edge_list.append((edges[1], node))

        return G, edge_list

    def kit_grid(self, G):
        """

                Args:
                    G ():

                Returns:

                """
        G_connected = nx.connected_components(G)
        G_largest_component = max(G_connected, key=len)
        G = G.subgraph(G_largest_component)
        for component in G_connected:
            subgraph = G.subgraph(component)
            nx.draw(subgraph, with_labels=True)
            plt.show()
        for node in G.nodes():
            if G.has_node(node):
                pass
            else:
                G_connected = nx.connected_components(G)

                G_largest_component = max(G_connected, key=len)
                G = G.subgraph(G_largest_component)
        return G

    @staticmethod
    def arrow3D(ax, x, y, z, dx, dy, dz, length, arrowstyle="-|>", color="black"):
        """

                Args:
                    ax ():
                    x ():
                    y ():
                    z ():
                    dx ():
                    dy ():
                    dz ():
                    length ():
                    arrowstyle ():
                    color ():
                """
        if length != 0:
            arrow = 0.1 / length
        else:
            arrow = 0.1 / 0.0001

        if isinstance(arrow, Quantity):
            arrow = arrow.magnitude

        ax.quiver(x, y, z, dx, dy, dz, color=color, arrow_length_ratio=arrow)
        # ax.quiver(x, y, z, dx, dy, dz, color=color, normalize=True)

    @staticmethod
    def visulize_networkx(G,
                          type_grid,
                          title: str = None, ):
        """
                [[[0.2 4.2 0.2]
                    [0.2 0.2 0.2]]
                Args:
                    G ():

                """

        # node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values()))
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values(), key=lambda x: (x[0], x[1], x[2])))
        node_colors = nx.get_node_attributes(G, "color")
        node_colors_list = [node_colors[node] for node in G.nodes()]
        # ax.scatter(*node_xyz.T, s=50, ec="w")
        # ax.scatter(*node_xyz.T, s=50, ec="w", c=node_colors_list)
        used_labels = set()
        for node, data in G.nodes(data=True):
            pos = np.array(data["pos"])
            color = data["color"]
            s = 50
            if set(["Verteiler", "radiator_forward"]) & set(data["type"]):
                label = set(["Verteiler", "radiator_forward"]) & set(data["type"])
                label = list(label)[0]
                """if label == "Verteiler":
                            label = "Startknoten"
                        if label == "radiator_forward":
                            label = "Endknoten"""
                s = 50
            else:
                s = 10
                label = None
            if label not in used_labels:
                used_labels.add(label)
                ax.scatter(*pos, s=s, ec="w", c=color, label=label)
            else:
                ax.scatter(*pos, s=s, ec="w", c=color)
            # ax.scatter(*pos.T, s=s, ec="w", c=color, label=label)

        if G.is_directed():
            for u, v in G.edges():
                edge = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos'])])
                direction = edge[0][1] - edge[0][0]
                # ax.quiver(*edge[0][0], *direction, color=G.edges[u, v]['color'])
                length = G.edges[u, v]['length']

                GetBuildingGeometry.arrow3D(ax, *edge[0][0], *direction, arrowstyle="-|>",
                                                  color=G.edges[u, v]['color'],
                                                  length=length)
        else:
            for u, v in G.edges():
                edge = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos'])])
                ax.plot(*edge.T, color=G.edges[u, v]['color'])
                # ax.plot(*edge.T, color="red")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        ax.set_xlim(0, 43)
        # Achsenlimits festlegen
        ax.set_xlim(node_xyz[:, 0].min(), node_xyz[:, 0].max())
        ax.set_ylim(node_xyz[:, 1].min(), node_xyz[:, 1].max())
        ax.set_zlim(node_xyz[:, 2].min(), node_xyz[:, 2].max())
        ax.set_box_aspect([3, 1.5, 1])
        # ax.set_box_aspect([1, 1, 1])
        ax.legend()
        if title is None:
            plt.title(f'Gebäudegraph vom Typ {type_grid}')
        else:

            plt.title(title)
        fig.tight_layout()

    def visualzation_networkx_3D(self, G, minimum_trees: list, type_grid: str):

        """

                Args:
                    G ():
                    minimum_trees ():
                """
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        # Graph Buildings G
        node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values()))
        ax.scatter(*node_xyz.T, s=1, ec="w")
        for u, v in G.edges():
            edge = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos'])])
            ax.plot(*edge.T, color=G.edges[u, v]['color'])

        # Graph Steiner Tree
        for minimum_tree in minimum_trees:
            for u, v in minimum_tree.edges():
                edge = np.array([(minimum_tree.nodes[u]['pos'], minimum_tree.nodes[v]['pos'])])
                if minimum_tree.graph["grid_type"] == "forward":
                    ax.plot(*edge.T, color="magenta")
                else:
                    ax.plot(*edge.T, color="blue")

            node_xyz = np.array(
                sorted([data["pos"] for n, data in minimum_tree.nodes(data=True) if {"radiator"} in set(data["type"])]))
            if len(node_xyz) > 0 and node_xyz is not None:
                ax.scatter(*node_xyz.T, s=10, ec="red")
            node_xyz = np.array(sorted([data["pos"][0] for n, data in minimum_tree.nodes(data=True) if
                                        set(data["type"]) not in {"heat_source"} and {"radiator"}]))
            # node_xyz = np.array(sorted([data["pos"][0] for n, data in minimum_tree.nodes(data=True) if "pos" in data]))
            if len(node_xyz) > 0 and node_xyz is not None:
                ax.scatter(node_xyz.T[0], node_xyz.T[1], node_xyz.T[2], s=100, ec="yellow")
        """for minimum_tree in minimum_trees:
                    edge_xyz = np.array([(minimum_tree.nodes[u]['pos'], minimum_tree.nodes[v]['pos']) for u, v in minimum_tree.edges()])
                    if len(edge_xyz) > 0 or edge_xyz is not None:
                        for vizedge in edge_xyz:
                            if minimum_tree.graph["grid_type"] == "forward":
                                ax.plot(*vizedge.T, color="tab:red")
                            else:
                                ax.plot(*vizedge.T, color="blue")"""
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        plt.title(f'Graphennetzwerk vom typ {type_grid}')
        fig.tight_layout()

    def create_node_on_edge_overlap(self,
                                    G: nx.Graph(),
                                    color: str,
                                    e1: nx.Graph().edges(),
                                    grid_type: str,
                                    type_node: list,
                                    edge_type: str,
                                    tolerance: float = 0.1,
                                    type_flag: bool = False):
        """

                Args:
                    G ():
                    color ():
                    type_node ():
                    connect_projected_node_flag ():
                    type_flag ():
                    all_edges_flag ():

                Returns:

                """
        # Iteriere über alle Kantenpaare
        #
        nodes = []
        intersect_node = None
        if G.has_edge(e1[0], e1[1]) is True:
            type_connect_edge = G.edges[(e1[0], e1[1])]["type"]
            for e2 in G.edges(data=True):
                if e2 != e1:
                    if G.nodes[e1[0]]['pos'][2] == G.nodes[e1[1]]['pos'][2] == G.nodes[e2[0]]['pos'][2] == \
                            G.nodes[e2[1]]['pos'][2]:
                        type_edge = G.edges[(e2[0], e2[1])]["type"]
                        if type_flag is True:
                            if type_connect_edge == type_edge == edge_type:
                                l1 = LineString([G.nodes[e1[0]]['pos'][0:2], G.nodes[e1[1]]['pos'][0:2]])
                                l2 = LineString([G.nodes[e2[0]]['pos'][0:2], G.nodes[e2[1]]['pos'][0:2]])
                                if l1.crosses(l2):
                                    intersection = l1.intersection(l2)
                                    pos = (intersection.x, intersection.y, G.nodes[e2[0]]['pos'][2])
                                    G, intersect_node = self.create_intersect_node(G=G,
                                                                                   grid_type=grid_type,
                                                                                   node=e1[0],
                                                                                   color=color,
                                                                                   pos=pos,
                                                                                   type_node=type_node)
                                    G = self.delte_overlapped_edge(G=G,
                                                                   edge_1=e1[0],
                                                                   edge_2=e1[1],
                                                                   edge_3=e2[0],
                                                                   edge_4=e2[1])

                                    # Erstellt neue Kanten zwischen neuen Knoten und den alten Knoten
                                    G = self.create_overlapped_edge(G=G,
                                                                    connected_node=intersect_node,
                                                                    edge_type=edge_type,
                                                                    edge_1=e1[0],
                                                                    edge_2=e1[1],
                                                                    edge_3=e2[0],
                                                                    edge_4=e2[1],
                                                                    color=color,
                                                                    grid_type=grid_type)

                                    if e1[0] not in nodes:
                                        nodes.append(e1[0])
                                    if e1[1] not in nodes:
                                        nodes.append(e1[1])
                                    if e2[0] not in nodes:
                                        nodes.append(e2[0])
                                    if e2[1] not in nodes:
                                        nodes.append(e2[1])

                                    return G, nodes, intersect_node

        return G, nodes, intersect_node

    def center_points(self,
                      global_corners: list,
                      offset: float):
        """

                Args:
                    global_corners ():
                    offset ():

                Returns:

                """
        x_coords = [point[0] for point in global_corners]
        y_coords = [point[1] for point in global_corners]
        z_coords = [point[2] for point in global_corners]
        z_min = np.min(z_coords)
        z_max = np.max(z_coords)
        x_diff = np.max(x_coords) - np.min(x_coords)
        y_diff = np.max(y_coords) - np.min(y_coords)

        if x_diff > y_diff:
            direction = "x"
            y = y_diff * offset + np.min(y_coords)
            point_1 = (np.max(x_coords), y, z_min)
            point_2 = (np.min(x_coords), y, z_min)
            point_3 = (np.max(x_coords), y, z_max)
            point_4 = (np.min(x_coords), y, z_max)
        else:
            direction = "y"
            x = (x_diff * offset) + np.min(x_coords)
            point_1 = (x, np.max(y_coords), z_min)
            point_2 = (x, np.min(y_coords), z_min)
            point_3 = (x, np.max(y_coords), z_max)
            point_4 = (x, np.min(y_coords), z_max)
        point_list = []
        point_list.append(point_1)
        point_list.append(point_2)
        point_list.append(point_3)
        point_list.append(point_4)
        return direction, point_list

    def center_element(self,
                       G: nx.Graph(),
                       global_corners: list,
                       color_nodes: str,
                       color_edges: str,
                       offset: float,
                       belongs_to: str,
                       room_ID: str,
                       edge_type: str,
                       grid_type: str,
                       node_type: list,
                       floor_belongs_to: str,
                       tol_value: float = 0.0,
                       update_node: bool = True,
                       direction_x: bool = True,
                       direction_y: bool = True,
                       direction_z: bool = True,
                       ):
        """

                Args:
                    G (): Networkx Graph.
                    global_corners (): Punkte des Element.
                    color (): Farbe der Knoten und Kanten.
                    offset (): Verschiebung der Knoten um Offset.
                    belongs_to (): Element gehört zu Space.
                    room_ID (): ID des Elements.
                    edge_type (): Typ der Kante.
                    grid_type (): Art des Netwerkes
                    node_type (): Typ des Knotens.
                    floor_belongs_to (): Element gehört zu Etage (ID)
                    update_node (): Aktualisert Knoten, falls dieser auf der Positon vorhanden ist.

                Returns:

                """
        direction, point_list = self.center_points(global_corners=global_corners,
                                                   offset=offset)
        node_list = []
        for i, point in enumerate(point_list):
            G, center_node = self.create_nodes(G=G,
                                               grid_type=grid_type,
                                               points=point,
                                               color=color_nodes,
                                               type_node=node_type,
                                               element=room_ID,
                                               belongs_to=belongs_to,
                                               direction=direction,
                                               tol_value=tol_value,
                                               update_node=update_node,
                                               floor_belongs_to=floor_belongs_to)
            node_list.append(center_node)
        G = self.create_edges(G=G,
                              node_list=node_list,
                              edge_type=edge_type,
                              color=color_edges,
                              grid_type=grid_type,
                              direction_x=direction_x,
                              direction_y=direction_y,
                              direction_z=direction_z,
                              tol_value=0.0,
                              connect_types_element=True,
                              connect_element_together=False,
                              connect_types=False,
                              nearest_node_flag=True,
                              node_type=node_type,
                              connect_node_flag=False,
                              disjoint_flag=False,
                              intersects_flag=False,
                              within_flag=False)

        return G, node_list

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

    def spanning_tree(self, graph: nx.DiGraph(), start, end_points):
        """

                    graph ():
                    start ():
                    end_points ():

                Returns:

                """
        shortest_paths = {}
        for end_node in end_points:
            shortest_path = nx.dijkstra_path(graph, start, end_node)
            shortest_paths[end_node] = shortest_path
        T = nx.Graph()
        for end_node, shortest_path in shortest_paths.items():
            for i in range(len(shortest_path) - 1):
                edge = (shortest_path[i], shortest_path[i + 1])
                T.add_edge(*edge, length=graph.get_edge_data(*edge)['length'])
        T = nx.Graph(graph.subgraph(T.nodes()).copy())
        mst = nx.minimum_spanning_tree(T, length="length")
        total_length = sum([edge[2]['length'] for edge in mst.edges(data=True)])
        print(f"spanning Tree:{total_length}")
        return mst

    def add_offset(self, offset, start_p, end_p, path_p):
        # start = (start_p[0] + offset, start_p[1] + offset, start_p[2])
        start = tuple((x + offset, y + offset, z) for x, y, z in start_p)
        path = tuple((x + offset, y + offset, z) for x, y, z in path_p)
        end = tuple((x + offset, y + offset, z) for x, y, z in end_p)
        return start, path, end

    def add_graphs(self, graph_list, grid_type: str = "forward"):
        """

                Args:
                    graph_list ():

                Returns:

                """
        combined_graph = nx.Graph()
        for subgraph in graph_list:
            combined_graph = nx.union(combined_graph, subgraph)
            # combined_graph = nx.disjoint_union(combined_graph, subgraph)
        combined_graph.graph["circulation_direction"] = grid_type
        return combined_graph

    @staticmethod
    def directed_graph(G, source_nodes, edge_type: str = "forward", grid_type: str = "forward", color: str = "red"):
        """
                Args:
                    G ():
                    source_nodes ():
                Returns:
                """

        D = nx.DiGraph(grid_type=grid_type)
        D.add_nodes_from(G.nodes(data=True))
        T = nx.bfs_tree(G, source_nodes)
        for edges in T.edges():
            length = abs(distance.euclidean(G.nodes[edges[0]]["pos"], G.nodes[edges[1]]["pos"]))
            D.add_edge(edges[0], edges[1], type=edge_type, grid_type=grid_type, length=length, color=color)
        D.graph["grid_type"] = grid_type
        return D

    def create_directed_edges(self, G, node_list, color: str, edge_type: str, grid_type: str):
        """

                Args:
                    G ():
                    node_list ():
                    color ():
                    edge_type ():
                    grid_type ():

                Returns:

                """
        for i in range(len(node_list) - 1):
            length = abs(distance.euclidean(G.nodes[node_list[i]]["pos"], G.nodes[node_list[i + 1]]["pos"]))
            G.add_edge(node_list[i],
                       node_list[i + 1],
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       length=length)

        return G

    def remove_edges_from_node(self,
                               G: nx.Graph(),
                               node: nx.Graph().nodes(),
                               tol_value: float = 0.0,
                               z_flag: bool = True,
                               y_flag: bool = True,
                               x_flag: bool = True,
                               ):
        """

                Args:
                    G (): Networkx Graph
                    node (): Knoten
                    tol_value (): tolleranz
                    top_z_flag ():
                    bottom_z_flag ():
                    pos_x_flag ():
                    neg_x_flag ():
                    pos_y_flag ():
                    neg_y_flag ():

                Returns:

                """
        node_pos = G.nodes[node]["pos"]
        node_neighbor = list(G.neighbors(node))
        y_list, x_list, z_list = [], [], []
        x_2, y_2, z_2 = node_pos
        for neighbor in node_neighbor:
            x_1, y_1, z_1 = G.nodes[neighbor]['pos']
            # Nachbarknoten vom Knoten
            if abs(x_1 - x_2) <= tol_value and abs(y_1 - y_2) <= tol_value:
                z_list.append(neighbor)
            if abs(y_1 - y_2) <= tol_value and abs(z_1 - z_2) <= tol_value:
                x_list.append(neighbor)
            if abs(x_1 - x_2) <= tol_value and abs(z_1 - z_2) <= tol_value:
                y_list.append(neighbor)
        # z edges
        if z_flag is True:
            if len(z_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_z_neighbor = None
                pos_z_neighbor = None
                for z in z_list:
                    diff = G.nodes[node]['pos'][2] - G.nodes[z]['pos'][2]
                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_z_neighbor = z
                    elif diff < 0 and (diff) < min_neg_diff:
                        min_neg_diff = (diff)
                        pos_z_neighbor = z

                if neg_z_neighbor is not None:
                    z_list.remove(neg_z_neighbor)
                if pos_z_neighbor is not None:
                    z_list.remove(pos_z_neighbor)
                for z in z_list:
                    if G.has_edge(z, node):
                        G.remove_edge(z, node)
                    elif G.has_edge(node, z):
                        G.remove_edge(node, z)
        # x edges
        if x_flag is True:
            if len(x_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_x_neighbor = None
                pos_x_neighbor = None
                for x in x_list:
                    diff = G.nodes[node]['pos'][0] - G.nodes[x]['pos'][0]
                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_x_neighbor = x
                    elif diff < 0 and (diff) < min_neg_diff:
                        min_neg_diff = (diff)
                        pos_x_neighbor = x
                if neg_x_neighbor is not None:
                    x_list.remove(neg_x_neighbor)
                if pos_x_neighbor is not None:
                    x_list.remove(pos_x_neighbor)
                for x in x_list:
                    if G.has_edge(x, node):
                        G.remove_edge(x, node)
                    if G.has_edge(node, x):
                        G.remove_edge(node, x)
        # y edges
        if y_flag is True:
            if len(y_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_y_neighbor = None
                pos_y_neighbor = None
                for y in y_list:
                    diff = G.nodes[node]['pos'][1] - G.nodes[y]['pos'][1]
                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_y_neighbor = y
                    elif diff < 0 and (diff) < min_neg_diff:
                        min_neg_diff = (diff)
                        pos_y_neighbor = y
                if neg_y_neighbor is not None:
                    y_list.remove(neg_y_neighbor)
                if pos_y_neighbor is not None:
                    y_list.remove(pos_y_neighbor)
                for y in y_list:
                    if G.has_edge(y, node):
                        G.remove_edge(y, node)
                    if G.has_edge(node, y):
                        G.remove_edge(node, y)
        return G, z_list, x_list, y_list

    def remove_edges(self, G, tol_value: float = 0.0):
        """
                color, edge_type, grid_type)
                Args:
                    G ():
                Returns:
                """
        node_dict = {}
        edge_dict = {}

        for node in G.nodes():
            if 'pos' in G.nodes[node]:
                edge_dict[node] = list(G.edges(node))
                node_dict[node] = list(G.neighbors(node))
        G = G.copy(as_view=False)
        for node in node_dict:
            # neighbors = list(G.neighbors(node))
            y_list, x_list, z_list = [], [], []
            x_1, y_1, z_1 = G.nodes[node]['pos']
            # Nachbarknoten vom Knoten
            for neigh in node_dict[node]:
                # for neigh in neighbors:
                x_2, y_2, z_2 = G.nodes[neigh]['pos']
                if abs(x_1 - x_2) <= tol_value and abs(y_1 - y_2) <= tol_value:
                    z_list.append(neigh)
                if abs(y_1 - y_2) <= tol_value and abs(z_1 - z_2) <= tol_value:
                    x_list.append(neigh)
                if abs(x_1 - x_2) <= tol_value and abs(z_1 - z_2) <= tol_value:
                    y_list.append(neigh)
            # z edges
            if len(z_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_z_neighbor = None
                pos_z_neighbor = None
                for z in z_list:
                    # diff = z_1 - G.nodes[z]['pos'][2]
                    diff = G.nodes[node]['pos'][2] - G.nodes[z]['pos'][2]
                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_z_neighbor = z
                    elif diff < 0 and abs(diff) < min_neg_diff:
                        min_neg_diff = abs(diff)
                        pos_z_neighbor = z
                if neg_z_neighbor is not None:
                    z_list.remove(neg_z_neighbor)
                if pos_z_neighbor is not None:
                    z_list.remove(pos_z_neighbor)
                for z in z_list:
                    if G.has_edge(z, node):
                        G.remove_edge(z, node)
                    elif G.has_edge(node, z):
                        G.remove_edge(node, z)
            # x edges
            if len(x_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_x_neighbor = None
                pos_x_neighbor = None
                for x in x_list:
                    # diff = x_1 - G.nodes[x]['pos'][0]
                    diff = G.nodes[node]['pos'][0] - G.nodes[x]['pos'][0]

                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_x_neighbor = x
                    elif diff < 0 and abs(diff) < min_neg_diff:
                        min_neg_diff = abs(diff)
                        pos_x_neighbor = x
                if neg_x_neighbor is not None:
                    x_list.remove(neg_x_neighbor)

                if pos_x_neighbor is not None:
                    x_list.remove(pos_x_neighbor)

                for x in x_list:
                    if G.has_edge(x, node):
                        G.remove_edge(x, node)
                    elif G.has_edge(node, x):
                        G.remove_edge(node, x)

            # y edges
            if len(y_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_y_neighbor = None
                pos_y_neighbor = None
                for y in y_list:
                    # diff = y_1 - G.nodes[y]['pos'][1]
                    diff = G.nodes[node]['pos'][1] - G.nodes[y]['pos'][1]
                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_y_neighbor = y
                    elif diff < 0 and abs(diff) < min_neg_diff:
                        min_neg_diff = abs(diff)
                        pos_y_neighbor = y
                if neg_y_neighbor is not None:
                    y_list.remove(neg_y_neighbor)
                if pos_y_neighbor is not None:
                    y_list.remove(pos_y_neighbor)
                for y in y_list:
                    if G.has_edge(y, node):
                        G.remove_edge(y, node)
                    elif G.has_edge(node, y):
                        G.remove_edge(node, y)

        return G

    def create_backward(self, G, grid_type: str = "backward", offset: float = 0.1, color: str = "blue"):
        """

                Args:
                    G ():
                    grid_type ():
                    offset ():

                Returns:

                """

        G_reversed = G.reverse()
        G_reversed.graph["grid_type"] = grid_type
        # Offset für die Knotenpositionen berechnen
        node_positions = nx.get_node_attributes(G, "pos")
        node_offset = {node: (pos[0] + offset, pos[1] + offset, pos[2]) for node, pos in node_positions.items()}
        nx.set_node_attributes(G_reversed, node_offset, "pos")
        for node, data in G_reversed.nodes(data=True):
            G_reversed.nodes[node]['grid_type'] = grid_type
            if "radiator_forward" in data["type"]:
                G_reversed.nodes[node]['type'] = ["radiator_backward"]
            if "start_node" in data["type"]:
                # G_reversed.nodes[node]['type'].append("end_node")
                G_reversed.nodes[node]['type'] = ["end_node", "Vereinigung"]
            if "Verteiler" in data["type"]:
                # G_reversed.nodes[node]['type'].append("end_node")
                G_reversed.nodes[node]['type'] = ["Vereinigung"]

        # Farbe der Kanten ändern
        edge_attributes = {(u, v): {"color": color} for u, v in G_reversed.edges()}
        nx.set_edge_attributes(G_reversed, edge_attributes)
        return G_reversed




if __name__ == '__main__':

    working_path = r"D:\dja-jho\Testing\HydraulicSystem"
    ifc_model = "AC20-Institute-Var-2"

    temperature_forward = 90
    temperature_backward = 70
    sheet_pipe = "Stahlrohre"
    create_graph = False
    create_new_graph = False
    create_heating_circle_flag = False
    # Kupfer
    # rho_cu = 8960
    # absolute_roughness = 0.0023
    # Stahl
    absolute_roughness = 0.045
    rho_steel = 7850

    density = rho_steel

    ifc = Path(working_path, "AC20-Institute-Var-2.ifc")
    dym_json_file = Path(working_path, "tz_mapping.json")
    dym_mat_file = Path(working_path, "2010_heavy_Alu_Isolierverglasung_bearbeitet.mat")

    ifc_building_json = Path(working_path, "ifc_building.json")
    ifc_delivery_json = Path(working_path, "ifc_delivery.json")
    network_building_json = Path(working_path, "network_building.json")
    network_heating_json = Path(working_path, "network_heating.json")
    network_heating_forward_json = Path(working_path, "network_heating.json")
    network_heating_backward_json = Path(working_path, "network_heating.json")
    calc_building_json = Path(working_path, "calculation_building.json")
    calc_heating_json = Path(working_path, "calculation_heating.json")

    create_heating_circle_flag = True
    create_new_graph = True

    start_point = (23.9, 6.7, -3.0)

    netx = GetBuildingGeometry(network_building_json=network_building_json,
                               network_heating_json=network_heating_json,
                               one_pump_flag=False,
                               create_heating_circle_flag=create_heating_circle_flag,
                               create_new_graph=create_new_graph,
                               working_path=working_path,
                               ifc_model=ifc_model,
                               source_data=start_point)





