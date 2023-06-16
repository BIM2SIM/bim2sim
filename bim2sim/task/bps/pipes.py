import copy

import networkx as nx
from networkx.algorithms.community import k_clique_communities
import matplotlib.pyplot as plt
from networkx.algorithms.components import is_strongly_connected
from pandapipes.component_models import Pipe
import pandapipes.plotting as plot
import pandapipes as pp
from networkx.readwrite import json_graph
import numpy as np
import math
from scipy.spatial import distance
from shapely.ops import nearest_points
import random

from shapely.geometry import Polygon, Point, LineString

from OCC.Display.SimpleGui import init_display
import pint
from itertools import combinations
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.STEPControl
import OCC.Core.Interface
import itertools
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.geom.occ_utils as geom_utils
import json


class GeometryBuildingsNetworkx():
    # todo: Kanten Kollision vermeiden
    # todo : unit checker mit einbauen
    # todo: polygon bilden -> Nachsten polygon finden -> Knoten projezieren -> Alten Knoten löschen
    # todo : Komponten -> Radiator: L-System Z richtung --|
    # todo: direction_flow für radiator einbauen
    # todo: Zusätzliche punkte einzeichen, damit radiatoren auch erreicht werden können, falls nicht

    def __init__(self, source_data, building_data, delivery_data, floor_data):
        self.source_data = source_data
        self.building_data = building_data
        self.delivery_data = delivery_data
        self.floor_data = floor_data

    def __call__(self):
        print("Create Buildings network")
        G = self.create_building_nx_network(floor_dict_data=self.building_data,
                                            grid_type="building",
                                            color="black",
                                            tol_value=0.0,
                                            edge_type="floor_plan")

        # Delivery points
        """copy_forward_G = G.copy()
        delivery_forward_nodes, delivery_backward_nodes = self.get_delivery_nodes(G=copy_forward_G,
                                                                                  type_delivery=["window"])"""

        # print("delivery_forward_nodes", delivery_forward_nodes)
        print("Read Building Graph")
        G = self.read_json_graph(file="build_graph.json")
        forward_graph = self.create_heating_circle(G=G,
                                                   type_delivery=["window"],
                                                   grid_type="forward")

        """

        copy_backward_G = G.copy()
        delivery_forward_nodes, delivery_backward_nodes = self.get_delivery_nodes(G=copy_backward_G,
                                                                                  type_delivery="window")


        backward_graph = self.create_heating_circle(G=copy_backward_G,
                                                   delivery_nodes=delivery_backward_nodes,
                                                   non_delivery_nodes=delivery_forward_nodes,
                                                   grid_type="backward")
        backward_graph = self.create_backward(G=backward_graph, grid_type="backward")
        heating_circle = self.connect_forward_backward(backward=backward_graph, forward=forward_graph)
        self.check_directed_graph(G=heating_circle, type_graph="heating_circle")"""
        # self.visualzation_networkx_3D(G=G, minimum_trees=[heating_circle])
        # plt.show()
        return forward_graph

    @staticmethod
    def read_buildings_json(file="buildings_json.json"):
        with open(file, "r") as datei:
            data = json.load(datei)
        return data



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
            # Ergebnis ausgeben
            """if len(isolated_nodes) > 0 and isolated_nodes is not None:
                print("Isolierte Knoten:")
                for node in isolated_nodes:
                    print(node)
            # Schwach zusammenhängende Komponenten identifizieren
            weak_components = list(nx.weakly_connected_components(G))
            # Ergebnis ausgeben
            if len(weak_components) > 0 and weak_components is not None:
                print("Schwach zusammenhängende Komponenten:")
                for component in weak_components:
                    print("Knoten in Komponente:", component)
                    for node in component:
                        print("Knoten:", node)
                        print("Position:", G.nodes[node]["pos"])

            # Stark zusammenhängende Komponenten identifizieren
            strong_components = list(nx.strongly_connected_components(G))
            # Ergebnis ausgeben
            if len(strong_components) > 0 and strong_components is not None:
                print("Stark zusammenhängende Komponenten:")
                for component in strong_components:
                    print("Knoten in Komponente:", component)
                    for node in component:
                        print("Knoten:", node)
                        print("Position:", G.nodes[node]["pos"])"""
            #netx.visulize_networkx(G=G)
            #plt.show()
            # exit(1)

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
        edge_list  = []
        # Erstelle eine Liste mit den IDs, die den Element-IDs zugeordnet sind
        for element in delivery_dict:
            forward_node, backward_node = self.get_bottom_left_node(G=G, nodes=delivery_dict[element])
            delivery_forward_points.append(forward_node)
            delivery_backward_points.append(backward_node)
            edge_list.append((forward_node, backward_node))

            nx.set_node_attributes(G, {forward_node: {'type': ['radiator_forward']}})
            nx.set_node_attributes(G, {forward_node: {'color': 'red'}})
            nx.set_node_attributes(G, {backward_node: {'type': ['radiator_backward']}})
            nx.set_node_attributes(G, {backward_node: {'color': 'blue'}})
        return delivery_forward_points, delivery_backward_points, edge_list

    def check_neighbour_nodes(self,
                              G,
                              edge_point_A,
                              edge_point_B):
        """
        Args:
            G ():
            edge_point_A (): Knoten der verbunden werden soll
            edge_point_B (): Gesnappter Knoten an nächste Wand
        Returns:
        """
        #return False
        for neighbor, attr in G.nodes(data=True):
            # Koordinaten eines Knotens
            point = attr["pos"]
            if point != edge_point_A:
                # z - Richtung
                if edge_point_A[2] == edge_point_B[2] == point[2]:
                    p = Point(point[0], point[1])
                    line = LineString([(edge_point_A[0], edge_point_A[1]), (edge_point_B[0], edge_point_B[1])])
                    if point[0] == edge_point_A[0] and point[1] == edge_point_A[1] or point[0] == edge_point_B[0] and \
                            point[1] == edge_point_B[1]:
                        continue
                    if p.intersects(line) is True:
                        return p.intersects(line)
                # y - Richtung
                if edge_point_A[1] == edge_point_B[1] == point[1]:
                    p = Point(point[0], point[2])
                    line = LineString([(edge_point_A[0], edge_point_A[2]), (edge_point_B[0], edge_point_B[2])])
                    if point[0] == edge_point_A[0] and point[2] == edge_point_A[2] or point[0] == edge_point_B[0] and \
                            point[2] == edge_point_B[2]:
                        continue
                    if p.intersects(line) is True:
                        return p.intersects(line)
                # X - Richtung
                if edge_point_A[0] == edge_point_B[0] == point[0]:
                    p = Point(point[1], point[2])
                    line = LineString([(edge_point_A[1], edge_point_A[2]), (edge_point_B[1], edge_point_B[2])])
                    if point[1] == edge_point_A[1] and point[2] == edge_point_A[2] or point[1] == edge_point_B[1] and \
                            point[2] == edge_point_B[2]:
                        continue
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
                                     start_source_point):
        source_dict = {}
        for i, floor in enumerate(floor_dict):
            _dict = {}
            _dict["pos"] = (start_source_point[0], start_source_point[1], floor_dict[floor]["height"])
            _dict["type_node"] = "source"
            _dict["element"] = f"source_{floor}"
            _dict["color"] = "green"
            _dict["belongs_to"] = floor
            source_dict[floor] = _dict
        return source_dict

    def get_source_nodes(self,
                         G,
                         points,
                         floor_dict):
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
        source_list = []
        source_dict = self.define_source_node_per_floor(floor_dict=floor_dict,
                                                        start_source_point=points)
        G = G.copy()
        # Erstellen der Source Knoten
        for floor in source_dict:
            pos = source_dict[floor]["pos"]
            id_name = f"source_{floor}"
            G, source_node = self.create_nodes(G=G,
                                               id_name=id_name,
                                               points=pos,
                                               color="red",
                                               type_node="source",
                                               element=id_name,
                                               grid_type="heating_circle",
                                               belongs_to=floor,
                                               direction="y",
                                               update_node=True,
                                               floor_belongs_to=floor)
            source_list.append(source_node)
        # todo: sollte eigentlich nur die wall_center Kanten nehmen
        G = self.connect_nodes_with_grid(G=G,
                                         node_list=source_list,
                                         color="grey",
                                         type_node=["center_wall"],
                                         edge_type_node=["center_wall"],
                                         #same_type_flag=True,
                                         all_edges_flag=True,
                                         direction_x=True,
                                         direction_y = True,
                                         direction_z=False,
                                         disjoint_flag=False,
                                         intersects_flag=False,
                                         within_flag=False,
                                         create_snapped_edge_flag=True)
        self.check_graph(G=G, type="Source")
        return G, source_list

    def connect_forward_backward(self, backward, forward):
        """

        Args:
            backward ():
            forward ():

        Returns:

        """
        # Knoten-Listen für übereinstimmende Knoten erstellen
        # graph1_renamed = nx.relabel_nodes(backward, lambda x: f'graph1_{x}')
        # graph2_renamed = nx.relabel_nodes(forward, lambda x: f'graph2_{x}')

        # heating_circle = nx.union(backward, forward)
        heating_circle = nx.disjoint_union(backward, forward)
        matching_nodes = []
        for node1, attr1 in heating_circle.nodes(data=True):
            for node2, attr2 in heating_circle.nodes(data=True):
                if attr1['type'] == 'radiator' and attr2['type'] == 'radiator' and \
                        attr1['element'] == attr2['element']:
                    matching_nodes.append((node1, node2))
        """for node1, node2 in matching_nodes:
            length = abs(distance.euclidean(heating_circle.nodes[node2]["pos"], heating_circle.nodes[node1]["pos"]))
            heating_circle.add_edge(node1,
                                    node2,
                                    color="grey",
                                    type="pipe",
                                    grid_type="heating_circle",
                                    direction="x",
                                    weight=length)"""
        return heating_circle

    def create_heating_circle(self,
                              G,
                              grid_type,
                              type_delivery: list = ["window"]):

        # Erstelle Endpunkte: Hier Fenster Punkte
        delivery_forward_nodes, delivery_backward_nodes, forward_backward_edge = self.get_delivery_nodes(G=G,
                                                                                  type_delivery=type_delivery)
        # Erstelle Anfangspunkte: Werden vorher angegeben
        # forward
        nodes_forward = ["center_wall", "snapped_window_nodes", "window", "radiator_forward", "source", "space", "door"]
        subgraph_nodes_forward = [n for n, attr in G.nodes(data=True) if
                                  any(t in attr.get("type", []) for t in nodes_forward)]
        forward_graph = G.subgraph(subgraph_nodes_forward)
        self.connect_nodes_with_grid
        # backward
        nodes_backward = ["center_wall", "snapped_window_nodes", "window", "radiator_backward", "source", "space"]
        subgraph_nodes_backward = [n for n, attr in G.nodes(data=True) if
                                  any(t in attr.get("type", []) for t in nodes_backward)]
        backward_graph = G.subgraph(subgraph_nodes_backward)
        #forward_graph = G
        print("Add Source Nodes")
        forward_graph, source_list = self.get_source_nodes(G=forward_graph,
                                                           points=self.source_data,
                                                           floor_dict=self.building_data)
        """backward_graph, source_list = self.get_source_nodes(G=backward_graph,
                                                           points=self.source_data,
                                                           floor_dict=self.building_data)"""

        """nodes_forward = ["center_wall", "snapped_window_nodes", "window", "radiator_forward", "source", "space"]
        # nodes = ["center_wall"]
        subgraph_nodes_forward = [n for n, attr in G.nodes(data=True) if
                                  any(t in attr.get("type", []) for t in nodes_forward)]"""

        self.check_graph(G=forward_graph, type="forward_graph")
        #self.check_graph(G=backward_graph, type="backward_graph")
        ff_graph_list = []
        bf_graph_list = []
        # pro Etage
        for i, floor in enumerate(self.building_data):
            print(f"Calculate steiner tree {floor}_{i}")
            # Pro Delivery Point pro Etage
            element_nodes_forward = []
            element_nodes_backward = []
            for delivery_node in delivery_forward_nodes:
                if forward_graph.nodes[delivery_node]["floor_belongs_to"] == floor:
                    element_nodes_forward.append(delivery_node)
            for source_node in source_list:
                if forward_graph.nodes[source_node]["floor_belongs_to"] == floor:
                    element_nodes_forward.append(source_node)


            """for delivery_node in delivery_forward_nodes:
                if backward_graph.nodes[delivery_node]["floor_belongs_to"] == floor:
                    element_nodes_backward.append(delivery_node)"""
            # Pro Source Point pro Etage
            """for source_node in source_list:
                
                if backward_graph.nodes[source_node]["floor_belongs_to"] == floor:
                    element_nodes_backward.append(source_node)"""

            f_st, total_weight = self.steiner_tree(graph=forward_graph,
                                                   term_points=element_nodes_forward,
                                                   grid_type="forward")

            # Add components
            #
            if total_weight != 0  and total_weight is not None:
                f_st = self.add_component_nodes(G=f_st)
                f_st = self.directed_graph(G=f_st, source_nodes=source_list[i], grid_type=grid_type)
                self.check_directed_graph(G=f_st, type_graph=grid_type)
                ff_graph_list.append(f_st)

            """b_st, total_weight = self.steiner_tree(graph=backward_graph,
                                                   term_points=element_nodes_backward,
                                                   grid_type="backward")
            if total_weight != 0 and total_weight is not None:
                b_st = self.add_component_nodes(G=b_st)
                b_st = self.directed_graph(G=b_st, source_nodes=source_list[i], grid_type=grid_type)
                b_st = self.create_backward(G=b_st)
                self.check_directed_graph(G=b_st, type_graph=grid_type)
                bf_graph_list.append(b_st)
                # plots
                # self.visualize_node_order(G=f_st)
                # self.visualzation_networkx_3D(G=G, minimum_trees=[f_st])
                # netx.visulize_networkx(G=f_st)
                # plt.show()"""

        f_st = self.add_graphs(graph_list=ff_graph_list)
        #b_st = self.add_graphs(graph_list=bf_graph_list)
        # Add rise tube
        f_st = self.add_rise_tube(G=f_st, circulation_direction=grid_type)

        #b_st = self.add_rise_tube(G=b_st, circulation_direction=grid_type)
        self.check_graph(G=f_st, type=grid_type)
        #self.check_graph(G=b_st, type=grid_type)
        # direct graph

        f_st = self.directed_graph(G=f_st, source_nodes=source_list[0], grid_type=grid_type)
        #b_st = self.directed_graph(G=b_st, source_nodes=source_list[0], grid_type=grid_type)
        #heating_circle =  nx.disjoint_union(f_st, b_st)
        """for edge in forward_backward_edge:
            heating_circle.add_edge(edge[0], edge[1])"""
        #self.check_directed_graph(G=heating_circle, type_graph=grid_type)
        #print(heating_circle)
        #self.visualzation_networkx_3D(G=G, minimum_trees=[f_st])
        #self.visualize_node_order(G=f_st)
        #self.visualzation_networkx_3D(G=G, minimum_trees=[f_st])
        #netx.visulize_networkx(G=f_st)
        #plt.show()
        # self.max_flow()
        # self.visualize_node_order(G=f_st)
        # exit(0)
        # self.check_directed_graph(G=f_st, type_graph=grid_type)
        #self.save_networkx_json(G=heating_circle, file="heating_graph.json")
        self.save_networkx_json(G=f_st, file="heating_graph.json")
        return f_st
        #return heating_circle

    def read_json_graph(self, file):
        with open(file, "r") as file:
            json_data = json.load(file)
            G = nx.node_link_graph(json_data)
        return G

    def visualize_node_order(self, G):
        # Knotenpositionen
        node_positions = nx.spring_layout(G)
        plt.figure(figsize=(8, 6))
        # Anfangs- und Endknoten farblich markieren
        node_color = ['red' if "radiator_forward" in set(G.nodes[node]['type']) else 'g' if 'source' in G.nodes[node]['type'] else 'b'
                      for node in G.nodes()]
        # Graph zeichnen
        t = nx.get_node_attributes(G, "pos")
        new_dict = {key: (x, y) for key, (x, y, z) in t.items()}
        nx.draw(G,
                pos=new_dict,
                node_color=node_color,
                node_shape='o',
                node_size=10,
                font_size=12)



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
        # todo: Hier iwas
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

    def create_edge_connection(self,
                               direction,
                               neighbor_pos,
                               node_pos,
                               tol_value,
                               neighbor,
                               pos_neighbors,
                               neg_neighbors):
        """

        Args:
            direction ():
            neighbor_pos ():
            node_pos ():
            tol_value ():
            neighbor ():
            pos_neighbors ():
            neg_neighbors ():

        Returns:

        """
        if direction == "x":
            if (neighbor_pos[0] - node_pos[0]) < 0 and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and abs(
                    neighbor_pos[2] - node_pos[2]) <= tol_value:
                pos_neighbors.append(neighbor)
            if (neighbor_pos[0] - node_pos[0]) > 0 and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and abs(
                    neighbor_pos[2] - node_pos[2]) <= tol_value:
                neg_neighbors.append(neighbor)
        if direction == "y":
            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and (neighbor_pos[1] - node_pos[1]) < 0 and abs(
                    neighbor_pos[2] - node_pos[2]) <= tol_value:
                pos_neighbors.append(neighbor)
            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and (neighbor_pos[1] - node_pos[1]) > 0 and abs(
                    neighbor_pos[2] - node_pos[2]) <= tol_value:
                neg_neighbors.append(neighbor)
        if direction == "z":
            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and (
                    neighbor_pos[2] - node_pos[2]) < 0:
                pos_neighbors.append(neighbor)
            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and (
                    neighbor_pos[2] - node_pos[2]) > 0:
                neg_neighbors.append(neighbor)
        return neg_neighbors, pos_neighbors

    def same_edge(self, G, node_1, node_2):
        node1_edges = G.edges(node_1)
        node2_edges = G.edges(node_2)
        if len(node1_edges) != 1 or len(node2_edges) != 1:
            # Knoten sind nicht genau mit einer Kante verbunden
            return False
        else:

            edge1 = node1_edges[0]
            edge2 = node2_edges[0]
            if edge1 == edge2:
                # Knoten sind auf derselben Kante
                return True
            else:
                # Knoten sind auf unterschiedlichen Kanten
                return False

    def check_graph(self, G, type):
        if nx.is_connected(G) is True:
            print(f"{type} Graph is connected.")
        else:
            print(f"{type} Graph is not connected.")
            for node in G.nodes():
                if nx.is_isolate(G, node) is True:
                    print("node", node, "is not connected.")
                    print(G.nodes[node]["pos"])
            # Bestimme die verbundenen Komponenten
            components = list(nx.connected_components(G))

            # Finde die nicht miteinander verbundenen Komponenten
            disconnected_components = [c for c in components if len(c) > 1]

            # Gib die nicht miteinander verbundenen Komponenten aus
            for component in disconnected_components:
                for c in component:
                    print("node", c, "is not connected.")
                    print(G.nodes[c]["pos"])
            netx.visulize_networkx(G=G)
            plt.show()
            exit(1)

    def avoid_edge_collisions(self, G, pos, threshold=0.1):
        # Kopie der ursprünglichen Positionen erstellen
        new_pos = pos.copy()
        # Schleife über alle Kanten im Graphen
        for u, v in G.edges():
            # Start- und Endpositionen der Kanten abrufen
            start_pos = pos[u]
            end_pos = pos[v]
            # Überprüfen, ob die Kanten kollidieren
            if self.collision_detected(start_pos, end_pos, threshold):
                # Kollision festgestellt, Positionen anpassen
                new_pos[u] = self.random_adjustment(start_pos, threshold)
                new_pos[v] = self.random_adjustment(end_pos, threshold)
        return new_pos

    def collision_detected(self, start_pos, end_pos, threshold):
        # Prüfen, ob die Distanz zwischen Start- und Endposition größer als der Schwellenwert ist
        distance = self.calculate_distance(start_pos, end_pos)
        return distance < threshold

    def random_adjustment(self, position, threshold):
        # Zufällige Anpassung der Position um den Schwellenwert
        adjustment = random.uniform(-threshold, threshold)
        return position + adjustment

    def calculate_distance(self, pos1, pos2):
        # Berechnung der euklidischen Distanz zwischen zwei Positionen
        return ((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2) ** 0.5

    def nearest_neighbour_edge(self,
                               G,
                               node,
                               edge_type,
                               direction,
                               color: str = "red",
                               grid_type: str = "forward",
                               nearest_node_flag: bool = True,
                               connect_floor_spaces_together: bool = False,
                               tol_value: float = 0.0,
                               connect_element_together: bool = False,
                               node_type: list = None,
                               connect_types: bool = False,
                               connect_node_flag: bool = False,
                               connect_node_list: list = None,
                               type_nodes: list = ["space", "wall", "center_wall"],
                               disjoint_flag: bool = False,
                               intersects_flag: bool = False,
                               within_flag: bool = False,
                               col_tol: float = 0.1,
                               collision_type_node: list = ["space"],
                               all_node_flag: bool = False):
        """
        Args:
            edge_type ():
            color ():
            neighbor_node ():
            connect_floor_spaces_together ():
            connect_element_together ():
            connect_types ():
            connect_elements ():  if G.nodes[node]["element"] == data["element"]:
            connect_grid ():
            connect_all ():
            G ():
            node ():
            direction ():
            grid_type ():
            tol_value ():
        Returns:
        """
        pos_neighbors = []
        neg_neighbors = []
        node_pos = G.nodes[node]["pos"]
        node_pos = tuple(round(coord, 2) for coord in node_pos)
        """if connect_all is True:
            neg_neighbors, pos_neighbors = self.create_edge_connection(direction, neighbor_pos, node_pos,
                                                                       tol_value, neighbor,
                                                                       pos_neighbors, neg_neighbors)"""
        if connect_node_flag is True:
            for connect_node in connect_node_list:
                if connect_node != node:
                    connect_pos = G.nodes[connect_node]["pos"]
                    neg_neighbors, pos_neighbors = self.create_edge_connection(direction=direction,
                                                                               neighbor_pos=connect_pos,
                                                                               node_pos=node_pos,
                                                                               tol_value=tol_value,
                                                                               neighbor=connect_node,
                                                                               pos_neighbors=pos_neighbors,
                                                                               neg_neighbors=neg_neighbors,
                                                                               )
        elif nearest_node_flag is True:
            for neighbor, data in G.nodes(data=True):
                if neighbor != node:
                    neighbor_pos = data["pos"]
                    """if G.nodes[node]["type"] == "projected_window_nodes" and data["type"] == "projected_window_nodes":
                        if G.nodes[node]["element"] == data["element"]:
                            neg_neighbors, pos_neighbors = self.create_edge_connection(direction, neighbor_pos, node_pos,
                                                                                       tol_value, neighbor,
                                                                                       pos_neighbors, neg_neighbors)
                        else:
                            continue"""
                    """if connect_element_snapping_node is True:
                        if G.nodes[node]["element"] == data["element"]:
                            pass"""

                    if connect_element_together is True:
                        if set(G.nodes[node]["element"]) & set(data["element"]):
                            neg_neighbors, pos_neighbors = self.create_edge_connection(direction,
                                                                                       neighbor_pos,
                                                                                       node_pos,
                                                                                       tol_value,
                                                                                       neighbor,
                                                                                       pos_neighbors,
                                                                                       neg_neighbors)
                    if connect_floor_spaces_together is True:
                        if node_type is None:
                            print(f"Define node_type {node_type}.")
                            exit(1)
                        if set(node_type) & set(G.nodes[node]["type"]) and set(node_type) & set(data["type"]):
                            if G.nodes[node]["floor_belongs_to"] == data["floor_belongs_to"]:
                                if set(G.nodes[node]["element"]).isdisjoint(set(data["element"])):
                                    neg_neighbors, pos_neighbors = self.create_edge_connection(direction,
                                                                                               neighbor_pos,
                                                                                               node_pos,
                                                                                               tol_value,
                                                                                               neighbor,
                                                                                               pos_neighbors,
                                                                                               neg_neighbors)


                    if connect_types is True:
                        #if set(node_type) & set(G.nodes[node]["type"]) & set(data["type"]):
                        if set(node_type) &  set(data["type"]):
                            neg_neighbors, pos_neighbors = self.create_edge_connection(direction,
                                                                                       neighbor_pos,
                                                                                       node_pos,
                                                                                       tol_value,
                                                                                       neighbor,
                                                                                       pos_neighbors,
                                                                                       neg_neighbors)
                    if all_node_flag is True:
                        neg_neighbors, pos_neighbors = self.create_edge_connection(direction,
                                                                                   neighbor_pos,
                                                                                   node_pos,
                                                                                   tol_value,
                                                                                   neighbor,
                                                                                   pos_neighbors,
                                                                                   neg_neighbors)

                        """if "space" in set(G.nodes[node]["type"]) and "space" in set(data["type"]):
                            #if set(G.nodes[node]["belongs_to"]) & set(data["belongs_to"]):
                            neg_neighbors, pos_neighbors = self.create_edge_connection(direction,
                                                                                           neighbor_pos,
                                                                                           node_pos,
                                                                                           tol_value,
                                                                                           neighbor,
                                                                                           pos_neighbors,
                                                                                           neg_neighbors)
                        if "wall" in set(G.nodes[node]["type"]) and "wall" in set(data["type"]):
                            neg_neighbors, pos_neighbors = self.create_edge_connection(direction,
                                                                                       neighbor_pos,
                                                                                       node_pos,
                                                                                       tol_value,
                                                                                       neighbor,
                                                                                       pos_neighbors,
                                                                                       neg_neighbors)"""

                """
                if connect_elements is False:
                    if G.nodes[node]["type"] == "window" and data["type"] == "window":
                        continue
                if connect_grid is True:
                    if G.nodes[node]["type"] == "space" and data["type"] == "space":
                        neg_neighbors, pos_neighbors = self.create_edge_connection(direction, neighbor_pos, node_pos,
                                                                                   tol_value, neighbor,
                                                                                   pos_neighbors, neg_neighbors)
                    if G.nodes[node]["type"] == "projected_points" and data["type"] == "space":
                        neg_neighbors, pos_neighbors = self.create_edge_connection(direction, neighbor_pos, node_pos,
                                                                                   tol_value, neighbor,
                                                                                   pos_neighbors, neg_neighbors)
                    if G.nodes[node]["type"] == "space" and data["type"] == "projected_points":
                        neg_neighbors, pos_neighbors = self.create_edge_connection(direction, neighbor_pos, node_pos,
                                                                                   tol_value, neighbor,
                                                                                   pos_neighbors, neg_neighbors)
                    continue

                if abs(node_pos[0] - neighbor_pos[0]) <= tol_value or abs(node_pos[1] - neighbor_pos[1]) <= tol_value or abs(
                        node_pos[2] - neighbor_pos[2]) <= tol_value:
                    if data["element"] == G.nodes[node]["element"]:
                        neg_neighbors, pos_neighbors = self.create_edge_connection(direction, neighbor_pos, node_pos, tol_value, neighbor,
                                               pos_neighbors, neg_neighbors)
                    if G.nodes[node]["element"] == data["belongs_to"] or G.nodes[node]["belongs_to"] == data["element"]:
                        neg_neighbors, pos_neighbors = self.create_edge_connection(direction, neighbor_pos, node_pos,
                                                                                   tol_value, neighbor,
                                                                                   pos_neighbors, neg_neighbors)
                """
        # print(intersects_flag)
        if pos_neighbors:
            nearest_neighbour = sorted(pos_neighbors, key=lambda p: distance.euclidean(G.nodes[p]["pos"], node_pos))[0]
            if nearest_neighbour is not None:
                if not G.has_edge(node, nearest_neighbour) and not G.has_edge(node, nearest_neighbour):
                    if self.check_collision(G=G,
                                            edge_point_A=G.nodes[node]["pos"],
                                            edge_point_B=G.nodes[nearest_neighbour]["pos"],
                                            disjoint_flag=disjoint_flag,
                                            intersects_flag=intersects_flag,
                                            within_flag=within_flag,
                                            tolerance=col_tol) is False:
                        length = abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos))

                        G.add_edge(node,
                                   nearest_neighbour,
                                   color=color,
                                   type=edge_type,
                                   grid_type=grid_type,
                                   direction=direction,
                                   weight=length)
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
                                            collision_type_node=collision_type_node) is False:
                        length = abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos))

                        G.add_edge(node,
                                   nearest_neighbour,
                                   color=color,
                                   type=edge_type,
                                   grid_type=grid_type,
                                   direction=direction,
                                   weight=length)
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

        """nearest_pos_x_lines = min(x_pos_lines,
                                  key=lambda line: abs(line.coords[0][0] - point.x)) if x_pos_lines else None
        nearest_neg_x_lines = min(x_neg_lines,
                                  key=lambda line: abs(line.coords[0][0] - point.x)) if x_neg_lines else None
        nearest_pos_y_lines = min(y_pos_lines,
                                  key=lambda line: abs(line.coords[0][1] - point.y)) if y_pos_lines else None
        nearest_neg_y_lines = min(y_neg_lines,
                                  key=lambda line: abs(line.coords[0][1] - point.y)) if y_neg_lines else None
        nearest_pos_z_lines = min(z_pos_lines,
                                  key=lambda line: abs(line.coords[0][2] - point.z)) if z_pos_lines else None
        nearest_neg_z_lines = min(z_neg_lines,
                                  key=lambda line: abs(line.coords[0][2] - point.z)) if z_neg_lines else None
        new_node_neg_x = new_node_pos_x = new_node_neg_y = new_node_pos_y = new_node_neg_z = new_node_pos_z = None"""

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
        if disjoint_flag is False and intersects_flag is False and within_flag is False:
            return False
        ele_dict = self.get_type_node_attr(G=G,
                                           type_node=collision_type_node,
                                           attr="pos")
        polygons = []
        for element in ele_dict:
            points = ele_dict[element]
            coords = np.array(points)
            if len(coords) == 8:
                coords_z = coords[coords[:, 2].argsort()]
                # Bestimme maximale und minimale Y- und X-Koordinaten
                max_y = np.max(coords_z[:, 1]) - tolerance
                min_y = np.min(coords_z[:, 1]) + tolerance
                max_x = np.max(coords_z[:, 0]) - tolerance
                min_x = np.min(coords_z[:, 0]) + tolerance
                polygon_2d = Polygon([(max_x, max_y), (min_x, max_y), (max_x, min_y), (min_x, min_y)])
                # print(polygon_2d)
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
                if snapped_line_with_tolerance.intersects(poly):
                    return True
                if snapped_line_with_tolerance.intersects(poly):
                    return True
                if snapped_line_with_tolerance.overlaps(poly):
                    return True
            elif within_flag is True:
                if snapped_line_with_tolerance.within(poly):
                    return True
        return False

    def center_space(self, ):
        max_y = np.max(coords_z[:, 1]) - tolerance
        min_y = np.min(coords_z[:, 1]) + tolerance
        max_x = np.max(coords_z[:, 0]) - tolerance
        min_x = np.min(coords_z[:, 0]) + tolerance

    def nearest_edges(self,
                      G,
                      node,
                      points,
                      edges,
                      z_flag: bool = True,
                      x_flag: bool = True,
                      y_flag: bool = True,
                      tol_value: float = 0.0,
                      top_z_flag: bool = False,
                      bottom_z_flag: bool = True,
                      pos_x_flag: bool = True,
                      neg_x_flag: bool =True,
                      pos_y_flag: bool =True,
                      neg_y_flag: bool= True):
        """
        Finde die nächste Kante für alle Rchtung in x,y,z coordinates.  Hier werden erstmal alle Kanten nach deren Richtung sortiert
        Args:

            floors_flag ():
            points (): Punktkoordinaten
            z_flag (): Falls True, such auch in Z Richtung nach Kanten
            x_flag (): Falls True, such auch in X Richtung nach Kanten
            y_flag (): Falls True, such auch in Y Richtung nach Kanten
            tol_value ():
            top_z_flag (): Falls False, Sucht nur in negativer z richtung
            edges (): Ausgewählte Kanten für den Punkt
        Returns:
        """
        # x_lines = []
        # x_neg_lines, x_pos_lines, y_neg_lines, y_pos_lines, z_pos_lines, z_neg_lines = [], [], [], [], [], []

        x_neg_lines, x_pos_lines, y_neg_lines, y_pos_lines, z_pos_lines, z_neg_lines = {}, {}, {}, {}, {}, {}

        for edge in edges:
            (x1, y1, z1) = G.nodes[edge[0]]["pos"]
            (x2, y2, z2) = G.nodes[edge[1]]["pos"]
            # for neigh in node_neighbor:
            # if neigh == edge[0] or neigh == edge[1]:
            #        print(node_neighbor)
            #       continue
            if edge[0] !=  node and edge[1] != node:
                if (x1, y1, z1) == (points[0], points[1], points[2]) or (x2, y2, z2) == (points[0], points[1], points[2]):
                    continue
                # x line: y1 = y2 , z1 = z2
                if abs(y1 - y2) <= tol_value and abs(z1 - z2) <= tol_value:
                    if x1 <= points[0] <= x2 or x2 <= points[0] <= x1:
                        # if x1 < points[0] < x2 or x2 < points[0] < x1:
                        # Rechts und Links Kante: z1 = z2 = pz
                        if y_flag is True:
                            if abs(z1 - points[2]) <= tol_value:
                                # left side
                                # if points[1] > y1:
                                if pos_y_flag is True:
                                    if points[1] >= y1:
                                        # y_pos_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                        y_pos_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                                if neg_y_flag is True:
                                    # right side
                                    if points[1] < y1:
                                        # y_neg_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                        y_neg_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                        # Vertikale Kante
                        if z_flag is True:
                            # y1 = py
                            if abs(y1 - points[1]) <= tol_value:
                                if bottom_z_flag is True:
                                    if points[2] >= z1:
                                        # z_pos_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                        z_pos_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                                if top_z_flag is True:
                                    if points[2] < z1:
                                        # z_neg_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                        z_neg_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                # y line: x1 = x2 und z1 = z2
                if abs(x1 - x2) <= tol_value and abs(z1 - z2) <= tol_value:
                    # z1 = pz
                    if y1 <= points[1] <= y2 or y2 <= points[1] <= y1:
                        # if y1 < points[1] < y2 or y2 < points[1] < y1:
                        if x_flag is True:
                            if abs(z1 - points[2]) <= tol_value:
                                # left side
                                # if points[0] >= x1
                                if pos_x_flag is True:
                                    if points[0] >= x1:
                                        x_pos_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                                        # x_pos_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                # right side
                                if neg_x_flag is True:
                                    if points[0] < x1:
                                        x_neg_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                                        # x_neg_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                        if z_flag is True:
                            # x1 = px
                            if abs(x1 - points[0]) <= tol_value:
                                if bottom_z_flag is True:
                                    if points[2] >= z1:
                                        # z_pos_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                        z_pos_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                                if top_z_flag is True:
                                    if points[2] < z1:
                                        # z_neg_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                        z_neg_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                # z line: x1 = x2 und y1 = y2
                if abs(x1 - x2) <= tol_value and abs(y1 - y2) <= tol_value:
                    # x1 = px
                    if z1 <= points[2] <= z2 or z2 <= points[2] <= z1:
                        # if z1 < points[2] < z2 or z2 < points[2] < z1:
                        if y_flag is True:
                            if abs(x1 - points[0]) <= tol_value:
                                if pos_y_flag is True:
                                    # left side
                                    if points[1] >= y1:
                                        # y_pos_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                        y_pos_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                                if neg_y_flag is True:
                                    # right side
                                    if points[1] < y1:
                                        # y_neg_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                        y_neg_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                        # y1 = py
                        if x_flag is True:
                            if abs(y1 - points[1]) <= tol_value:
                                if pos_x_flag is True:
                                    # left side
                                    if points[0] >= x1:
                                        # x_pos_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                        x_pos_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
                                if pos_x_flag is True:
                                    # right side
                                    if points[0] < x1:
                                        # x_neg_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
                                        x_neg_lines[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])

        new_node_neg_x, new_node_pos_x, new_node_neg_y, new_node_pos_y, new_node_neg_z, new_node_pos_z, \
        nearest_pos_x_lines, nearest_neg_x_lines, nearest_pos_y_lines, nearest_neg_y_lines, nearest_pos_z_lines, \
        nearest_neg_z_lines = \
            self.snapped_point_on_edges(points=points,
                                        x_neg_lines=x_neg_lines,
                                        x_pos_lines=x_pos_lines,
                                        y_neg_lines=y_neg_lines,
                                        y_pos_lines=y_pos_lines,
                                        z_pos_lines=z_pos_lines,
                                        z_neg_lines=z_neg_lines)

        return new_node_neg_x, new_node_pos_x, new_node_neg_y, new_node_pos_y, new_node_neg_z, new_node_pos_z, \
               nearest_pos_x_lines, nearest_neg_x_lines, nearest_pos_y_lines, nearest_neg_y_lines, nearest_pos_z_lines, \
               nearest_neg_z_lines

    def add_rise_tube(self,
                      G: nx.Graph(),
                      color: str = "red",
                      circulation_direction: str = "forward"):
        """
        Args:
            G ():
            circulation_direction ():
        Returns:
        """
        source_dict = {}
        for node, data in G.nodes(data=True):
            if "source" in G.nodes[node]["type"]:
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
                            weight=length)

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

    def snapping(self,
                 G: nx.Graph(),
                 node,
                 color,
                 belongs_to,
                 belongs_to_edge_list,
                 grid_type,
                 type_node,
                 element,
                 floor_belongs_to,
                 collision_type_node: list = ["space"],
                 z_flag: bool = True,
                 x_flag: bool = True,
                 y_flag: bool = True,
                 top_z_flag: bool = True,
                 bottom_z_flag: bool = True,
                 pos_x_flag: bool = True,
                 neg_x_flag: bool = True,
                 pos_y_flag: bool = True,
                 neg_y_flag: bool = True,
                 direction_x: bool = True,
                 direction_y: bool = True,
                 direction_z: bool = True,
                 connect_snap_nodes_flag: bool = True,
                 edge_type_node: list = None,
                 disjoint_flag: bool = False,
                 intersects_flag: bool = False,
                 within_flag: bool = False,
                 update_node: bool = True,
                 create_snapped_edge_flag: bool = False,
                 col_tolerance: float = 0.1,
                 tol_value: float = 0.0):

        """
        Args:
            x_flag (): Betrachtet Kanten in X-Richtung
            y_flag (): Betrachtet Kanten in Y-Richtung
            z_flag (): Betrachtet Kanten in Z-Richtung
            top_z_flag (): Falls False: Sucht nur in negativer z richtung

            floor_belongs_to (): ID der Etage zu dem das Element gehört
            connect_snap_nodes_flag (): True: Verbinden Knoten und die gesnappted Knoten
            disjoint_flag (): Collsion flag: disjoint
            intersects_flag (): Collsion flag: intersect
            within_flag (): Collsion flag: within
            update_node (): Update Knoten, falls ein Knoten auf der Position bereits existiert.
            node (): Knoten zum snappen
            color (): Farbe des Knoten
            belongs_to (): Element gehört zu Space ID
            belongs_to_edge_list (): Liste von Knoten die betrachtet werden sollen.
            grid_type (): Typ des Netzwerkes
            type_node (): Typ des Knoten
            element (): Element des Knoten, (Element bspw. Space, Tür, Fenster)
            direction_x ():
            direction_y ():
            direction_z ():
            G (): Networkx Graph

        Returns:
        """
        node_list = []
        remove_edge = []



        new_node_neg_x, new_node_pos_x, new_node_neg_y, new_node_pos_y, new_node_neg_z, new_node_pos_z, \
        nearest_pos_x_lines, nearest_neg_x_lines, nearest_pos_y_lines, nearest_neg_y_lines, nearest_pos_z_lines, \
        nearest_neg_z_lines = \
            self.nearest_edges(G=G,
                               node=node,
                               points=G.nodes[node]["pos"],
                               edges=belongs_to_edge_list,
                               z_flag=z_flag,
                               x_flag=x_flag,
                               y_flag=y_flag,
                               top_z_flag=top_z_flag,
                               bottom_z_flag=bottom_z_flag,
                               pos_x_flag=pos_x_flag,
                               neg_x_flag=neg_x_flag,
                               pos_y_flag=pos_y_flag,
                               neg_y_flag=neg_y_flag,
                               tol_value=tol_value)
        if direction_x is True:
            if new_node_neg_x is not None:
                node_id = f"{node}_x_neg_space"
                G, node_list, remove_edge = self.create_snapped_nodes(G=G,
                                                                      node=node,
                                                                      node_id=node_id,
                                                                      node_list=node_list,
                                                                      edge_point_B=new_node_neg_x,
                                                                      color=color,
                                                                      type_node=type_node,
                                                                      element=element,
                                                                      grid_type=grid_type,
                                                                      belongs_to=belongs_to,
                                                                      floor_belongs_to=floor_belongs_to,
                                                                      update_node=update_node,
                                                                      disjoint_flag=disjoint_flag,
                                                                      intersects_flag=intersects_flag,
                                                                      within_flag=within_flag,
                                                                      collision_type_node=collision_type_node,
                                                                      snapped_edge=nearest_neg_x_lines,
                                                                      create_snapped_edge_flag=create_snapped_edge_flag,
                                                                      remove_edge=remove_edge,
                                                                      col_tolerance=col_tolerance,
                                                                      edge_type_node=edge_type_node)
            if new_node_pos_x is not None:
                node_id = f"{node}_x_pos_space"
                G, node_list, remove_edge = self.create_snapped_nodes(G=G,
                                                                      node=node,
                                                                      node_id=node_id,
                                                                      node_list=node_list,
                                                                      edge_point_B=new_node_pos_x,
                                                                      color=color,
                                                                      type_node=type_node,
                                                                      element=element,
                                                                      grid_type=grid_type,
                                                                      belongs_to=belongs_to,
                                                                      floor_belongs_to=floor_belongs_to,
                                                                      update_node=update_node,
                                                                      disjoint_flag=disjoint_flag,
                                                                      intersects_flag=intersects_flag,
                                                                      within_flag=within_flag,
                                                                      collision_type_node=collision_type_node,
                                                                      snapped_edge=nearest_pos_x_lines,
                                                                      create_snapped_edge_flag=create_snapped_edge_flag,
                                                                      remove_edge=remove_edge,
                                                                      col_tolerance=col_tolerance,
                                                                      edge_type_node=edge_type_node)
        if direction_y is True:
            if new_node_neg_y is not None:
                node_id = f"{node}_y_neg_space"
                G, node_list, remove_edge = self.create_snapped_nodes(G=G,
                                                                      node=node,
                                                                      node_id=node_id,
                                                                      node_list=node_list,
                                                                      edge_point_B=new_node_neg_y,
                                                                      color=color,
                                                                      type_node=type_node,
                                                                      element=element,
                                                                      grid_type=grid_type,
                                                                      belongs_to=belongs_to,
                                                                      floor_belongs_to=floor_belongs_to,
                                                                      update_node=update_node,
                                                                      disjoint_flag=disjoint_flag,
                                                                      intersects_flag=intersects_flag,
                                                                      within_flag=within_flag,
                                                                      collision_type_node=collision_type_node,
                                                                      snapped_edge=nearest_neg_y_lines,
                                                                      create_snapped_edge_flag=create_snapped_edge_flag,
                                                                      remove_edge=remove_edge,
                                                                      col_tolerance=col_tolerance,
                                                                      edge_type_node=edge_type_node)
            if new_node_pos_y is not None:
                node_id = f"{node}_y_pos_space"
                G, node_list, remove_edge = self.create_snapped_nodes(G=G,
                                                                      node=node,
                                                                      node_id=node_id,
                                                                      node_list=node_list,
                                                                      edge_point_B=new_node_pos_y,
                                                                      color=color,
                                                                      type_node=type_node,
                                                                      element=element,
                                                                      grid_type=grid_type,
                                                                      belongs_to=belongs_to,
                                                                      floor_belongs_to=floor_belongs_to,
                                                                      update_node=update_node,
                                                                      disjoint_flag=disjoint_flag,
                                                                      intersects_flag=intersects_flag,
                                                                      within_flag=within_flag,
                                                                      collision_type_node=collision_type_node,
                                                                      snapped_edge=nearest_pos_y_lines,
                                                                      create_snapped_edge_flag=create_snapped_edge_flag,
                                                                      remove_edge=remove_edge,
                                                                      col_tolerance=col_tolerance,
                                                                      edge_type_node=edge_type_node)
        if direction_z is True:
            if new_node_neg_z is not None:
                node_id = f"{node}_z_neg_space"
                G, node_list, remove_edge = self.create_snapped_nodes(G=G,
                                                                      node=node,
                                                                      node_id=node_id,
                                                                      node_list=node_list,
                                                                      edge_point_B=new_node_neg_z,
                                                                      color=color,
                                                                      type_node=type_node,
                                                                      element=element,
                                                                      grid_type=grid_type,
                                                                      belongs_to=belongs_to,
                                                                      floor_belongs_to=floor_belongs_to,
                                                                      update_node=update_node,
                                                                      disjoint_flag=disjoint_flag,
                                                                      intersects_flag=intersects_flag,
                                                                      within_flag=within_flag,
                                                                      collision_type_node=collision_type_node,
                                                                      snapped_edge=nearest_neg_z_lines,
                                                                      create_snapped_edge_flag=create_snapped_edge_flag,
                                                                      remove_edge=remove_edge,
                                                                      col_tolerance=col_tolerance,
                                                                      edge_type_node=edge_type_node)
            if new_node_pos_z is not None:
                node_id = f"{node}_z_pos_space"
                G, node_list, remove_edge = self.create_snapped_nodes(G=G,
                                                                      node=node,
                                                                      node_id=node_id,
                                                                      node_list=node_list,
                                                                      edge_point_B=new_node_pos_z,
                                                                      color=color,
                                                                      type_node=type_node,
                                                                      element=element,
                                                                      grid_type=grid_type,
                                                                      belongs_to=belongs_to,
                                                                      floor_belongs_to=floor_belongs_to,
                                                                      update_node=update_node,
                                                                      disjoint_flag=disjoint_flag,
                                                                      intersects_flag=intersects_flag,
                                                                      within_flag=within_flag,
                                                                      collision_type_node=collision_type_node,
                                                                      snapped_edge=nearest_pos_z_lines,
                                                                      create_snapped_edge_flag=create_snapped_edge_flag,
                                                                      remove_edge=remove_edge,
                                                                      col_tolerance=col_tolerance,
                                                                      edge_type_node=edge_type_node)

        return G, node_list

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

    def analyize_edge_direction(self, G: nx.Graph(), edge_1, edge_2):

        pass

    def analyize_network_degree(self, G: nx.Graph(), node):
        if G.degree[node] == 2:
            return "Pipe"
            # Pipe bending
        if G.degree[node] == 3:
            return "three-way-valve"
        if G.degree[node] == 4:
            return "four-way-valve"


    def add_components_on_graph(self, G, node, str_chain, tol_value: float =0.0):
        """
        Fügt Komponenten auf den Graphen hinzu.
        Args:
            G ():
            str_chain ():
        """
        # todo: Wenn von Knoten ausgeht, Kanten in diese Richtung legen,
        # todo: Wenn Kante zum Knoten führt, dann anders rum.
        G = G.copy()
        x1, y1, z1 = G.nodes[node]["pos"]
        neighbors = list(G.neighbors(node))
        for k, neighbor in enumerate(neighbors):
            last_node = None
            if G.has_edge(neighbor, node):
                G.remove_edge(neighbor, node)
            if G.has_edge(node, neighbor):
                G.remove_edge(node, neighbor)
            x2, y2, z2 = G.nodes[neighbor]["pos"]
            # Z Achse
            if abs(x1 - x2) <= tol_value and abs(y1 - y2) <= tol_value:
                diff_z = (z1 - z2)
                comp_diff = diff_z / len(str_chain)
                for i in range(0, len(str_chain)):
                    z = z1 - i * comp_diff
                    id_name = f"{node}_{str_chain[i]}_{k}"
                    pos = (x1, y1 ,z)
                    G, node_name = self.create_nodes(G=G,
                                      id_name=id_name,
                                      points=pos,
                                      color=G.nodes[node]["color"],
                                      type_node=str_chain[i],
                                      grid_type="heating_circle",
                                      direction=G.nodes[node]["direction"],
                                      update_node=True,
                                      element=G.nodes[node]["element"],
                                      belongs_to=G.nodes[node]["belongs_to"],
                                      floor_belongs_to=G.nodes[node]["floor_belongs_to"])
                    if last_node is not None:
                        node_1 = node_name
                        node_2 = node
                        length = abs(distance.euclidean(G.nodes[last_node]["pos"], pos))
                        G.add_edge(node_1,
                                   node_2,
                                   color=G.nodes[node]["color"],
                                   type="heating",
                                   grid_type="heating",
                                   direction="z",
                                   weight=length)
                    last_node = node_name
            # X Achse
            elif abs(z1 - z2) <= tol_value and abs(y1 - y2) <= tol_value:
                diff_x = (x1 - x2)
                comp_diff = diff_x / len(str_chain)
                for i in range(0, len(str_chain)):
                    x = x1 - i * comp_diff
                    id_name = f"{node}_{str_chain[i]}_{k}"
                    pos = (x, y1, z1)

                    G, node_name = self.create_nodes(G=G,
                                                      id_name=id_name,
                                                      points=pos,
                                                      color=G.nodes[node]["color"],
                                                      type_node=str_chain[i],
                                                      grid_type="heating_circle",
                                                      direction=G.nodes[node]["direction"],
                                                      update_node=True,
                                                      element=G.nodes[node]["element"],
                                                      belongs_to=G.nodes[node]["belongs_to"],
                                                      floor_belongs_to=G.nodes[node]["floor_belongs_to"])
                    if last_node is not None:
                        node_1 = node_name
                        node_2 = node
                        length = abs(distance.euclidean(G.nodes[last_node]["pos"], pos))
                        G.add_edge(node_1,
                                   node_2,
                                   color=G.nodes[node]["color"],
                                   type="heating",
                                   grid_type="heating",
                                   direction="x",
                                   weight=length)
                    last_node = node_name
            # Y Achse
            elif abs(z1 - z2) <= tol_value and abs(x1 - x2) <= tol_value:
                diff_y = (y1 - y2)
                comp_diff = diff_y / len(str_chain)
                for i in range(0, len(str_chain)):
                    y = y1 - i * comp_diff
                    id_name = f"{node}_{str_chain[i]}_{k}"
                    pos = (x1, y, z1)
                    G, node_name = self.create_nodes(G=G,
                                                      id_name=id_name,
                                                      points=pos,
                                                      color=G.nodes[node]["color"],
                                                      type_node=str_chain[i],
                                                      grid_type="heating_circle",
                                                      direction=G.nodes[node]["direction"],
                                                      update_node=True,
                                                      element=G.nodes[node]["element"],
                                                      belongs_to=G.nodes[node]["belongs_to"],
                                                      floor_belongs_to=G.nodes[node]["floor_belongs_to"])

                    if last_node is not None:
                        node_1 = node_name
                        node_2 = node
                        length = abs(distance.euclidean(G.nodes[last_node]["pos"], pos))
                        G.add_edge(node_1,
                                   node_2,
                                   color=G.nodes[node]["color"],
                                   type="heating",
                                   grid_type="heating",
                                   direction="y",
                                   weight=length)
                    last_node = node_name

            length = abs(distance.euclidean(G.nodes[last_node]["pos"], G.nodes[neighbor]["pos"]))
            G.add_edge(last_node,
                       neighbor,
                       color=G.nodes[node]["color"],
                       type="heating",
                       grid_type="heating",
                       direction="x",
                       weight=length)
        return G



    def add_component_nodes(self, G: nx.Graph(), circulation_direction: str = "forward"):
        """
        Args:
            frozen_graph ():
            circulation_direction ():
        Returns:

        """
        # todo: Verteilungssystem, Pumpe für jeden strang vom Verteilungssystem,
        radiator_dict = {}
        source_dict = {}
        source_nodes = None
        radiator_nodes = None
        for node, data in G.nodes(data=True):
            # first source
            if "source" in data['type']:
                #l_rules = "source" + "-pipe-" + "pump" + "-vented"
                #l_rules = "source" +  "-pump-" + "vented"
                l_rules  =  "-pump-" + "x[1]"
                G.nodes[node]["type"].append("distributor")
                str_chain = l_rules.split("-")
                G = self.add_components_on_graph(G=G, node=node, str_chain=str_chain)
            elif "radiator_forward" in data['type']:
                #l_rules = "ventil" + "-pipe-" "radiator"
                l_rules = "-ventil"
                str_chain = l_rules.split("-")
                G = self.add_components_on_graph(G=G, node=node, str_chain=str_chain)
            # Other sources
            elif "radiator_backward" in data['type']:
                G.nodes[node]["type"].append("vented")

                l_rules = "distributor" + "-pump-" + "pipe"
               # source_nodes = self.add_new_component_nodes(G=G, node=node, str_chain=str_chai)
            elif G.degree[node] == 2:
                pass

            elif G.degree[node] == 3:
                #l_rules = "three_way_valve"
                G.nodes[node]["type"].append("three_way_valve")
                #str_source_chain = l_rules.split("-")
                #source_nodes = self.add_components_on_graph(G=G, node=node, str_source_chain)
                #source_dict[node] = source_nodes

            elif G.degree[node] == 4:
                G.nodes[node]["type"].append("three_way_valve")

        # todo: Entlüfter, Verteiler, Ventilarten

        """if source_nodes is not None:
            for source in source_dict:
                node_list = []
                for node in source_dict[source]:
                    #print(G)
                    G, node = self.create_nodes(G=G,
                                                id_name=node,
                                                points=source_dict[source][node]["pos"],
                                                color="green",
                                                type_node=source_dict[source][node]["type"],
                                                element=node,
                                                update_node=True,
                                                grid_type="forward",
                                                belongs_to=source,
                                                floor_belongs_to=source_dict[source][node]["floor_belongs_to"])
                    #print(G)

                    node_list.append(node)
                G = self.nearest_neighbour_edge(G=G,
                                                edge_type="pipe",
                                                node=node,
                                                direction="x",
                                                grid_type=circulation_direction)
                G = self.nearest_neighbour_edge(G=G,
                                                edge_type="pipe",
                                                node=node,
                                                direction="y",
                                                grid_type=circulation_direction)"""
        """if radiator_nodes is not None:
            for rad in radiator_dict:
                for node in radiator_dict[rad]:
                    G, node = self.create_nodes(G=G,
                                                id_name=node,
                                                points=radiator_dict[rad][node]["pos"],
                                                color="red",
                                                type_node=radiator_dict[rad][node]["type"],
                                                element=node,
                                                grid_type="forward",
                                                belongs_to=rad,
                                                floor_belongs_to=radiator_dict[rad][node]["floor_belongs_to"])
                    # G.add_node(node, pos=radiator_dict[rad][node]["pos"], type=radiator_dict[rad][node]["type"], circulation_direction=circulation_direction)
                    G = self.nearest_neighbour_edge(G=G, edge_type="pipe", node=node, direction="z",
                                                    grid_type=circulation_direction)"""
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

    def get_room_edges(self,
                       G: nx.Graph(),
                       node,
                       edge_type_node: list = None,
                       exception_type_node: list = None,
                       all_edges_flag: bool = False,
                       all_edges_floor_flag: bool = False,
                       same_type_flag: bool = False,
                       element_belongs_to_flag=False,
                       belongs_to_floor=None):
        """
        Args:
            edge_type_node ():
            node (): Knoten, der mit dem Graphen verbunden werden soll.
            all_edges_flag (): Sucht alle Kanten eines Graphen
            all_edges_floor_flag (): Sucht alle Kanten einer Etage eines Graphen
            same_type_flag (): Sucht alle Kanten, die den gleichen Knoten Type haben (bspw. Space)
            element_belongs_to_flag ():
            belongs_to_floor (): ID einer Etage
            G (): Networkx Graph
        Returns:
        """
        edge_list = []
        for edge in G.edges(data=True):
            if edge[0] == node or edge[1] == node:
                continue

            if exception_type_node is not None and len(exception_type_node) > 0:
                if set(G.nodes[edge[0]]["type"]) & set(exception_type_node) & set(G.nodes[edge[1]]["type"]):
                    continue
            """if edge_type_node is not None and len(edge_type_node) > 0:
                if set(edge_type_node) & set(G.nodes[edge[0]]["type"]) and set(edge_type_node) & set(
                        G.nodes[edge[1]]["type"]):
                    if (edge[0], edge[1]) not in edge_list:
                        edge_list.append((edge[0], edge[1]))"""
            if all_edges_flag is True:
                if (edge[0], edge[1]) not in edge_list:
                    edge_list.append((edge[0], edge[1]))
            if all_edges_floor_flag is True:
                if belongs_to_floor == G.nodes[edge[0]]["floor_belongs_to"] == G.nodes[edge[1]]["floor_belongs_to"]:
                    if (edge[0], edge[1]) not in edge_list:
                        edge_list.append((edge[0], edge[1]))
            if same_type_flag is True:
                # if G.nodes[edge[0]]["floor_belongs_to"] == belongs_to_floor == G.nodes[edge[1]]["floor_belongs_to"]:
                if set(edge_type_node) & set(G.nodes[edge[0]]["type"]) or set(edge_type_node) & set(
                            G.nodes[edge[1]]["type"]):
                    """if set(edge_type_node) & set(G.nodes[edge[0]]["type"]) & set(
                        G.nodes[edge[1]]["type"]):"""
                    if (edge[0], edge[1]) not in edge_list:
                        edge_list.append((edge[0], edge[1]))
            if element_belongs_to_flag is True:
                if set(edge_type_node) & set(G.nodes[edge[0]]["type"]) and set(edge_type_node) & set(
                        G.nodes[edge[1]]["type"]):
                    """if set(edge_type_node) & set(G.nodes[edge[0]]["type"]) and set(edge_type_node) & set(
                            G.nodes[edge[1]]["type"]):"""
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

        """if len(edge_list) == 0:
            for edge in G.edges(data=True):
                #edge_list.append((G.nodes[edge[0]]["pos"], G.nodes[edge[1]]["pos"]))
                edge_list.append((edge[0], edge[1]))"""
        return edge_list

    def project_nodes_on_building(self, G: nx.Graph(), node_list, color, grid_type):
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
                    G, project_node = self.create_nodes(G=G,
                                                        id_name=f"{node}_projection_{i}",
                                                        points=projected_window_point,
                                                        color=color,
                                                        type_node=type_node,
                                                        element=element,
                                                        grid_type=grid_type,
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
                     collision_type_node: list = ["space"]
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
        if len(node_list) > 0 or node_list is not None:
            for node in node_list:
                if direction_x is True:
                    G = self.nearest_neighbour_edge(G=G,
                                                    edge_type=edge_type,
                                                    node=node,
                                                    direction="x",
                                                    grid_type=grid_type,
                                                    tol_value=tol_value,
                                                    color=color,
                                                    connect_element_together=connect_element_together,
                                                    connect_floor_spaces_together=connect_floor_spaces_together,
                                                    connect_types=connect_types,
                                                    node_type=node_type,
                                                    connect_node_flag=connect_node_flag,
                                                    connect_node_list=connect_node_list,
                                                    nearest_node_flag=nearest_node_flag,
                                                    disjoint_flag=disjoint_flag,
                                                    intersects_flag=intersects_flag,
                                                    within_flag=within_flag,
                                                    col_tol=col_tol,
                                                    collision_type_node=collision_type_node,
                                                    all_node_flag=all_node_flag)
                if direction_y is True:
                    G = self.nearest_neighbour_edge(G=G,
                                                    edge_type=edge_type,
                                                    node=node,
                                                    direction="y",
                                                    grid_type=grid_type,
                                                    tol_value=tol_value,
                                                    color=color,
                                                    connect_element_together=connect_element_together,
                                                    connect_floor_spaces_together=connect_floor_spaces_together,
                                                    connect_types=connect_types,
                                                    node_type=node_type,
                                                    connect_node_flag=connect_node_flag,
                                                    connect_node_list=connect_node_list,
                                                    nearest_node_flag=nearest_node_flag,
                                                    disjoint_flag=disjoint_flag,
                                                    intersects_flag=intersects_flag,
                                                    within_flag=within_flag,
                                                    col_tol=col_tol,
                                                    collision_type_node=collision_type_node,
                                                    all_node_flag=all_node_flag
                                                    )
                if direction_z is True:
                    G = self.nearest_neighbour_edge(G=G, edge_type=edge_type,
                                                    node=node,
                                                    direction="z",
                                                    grid_type=grid_type,
                                                    tol_value=tol_value,
                                                    color=color,
                                                    connect_element_together=connect_element_together,
                                                    connect_floor_spaces_together=connect_floor_spaces_together,
                                                    connect_types=connect_types,
                                                    node_type=node_type,
                                                    connect_node_flag=connect_node_flag,
                                                    connect_node_list=connect_node_list,
                                                    nearest_node_flag=nearest_node_flag,
                                                    disjoint_flag=disjoint_flag,
                                                    intersects_flag=intersects_flag,
                                                    within_flag=within_flag,
                                                    col_tol=col_tol,
                                                    collision_type_node=collision_type_node,
                                                    all_node_flag=all_node_flag
                                                    )

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

    def create_nodes(self,
                     G: nx.Graph(),
                     id_name,
                     points,
                     color,
                     type_node,
                     element,
                     grid_type,
                     belongs_to,
                     floor_belongs_to: str,
                     direction: str = "y",
                     tol_value: float = 0.0,
                     update_node: bool = True):
        """
        Check ob der Knoten auf der Position schon existiert, wenn ja, wird dieser aktualisiert.
        room_points = [room_dict[room]["global_corners"] for room in room_dict]
        room_tup_list = [tuple(p) for points in room_points for p in points]
        building_points = tuple(room_tup_list)
        Args:
            id_name ():
            color ():
            element ():
            grid_type ():
            belongs_to ():
            floor_belongs_to ():
            direction ():
            tol_value ():
            update_node ():
            G ():
            points ():
            circulation_direction ():
            type_node ():
        Returns:
        """
        node_pos = tuple(round(coord, 2) for coord in points)
        if update_node is True:
            for node in G.nodes():
                # if node_pos == G.nodes[node]['pos']:
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
                        'grid_type': grid_type,
                        'direction': direction,
                        "belongs_to": belongs_to_list,
                        'floor_belongs_to': floor_belongs_to
                    })
                    return G, node
        # else:
        belongs = self.check_attribute(attribute=belongs_to)
        ele = self.check_attribute(attribute=element)
        type = self.check_attribute(attribute=type_node)
        G.add_node(id_name,
                   pos=node_pos,
                   color=color,
                   type=type,
                   element=ele,
                   grid_type=grid_type,
                   belongs_to=belongs,
                   direction=direction,
                   floor_belongs_to=floor_belongs_to)
        return G, id_name

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
        type_node = room_data["type"]
        space_nodes = []
        # Erstellt Knoten für einen Space/Wand
        if room_global_corners is not None:
            for i, points in enumerate(room_global_corners):
                id_name = f"{room_ID}_{type_node}_{i}"
                G, nodes = self.create_nodes(G=G,
                                             id_name=id_name,
                                             points=points,
                                             color=color,
                                             type_node=type_node,
                                             element=room_ID,
                                             grid_type=grid_type,
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
                            color,
                            grid_type,
                            tol_value,
                            floor_belongs_to):
        element_global_corner = element_data["global_corners"]
        element_belongs_to = element_data["belongs_to"]
        type_node = element_data["type"]
        element_nodes = []
        # Punkte erstellen oder aktualisieren
        for i, points in enumerate(element_global_corner):
            id_name = f"{element_ID}_{type_node}_{element_belongs_to}_{i}"
            G, nodes = self.create_nodes(G=G,
                                         id_name=id_name,
                                         points=points,
                                         color=color,
                                         type_node=type_node,
                                         element=element_ID,
                                         grid_type=grid_type,
                                         belongs_to=element_belongs_to,
                                         direction=element_data["direction"],
                                         floor_belongs_to=floor_belongs_to,
                                         update_node=True)
            if nodes not in element_nodes:
                element_nodes.append(nodes)
        # Projiziert Elemente Knoten (Fenster, ) auf Raum Ebene (Erstellt diese auf der Gebäude Ebene)
        G, projected_nodes = self.project_nodes_on_building(G=G,
                                                            node_list=element_nodes,
                                                            color=color,
                                                            grid_type=grid_type)
        # Löscht Knoten die aufeinander liegen
        if projected_nodes is not None and len(projected_nodes) > 0:
            G, projected_nodes = self.delete_duplicate_nodes(G=G,
                                                             duplicated_nodes=projected_nodes)
            # Erstellt Kanten für Elemente (Fenster nur untereinander)
            G = self.create_edges(G=G,
                                  node_list=projected_nodes,
                                  edge_type="floor_plan",
                                  grid_type=grid_type,
                                  tol_value=tol_value,
                                  color=color,
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
                                belongs_to_floor=None,
                                # get_room_edges
                                all_edges_flag: bool = False,
                                all_edges_floor_flag: bool = False,
                                same_type_flag: bool = False,
                                element_belongs_to_flag: bool = False,
                                edge_type_node: list = None,
                                exception_type_node: list = None,
                                # snapping
                                update_node: bool = True,
                                direction_x: bool = True,
                                direction_y: bool = True,
                                direction_z: bool = True,

                                top_z_flag: bool = True,
                                bottom_z_flag: bool = True,
                                pos_x_flag: bool = True,
                                neg_x_flag: bool = True,
                                pos_y_flag: bool = True,
                                neg_y_flag: bool = True,
                                z_flag: bool = True,
                                x_flag: bool = True,
                                y_flag: bool = True,
                                # collision
                                collision_type_node: list = ["space"],
                                disjoint_flag: bool = False,
                                intersects_flag: bool = False,
                                within_flag: bool = False,
                                col_tolerance: float = 0.1,
                                create_snapped_edge_flag: bool = True):
        """
        Args:
            edge_type_node (): Typknoten, die betrachtet oder explizit nicht betrachtet werden sollen
            update_node (): True: Aktualisiert Knoten, erstellt keinen Neuen Knoten, wenn auf der Position schon ein Knoten ist
            collision_type_node (): Bspw. ["space"]
            top_z_flag (): Falls False: Sucht nur in negativer z richtung
            z_flag (): Betrachtet Kanten in Z-Richtung
            x_flag ():  Betrachtet Kanten in X-Richtung
            y_flag ():  Betrachtet Kanten in Y-Richtung
            G (): Networkx Graph
            node_list (): Liste von Knoten die mit dem Graphen verbunden werden
            color (): Farbe der Knoten, die neu erstellt werden
            type_node (): Typ Art der neu erstellten Knoten

            Suchen der Kanten, auf die ein neuer Knoten gesnappt werden kann.
            all_edges_flag ():  Betrachtet alle Kanten eines Graphen G
            all_edges_floor_flag (): Betrachtet alle Kanten der Etage eines Graphen G
            same_type_flag (): Sucht alle Kanten, die den gleichen Knoten Type haben (bspw. Space)
            element_belongs_to_flag ():
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
        for i, node in enumerate(node_list):
            # Sucht alle Kanten, auf die ein Knoten gesnappt werden kann.
            for j, direction in enumerate(direction_flags):
                direction_flags = [top_z_flag, bottom_z_flag, pos_x_flag, neg_x_flag, pos_y_flag, neg_y_flag]
                for k, flag in enumerate(direction_flags):
                    if j == k:
                        direction_flags[k] = flag
                        # Setze alle anderen Flags auf False (für jeden anderen Index k außer j)
                    else:
                        direction_flags[k] = False
                edge_space_list = self.get_room_edges(G=G,
                                                      node=node,
                                                      all_edges_flag=all_edges_flag,
                                                      all_edges_floor_flag=all_edges_floor_flag,
                                                      same_type_flag=same_type_flag,
                                                      belongs_to_floor=belongs_to_floor,
                                                      element_belongs_to_flag=element_belongs_to_flag,
                                                      edge_type_node=edge_type_node,
                                                      exception_type_node=exception_type_node)
                """if "source" in set(G.nodes[node]["type"]):
                    netx.visulize_networkx(G=G)"""
                G, new_auxiliary_nodes = self.snapping(G=G,
                                                       node=node,
                                                       color=color,
                                                       belongs_to=G.nodes[node]["belongs_to"],
                                                       belongs_to_edge_list=edge_space_list,
                                                       type_node=type_node,
                                                       grid_type=G.nodes[node]["grid_type"],
                                                       element=G.nodes[node]["element"],
                                                       floor_belongs_to=G.nodes[node]["floor_belongs_to"],
                                                       update_node=update_node,
                                                       direction_x=direction_x,
                                                       direction_y=direction_y,
                                                       direction_z=direction_z,
                                                       #top_z_flag=top_z_flag,
                                                       #bottom_z_flag=bottom_z_flag,
                                                       #pos_x_flag=pos_x_flag,
                                                       #neg_x_flag=neg_x_flag,
                                                       #pos_y_flag=pos_y_flag,
                                                       #neg_y_flag=neg_y_flag,
                                                       top_z_flag=direction_flags[0],
                                                       bottom_z_flag=direction_flags[1],
                                                       pos_x_flag=direction_flags[2],
                                                       neg_x_flag=direction_flags[3],
                                                       pos_y_flag=direction_flags[4],
                                                       neg_y_flag=direction_flags[5],
                                                       z_flag=z_flag,
                                                       x_flag=x_flag,
                                                       y_flag=y_flag,
                                                       disjoint_flag=disjoint_flag,
                                                       intersects_flag=intersects_flag,
                                                       within_flag=within_flag,
                                                       edge_type_node=edge_type_node,
                                                       collision_type_node=collision_type_node,
                                                       create_snapped_edge_flag=create_snapped_edge_flag,
                                                       col_tolerance=col_tolerance)
                """if "source" in set(G.nodes[node]["type"]):
                    netx.visulize_networkx(G=G)
                    plt.show()
                    for aux in new_auxiliary_nodes:

                        print(aux)
                        print(G.nodes[aux]["pos"])
                        neighbor = list(G.neighbors(aux))
                        for neigh in neighbor:
                            print(G.nodes[neigh]["pos"])
                            pass"""

                """if aux not in node_list:
                    node_list.append(aux)"""
        return G

    def create_building_nx_network(self,
                                   floor_dict_data: dict,
                                   grid_type: str,
                                   edge_type: str,
                                   color: str = "red",
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
            floor_spaces = []
            wall_list = []
            G = nx.Graph(grid_type="building")
            # H = nx.Graph(grid_type="Heating")
            for room in floor_dict_data[floor_id]["rooms"]:
                room_data = floor_dict_data[floor_id]["rooms"][room]
                room_elements = room_data["room_elements"]
                G, space_nodes = self.create_space_grid(G=G,
                                                        room_data=room_data,
                                                        room_ID=room,
                                                        color="black",
                                                        tol_value=tol_value,
                                                        edge_type="space",
                                                        grid_type="space",
                                                        floor_belongs_to=floor_id,
                                                        #update_node=False,
                                                        update_node=False,
                                                        direction_x=True,
                                                        direction_y=True,
                                                        direction_z=True,
                                                        connect_element_together=True,
                                                        connect_floors=False,
                                                        nearest_node_flag=True,
                                                        connect_node_flag=False,
                                                        intersects_flag=False)
                for element in room_elements:
                    element_data = room_elements[element]
                    element_global_corner = element_data["global_corners"]
                    type_node = element_data["type"]
                    # Erstellt Knoten für Fenster
                    if room_elements[element]["type"] == "wall":
                        if room_elements[element]["global_corners"] is not None:
                            """G, wall_nodes = self.create_space_grid(G=G,
                                                                   room_data=room_elements[element],
                                                                   room_ID=element,
                                                                   color="grey",
                                                                   tol_value=tol_value,
                                                                   edge_type="wall",
                                                                   grid_type="wall",
                                                                   #update_node=False,
                                                                   update_node=False,
                                                                   floor_belongs_to=floor_id,
                                                                   direction_y=True,
                                                                   direction_z=True,
                                                                   direction_x=True,
                                                                   connect_element_together=True,
                                                                   connect_node_flag=True,
                                                                   intersects_flag=False)"""
                            G, center_wall = self.center_element(G=G,
                                                                 global_corners=room_elements[element][
                                                                     "global_corners"],
                                                                 color="grey",
                                                                 type_node="center_wall",
                                                                 room_data=room_elements[element],
                                                                 room_ID=element,
                                                                 grid_type="center_wall",
                                                                 floor_belongs_to=floor_id,
                                                                 update_node=True,
                                                                 edge_type="center_wall")
                # Jeder Space hat Elemente wie Fenster, Türen, Wände
                for element in room_elements:
                    if room_elements[element]["type"] == "window":
                        if room_elements[element]["global_corners"] is not None:
                            # Projiziert Knoten auf nächstes Polygon
                            G, projected_nodes = self.create_element_grid(G=G,
                                                                          element_data=room_elements[element],
                                                                          element_ID=element,
                                                                          tol_value=tol_value,
                                                                          color="red",
                                                                          grid_type=grid_type,
                                                                          floor_belongs_to=floor_id)
                            # Verbindet Projezierte Knoten über Snapping an die nächste Kante
                            if projected_nodes is not None and len(projected_nodes) > 0:
                                G = self.connect_nodes_with_grid(G=G,
                                                                 node_list=projected_nodes,
                                                                 color="grey",
                                                                 type_node=["snapped_window_nodes"],
                                                                 element_belongs_to_flag=True,
                                                                 #exception_type_node=["window"],
                                                                 edge_type_node=["space",
                                                                                 "snapped_window_nodes",
                                                                                 "snapped_door_nodes",
                                                                                 "center_wall"],
                                                                 top_z_flag=False,
                                                                 x_flag=False,
                                                                 y_flag=False,
                                                                 z_flag=True,
                                                                 update_node=True,
                                                                 collision_type_node=["space"],
                                                                 intersects_flag=True,
                                                                 create_snapped_edge_flag=True)
                    if room_elements[element]["type"] == "door":
                        if room_elements[element]["global_corners"] is not None:
                            # Projiziert Knoten auf nächstes Polygon
                            G, projected_nodes = self.create_element_grid(G=G,
                                                                          element_data=room_elements[element],
                                                                          element_ID=element,
                                                                          tol_value=tol_value,
                                                                          color="blue",
                                                                          grid_type=grid_type,
                                                                          floor_belongs_to=floor_id)
                            # Verbindet projizierte Knoten über Snapping an die nächste Kante
                            if projected_nodes is not None and len(projected_nodes) > 0:
                                G = self.connect_nodes_with_grid(G=G,
                                                                 node_list=projected_nodes,
                                                                 color="grey",
                                                                 type_node=["snapped_door_nodes"],
                                                                 edge_type_node=["space",
                                                                                 "snapped_window_nodes",
                                                                                 "snapped_door_nodes"],
                                                                                 #"center_wall"],
                                                                 belongs_to_floor=floor_id,
                                                                 top_z_flag=False,
                                                                 x_flag=False,
                                                                 update_node=True,
                                                                 y_flag=False,
                                                                 z_flag=True,
                                                                 element_belongs_to_flag=True,
                                                                 collision_type_node=["space"],
                                                                 intersects_flag=True,
                                                                 create_snapped_edge_flag=True)

            # Pro Etage
            nodes = ["center_wall", "snapped_door_nodes", "snapped_window_nodes"]
            center_wall_nodes = [n for n, attr in G.nodes(data=True) if
                                 any(t in attr.get("type", []) for t in nodes) and attr.get("floor_belongs_to") == floor_id]

            G = self.connect_nodes_with_grid(G=G,
                                             node_list=center_wall_nodes,
                                             color="red",
                                             type_node=["center_wall"],
                                             edge_type_node=["center_wall"],
                                             same_type_flag=True,
                                             element_belongs_to_flag=False,
                                             belongs_to_floor=floor_id,
                                             top_z_flag=True,
                                             x_flag=True,
                                             y_flag=True,
                                             z_flag=False,
                                             direction_x=True,
                                             direction_y=True,
                                             direction_z=True,
                                             disjoint_flag=False,
                                             intersects_flag=True,
                                             within_flag=False,
                                             col_tolerance=0.1,
                                             create_snapped_edge_flag=True
                                             )


            nodes = ["center_wall", "snapped_door_nodes", "snapped_window_nodes", "door", "window"]
            subgraph_nodes = [n for n, attr in G.nodes(data=True) if any(t in attr.get("type", []) for t in nodes)]
            H = G.subgraph(subgraph_nodes)
            #netx.visulize_networkx(G=G)
            floor_graph_list.append(H)
            #plt.show()
            self.check_graph(G=H, type=f"Floor_{i}")
        # Ganzes Gebäude
        G = self.add_graphs(graph_list=floor_graph_list)

        nodes = ["center_wall", "space"]
        center_wall_nodes = [n for n, attr in G.nodes(data=True) if any(t in attr.get("type", []) for t in nodes)]
        # center_wall_nodes = [n for n, attr in G.nodes(data=True) if "center_wall" in attr.get("type")]
        G = self.create_edges(G=G,
                              node_list=center_wall_nodes,
                              edge_type=edge_type,
                              grid_type=grid_type,
                              tol_value=tol_value,
                              direction_x=False,
                              direction_y=False,
                              direction_z=True,
                              connect_types=True,
                              color="grey",
                              node_type=["center_wall"])

        self.check_graph(G=G, type=f"Floor")
        self.save_networkx_json(G=G, file="build_graph.json")
        return G



    def is_collision(self, point1, point2, existing_edges):
        for edge in existing_edges:
            if (point1 == edge[0] and point2 == edge[1]) or (point1 == edge[1] and point2 == edge[0]):
                return True
        return False

    def create_snapped_nodes(self,
                             G,
                             node,
                             node_id,
                             node_list,
                             edge_point_B,
                             color,
                             type_node,
                             element,
                             grid_type,
                             belongs_to,
                             floor_belongs_to,
                             snapped_edge,
                             edge_type_node:list,
                             remove_edge: list,
                             collision_type_node: list = ["space"],
                             update_node: bool = True,
                             disjoint_flag: bool = False,
                             intersects_flag: bool = True,
                             within_flag: bool = False,
                             create_snapped_edge_flag: bool = False,
                             col_tolerance: float = 0.1
                             ):
        """

        Args:
            G ():
            node_id ():
            node_list ():
            edge_point_B ():
            color ():
            type_node ():
            element ():
            grid_type ():
            belongs_to ():
            floor_belongs_to ():
            update_node ():
            disjoint_flag ():
            intersects_flag ():
            within_flag ():
        Returns:
        """

        if self.check_collision(G=G,
                                edge_point_A=G.nodes[node]["pos"],
                                edge_point_B=edge_point_B,
                                disjoint_flag=disjoint_flag,
                                intersects_flag=intersects_flag,
                                within_flag=within_flag,
                                tolerance=col_tolerance,
                                collision_type_node=collision_type_node) is False:
            if self.check_neighbour_nodes(G=G,
                                          edge_point_A=G.nodes[node]["pos"],
                                          edge_point_B=edge_point_B) is False:
                G, id_name = self.create_nodes(G=G,
                                               id_name=node_id,
                                               points=edge_point_B,
                                               color=color,
                                               type_node=type_node,
                                               element=element,
                                               grid_type=grid_type,
                                               belongs_to=belongs_to,
                                               floor_belongs_to=floor_belongs_to,
                                               update_node=update_node)
                node_list.append(id_name)
                if create_snapped_edge_flag is True:
                    direction = G.get_edge_data(snapped_edge[0][0], snapped_edge[0][1])["direction"]
                    grid_type = G.get_edge_data(snapped_edge[0][0], snapped_edge[0][1])["grid_type"]
                    edge_type = G.get_edge_data(snapped_edge[0][0], snapped_edge[0][1])["type"]
                    if G.has_edge(snapped_edge[0][0], snapped_edge[0][1]):
                        G.remove_edge(snapped_edge[0][0], snapped_edge[0][1])
                    if G.has_edge(snapped_edge[0][1], snapped_edge[0][0]):
                        G.remove_edge(snapped_edge[0][1], snapped_edge[0][0])
                    if (snapped_edge[0][0], snapped_edge[0][1]) not in remove_edge:
                        remove_edge.append((snapped_edge[0][0], snapped_edge[0][1]))
                    if snapped_edge[0][0] != id_name:
                        G.add_edge(snapped_edge[0][0],
                                   id_name,
                                   color="grey",
                                   type=edge_type,
                                   grid_type=grid_type,
                                   direction=direction,
                                   weight=abs(
                                       distance.euclidean(G.nodes[snapped_edge[0][0]]["pos"], G.nodes[id_name]["pos"])))
                    if snapped_edge[0][1] != id_name:
                        G.add_edge(id_name,
                                   snapped_edge[0][1],
                                   color="grey",
                                   type=edge_type,
                                   grid_type=grid_type,
                                   direction=direction,
                                   weight=abs(
                                       distance.euclidean(G.nodes[snapped_edge[0][1]]["pos"], G.nodes[id_name]["pos"])))
                    if id_name != node:
                        G.add_edge(id_name,
                                   node,
                                   color="grey",
                                   type=edge_type,
                                   grid_type=grid_type,
                                   direction=direction,
                                   weight=abs(
                                       distance.euclidean(G.nodes[node]["pos"], G.nodes[id_name]["pos"])))
                    G, z_list, x_list, y_list = self.remove_edges_from_node(G=G, node=id_name)
                    G, z_list, x_list, y_list = self.remove_edges_from_node(G=G, node=node)
                    G = self.create_edges(G=G,
                                          node_list=[node],
                                          direction_x=True,
                                          direction_y=True,
                                          nearest_node_flag=True,
                                          connect_types=True,
                                          #node_type=type_node,
                                          node_type=edge_type_node,
                                          edge_type=edge_type,
                                          color="grey",
                                          grid_type=grid_type)
                    G = self.create_edges(G=G,
                                      node_list=[id_name],
                                      direction_x=True,
                                      direction_y=True,
                                      nearest_node_flag=True,
                                      connect_types=True,
                                      #node_type=type_node,
                                      node_type=edge_type_node,
                                      edge_type=edge_type,
                                      color="grey",
                                      grid_type=grid_type)

                    #print(G.degree(id_name))
                    #print(G.degree(node))

                    """if "center_wall" in set(G.nodes[node]["type"]):
                        print(G.degree(id_name))
                        netx.visulize_networkx(G=G)

                        plt.show()"""
                    """if len(x_list) ==0:
                        print("nichts gelöscht")
                    for x in x_list:
                        print("delete", G.nodes[x]['pos'])"""
                    #print("test")
                    """if id_name == "2XPyKWY018sA1ygZKgQPtU_center_wall_center_0_x_neg_space":
                        print(G.degree(id_name))
                        if len(x_list) == 0:
                            print("nichts gelöscht")
                        for x in x_list:
                            print("delete", G.nodes[x]['pos'])"""
                    #print(G.nodes[snapped_edge[0][0]]["type"])
                    #print(G.nodes[snapped_edge[0][1]]["type"])
                    """if id_name == "1zOBw0Gej5Wf0QAJfHnOc0_window_2dQFggKBb1fOc1CqZDIDlx_0_projection_0_z_pos_space_x_pos_space":
                        print(id_name)
                        print(snapped_edge[0][1])
                        print(snapped_edge[0][0])
                        print(G.nodes[snapped_edge[0][0]]["pos"])
                        print(G.nodes[snapped_edge[0][1]]["pos"])
                    if id_name == "1zOBw0Gej5Wf0QAJfHnOc0_window_2dQFggKBb1fOc1CqZDIDlx_2_projection_2_z_pos_space_x_pos_space":
                        print(id_name)
                        t = "1zOBw0Gej5Wf0QAJfHnOc0_window_2dQFggKBb1fOc1CqZDIDlx_0_projection_0_z_pos_space_x_pos_space"
                        es = (list(G.neighbors(t)))
                        for a in es:
                            print(a)
                            print(G.nodes[a]["pos"])
                        print(G.nodes[snapped_edge[0][0]]["pos"])
                        print(G.nodes[snapped_edge[0][1]]["pos"])"""
        return G, node_list, remove_edge

    def save_networkx_json(self, G, file):

        data = json_graph.node_link_data(G)
        with open(file, 'w') as f:
            json.dump(data, f)

    """def reduce_nodes(self,G, coordinate):
        # todo: Nochmal implementieren, wenn alles läuft
        import networkx as nx
        import numpy as np
        from sklearn.cluster import AgglomerativeClustering
        threshold = 1
        node_positions = nx.get_node_attributes(G, "pos")
        node_list = list(G.nodes())
        dist_matrix = np.zeros((len(node_list), len(node_list)))
        for i, ni in enumerate(node_list):
            pi = node_positions[ni]
            for j, nj in enumerate(node_list):
                if i == j:
                    dist_matrix[i, j] = 0
                    continue
                pj = node_positions[nj]
                if coordinate == "x":
                    dist_matrix[i, j] = abs(pi[0] - pj[0])
                elif coordinate == "y":
                    dist_matrix[i, j] = abs(pi[1] - pj[1])
                elif coordinate == "z":
                    dist_matrix[i, j] = abs(pi[2] - pj[2])
        G_new = G.copy()
        for i, ni in enumerate(node_list):
            for j, nj in enumerate(node_list):
                if i == j:
                    continue
                if dist_matrix[i, j] <= threshold:
                    new_position = list(node_positions[ni])
                    if coordinate == "x":
                        new_position[0] = (node_positions[ni][0] + node_positions[nj][0]) / 2
                        print(new_position[0])
                    elif coordinate == "y":
                        new_position[1] = (node_positions[ni][1] + node_positions[nj][1]) / 2
                    elif coordinate == "z":
                        new_position[2] = (node_positions[ni][2] + node_positions[nj][2]) / 2
                    new_position = tuple(new_position)
                    if ni in G_new.nodes and nj in G_new.nodes:
                        G_new = nx.contracted_nodes(G_new, ni, nj)
                        G_new.nodes[ni]["pos"] = new_position
                        #print(G_new)
        return G_new"""

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
                           weight=abs(distance.euclidean(G.nodes[edges[0]]["pos"], G.nodes[node]["pos"])))
                G.add_edge(edges[1],
                           node,
                           color=color,
                           type=edge_type,
                           grid_type=grid_type,
                           direction=direction,
                           weight=abs(distance.euclidean(G.nodes[edges[1]]["pos"], G.nodes[node]["pos"])))
                # edge_list.remove((edges[0], edges[1]))
                edge_list.append((edges[0], node))
                edge_list.append((edges[1], node))

        return G, edge_list

    def kit_grid(self, G):
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
                """print(f"Der Knoten {node} ist nicht im Graphen enthalten.")
                G = self.create_edges(G=G, node_list=[node], color="black", edge_type="floor_plan",
                                  grid_type="building")"""
                G_connected = nx.connected_components(G)

                G_largest_component = max(G_connected, key=len)
                G = G.subgraph(G_largest_component)
            """
            if G.has_edge(1, node):
                print(f"Es existiert eine Kante zwischen Knoten 1 und {node}.")
            else:
                print(f"Es existiert keine Kante zwischen Knoten 1 und {node}.")"""
        return G

    def visulize_networkx(self, G):
        """
        [[[0.2 4.2 0.2]
            [0.2 0.2 0.2]]
        Args:
            G ():

        """
        node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values(), key=lambda x: (x[0], x[1], x[2])))
        #node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values()))
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        ax.scatter(*node_xyz.T, s=10, ec="w")
        for u, v in G.edges():
            edge = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos'])])
            ax.plot(*edge.T, color=G.edges[u, v]['color'])
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
        fig.tight_layout()

    def visualzation_networkx_3D(self, G, minimum_trees: list):

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
                    ax.plot(*edge.T, color="red")
                else:
                    ax.plot(*edge.T, color="blue")

            node_xyz = np.array(
                sorted([data["pos"] for n, data in minimum_tree.nodes(data=True) if {"radiator"} in set(data["type"])]))
            if len(node_xyz) > 0 and node_xyz is not None:
                ax.scatter(*node_xyz.T, s=10, ec="red")
            node_xyz = np.array(sorted([data["pos"] for n, data in minimum_tree.nodes(data=True) if
                                        set(data["type"]) not in {"source"} and {"radiator"}]))
            if len(node_xyz) > 0 and node_xyz is not None:
                ax.scatter(*node_xyz.T, s=100, ec="yellow")
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
        fig.tight_layout()

    def create_node_on_edge_overlap(self,
                                    G,
                                    color,
                                    type_node: list,
                                    connect_projected_node_flag: bool = False,
                                    type_flag: bool = False,
                                    all_edges_flag: bool = True):
        # Iteriere über alle Kantenpaare
        remove_edge_list = []
        intersect_list = []
        edge_list = list(G.edges())
        for i, e1 in enumerate(edge_list):
            for e2 in edge_list:
                cross_flag = False
                # Überspringe das gleiche Kantenpaar
                if e1 != e2:
                    if G.nodes[e1[0]]['pos'][2] == G.nodes[e1[1]]['pos'][2] == G.nodes[e2[0]]['pos'][2] == \
                            G.nodes[e2[1]]['pos'][2]:
                        if type_flag is True:
                            if set(type_node) & set(G.nodes[e1[0]]["type"]) & set(G.nodes[e1[1]]["type"]) and set(
                                    type_node) & set(G.nodes[e2[0]]["type"]) & set(G.nodes[e2[1]]["type"]):
                                l1 = LineString([G.nodes[e1[0]]['pos'][0:2], G.nodes[e1[1]]['pos'][0:2]])
                                l2 = LineString([G.nodes[e2[0]]['pos'][0:2], G.nodes[e2[1]]['pos'][0:2]])
                                if l1.crosses(l2):
                                    cross_flag = True
                        elif all_edges_flag is True:
                            l1 = LineString([G.nodes[e1[0]]['pos'][0:2], G.nodes[e1[1]]['pos'][0:2]])
                            l2 = LineString([G.nodes[e2[0]]['pos'][0:2], G.nodes[e2[1]]['pos'][0:2]])
                            if l1.crosses(l2):
                                cross_flag = True
                        if cross_flag is True:
                            if l1.crosses(l2):
                                # Erstelle neue Knoten
                                intersection = l1.intersection(l2)
                                pos = (intersection.x, intersection.y, G.nodes[e2[0]]['pos'][2])
                                # id_name = f"{e1[0]}_{e2[0]}_{e1[1]}_{e2[1]}branching_{i}"
                                id_name = f"{e1[0]}_{e2[0]}_branching_{i}"
                                G, intersect_node = self.create_nodes(G=G,
                                                                      id_name=id_name,
                                                                      points=pos,
                                                                      color=color,
                                                                      type_node=type_node,
                                                                      element=G.nodes[e1[0]]["element"],
                                                                      grid_type=G.nodes[e1[0]]["grid_type"],
                                                                      belongs_to=G.nodes[e1[0]]["belongs_to"],
                                                                      direction=G.nodes[e1[0]]["direction"],
                                                                      update_node=True,
                                                                      floor_belongs_to=G.nodes[e1[0]][
                                                                          "floor_belongs_to"])

                                if intersect_node not in intersect_list:
                                    intersect_list.append(intersect_node)
                                if e2[0] not in remove_edge_list:
                                    remove_edge_list.append(e2[0])
                                if e2[1] not in remove_edge_list:
                                    remove_edge_list.append(e2[1])
                                if e1[1] not in remove_edge_list:
                                    remove_edge_list.append(e1[1])
                                if e1[0] not in remove_edge_list:
                                    remove_edge_list.append(e1[0])
                                # Lösche alte Kanten
                                if G.has_edge(e1[0], e1[1]):
                                    G.remove_edge(e1[0], e1[1])
                                    edge_list.remove((e1[0], e1[1]))
                                if G.has_edge(e1[1], e1[0]):
                                    G.remove_edge(e1[1], e1[0])
                                    edge_list.remove((e1[1], e1[0]))
                                if G.has_edge(e2[0], e2[1]):
                                    G.remove_edge(e2[0], e2[1])
                                    edge_list.remove((e2[0], e2[1]))
                                if G.has_edge(e2[1], e2[0]):
                                    G.remove_edge(e2[1], e2[0])
                                    edge_list.remove((e2[1], e2[0]))
                                # Erstellt neue Kanten zwischen neuen Knoten und den alten Knoten
                                # e1[0]
                                if G.has_edge(intersect_node, e1[0]) is False and G.has_edge(e1[0],
                                                                                             intersect_node) is False:
                                    length = abs(distance.euclidean(G.nodes[e1[0]]["pos"], pos))
                                    G.add_edge(intersect_node,
                                               e1[0],
                                               color=color,
                                               type=G.nodes[e1[0]]["type"],
                                               grid_type=G.nodes[e1[0]]["grid_type"],
                                               direction=G.nodes[e1[0]]["direction"],
                                               weight=length)
                                    edge_list.append((intersect_node, e1[0]))
                                # e1[1]
                                if G.has_edge(e1[1], intersect_node) is False and G.has_edge(intersect_node,
                                                                                             e1[1]) is False:
                                    length = abs(distance.euclidean(G.nodes[e1[1]]["pos"], pos))
                                    G.add_edge(e1[1],
                                               intersect_node,
                                               color=color,
                                               type=G.nodes[e1[1]]["type"],
                                               grid_type=G.nodes[e1[1]]["grid_type"],
                                               direction=G.nodes[e1[1]]["direction"],
                                               weight=length)
                                    edge_list.append((e1[1], intersect_node))
                                # e2[0]
                                if G.has_edge(intersect_node, e2[0]) is False and G.has_edge(e2[0],
                                                                                             intersect_node) is False:
                                    length = abs(distance.euclidean(G.nodes[e2[0]]["pos"], pos))
                                    G.add_edge(intersect_node,
                                               e2[0],
                                               color=color,
                                               type=G.nodes[e2[0]]["type"],
                                               grid_type=G.nodes[e2[0]]["grid_type"],
                                               direction=G.nodes[e2[0]]["direction"],
                                               weight=length)
                                    edge_list.append((intersect_node, e2[0]))
                                # e2[1]
                                if G.has_edge(intersect_node, e2[1]) is False and G.has_edge(e2[1],
                                                                                             intersect_node) is False:
                                    length = abs(distance.euclidean(G.nodes[e2[1]]["pos"], pos))
                                    G.add_edge(intersect_node,
                                               e2[1],
                                               color=color,
                                               type=G.nodes[e2[1]]["type"],
                                               grid_type=G.nodes[e2[1]]["grid_type"],
                                               direction=G.nodes[e2[1]]["direction"],
                                               weight=length)
                                    edge_list.append((intersect_node, e2[1]))
                                    # Lösche alte Kanten
            """if G.has_edge(e1[0], e1[1]):
                G.remove_edge(e1[0], e1[1])
                edge_list.remove((e1[0], e1[1]))
            if G.has_edge(e1[1], e1[0]):
                G.remove_edge(e1[1], e1[0])
                edge_list.remove((e1[1], e1[0]))
            if G.has_edge(e2[0], e2[1]):
                G.remove_edge(e2[0], e2[1])
                edge_list.remove((e2[0], e2[1]))
            if G.has_edge(e2[1], e2[0]):
                G.remove_edge(e2[1], e2[0])
                edge_list.remove((e2[1], e2[0]))"""
        nodes = []
        for node in intersect_list:
            G = self.remove_edges_from_node(G=G, node=node)
        if connect_projected_node_flag is True:
            pass

            """G = self.create_edges(G=G,
                              node_list=intersect_list,
                              edge_type="floor_plan",
                              grid_type="test",
                              tol_value=0.0,
                              color=color,
                              direction_x=True,
                              direction_y=True,
                              direction_z=True,
                              connect_node_flag=True,
                              connect_node_list=intersect_list)"""

            # G = self.remove_edges(G=G)
            """for node in remove_edge_list:
                if G.degree[node] == 1 or G.degree[node] == 0:
                    #G.remove_node(node)
                    nodes.append(node)"""

        """for node in intersect_list:
            G = self.remove_edges_from_node(G=G, node=node)"""

        return G

    def center_element(self,
                       G,
                       global_corners,
                       color,
                       room_data,
                       room_ID,
                       edge_type,
                       grid_type,
                       type_node,
                       floor_belongs_to,
                       update_node: bool = True):
        # type_node = room_data["type"]
        room_belong_to = room_data["belongs_to"]
        x_coords = [point[0] for point in global_corners]
        y_coords = [point[1] for point in global_corners]
        z_coords = [point[2] for point in global_corners]
        z_min = np.min(z_coords)
        z_max = np.max(z_coords)
        x_diff = np.max(x_coords) - np.min(x_coords)
        y_diff = np.max(y_coords) - np.min(y_coords)
        point_list = []
        if x_diff > y_diff:
            direction = "x"
            #y = y_diff / 2 + np.min(y_coords)
            y = y_diff / 4 + np.min(y_coords)
            point_1 = (np.max(x_coords), y, z_min)
            point_2 = (np.min(x_coords), y, z_min)
            point_3 = (np.max(x_coords), y, z_max)
            point_4 = (np.min(x_coords), y, z_max)
            point_list.append(point_1)
            point_list.append(point_2)
            point_list.append(point_3)
            point_list.append(point_4)
        else:
            direction = "y"
            #x = (x_diff / 2) + np.min(x_coords)
            x = (x_diff / 4) + np.min(x_coords)
            point_1 = (x, np.max(y_coords), z_min)
            point_2 = (x, np.min(y_coords), z_min)
            point_3 = (x, np.max(y_coords), z_max)
            point_4 = (x, np.min(y_coords), z_max)
            point_list.append(point_1)
            point_list.append(point_2)
            point_list.append(point_3)
            point_list.append(point_4)
        node_list = []
        for i, point in enumerate(point_list):
            id_name = f"{room_ID}_{type_node}_center_{i}"
            G, center_node = self.create_nodes(G=G,
                                               id_name=id_name,
                                               points=point,
                                               color=color,
                                               type_node=type_node,
                                               element=room_ID,
                                               grid_type=grid_type,
                                               belongs_to=room_belong_to,
                                               direction=direction,
                                               update_node=update_node,
                                               floor_belongs_to=floor_belongs_to)
            node_list.append(center_node)
        G = self.create_edges(G=G,
                              node_list=node_list,
                              edge_type=edge_type,
                              color=color,
                              grid_type=grid_type,
                              direction_x=True,
                              direction_y=True,
                              direction_z=True,
                              tol_value=0.0,
                              connect_element_together=True,
                              connect_types=False,
                              nearest_node_flag=True,
                              node_type=["center_walls"],
                              connect_node_flag=False,
                              disjoint_flag=False,
                              intersects_flag=False,
                              within_flag=False)

        return G, node_list

    def steiner_tree(self, graph: nx.Graph(), term_points, grid_type: str = "forward"):
        """
        Args:
            graph ():
            circulation_direction ():
            floor_height ():
        # term_points = sorted([n for n, data in graph.nodes(data=True) if data["type"] in {"radiator", "source"} ])
        Returns:
        """
        steinerbaum = nx.algorithms.approximation.steinertree.steiner_tree(graph, term_points, method="kou")
        total_weight = sum([edge[2]['weight'] for edge in steinerbaum.edges(data=True)])
        print(f"Steiner Tree: {grid_type} {total_weight}")
        steinerbaum.graph["circulation_direction"] = grid_type

        return steinerbaum, total_weight

    def spanning_tree(self, graph: nx.DiGraph(), start, end_points):
        """

        Args:
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
                T.add_edge(*edge, weight=graph.get_edge_data(*edge)['weight'])
        T = nx.Graph(graph.subgraph(T.nodes()).copy())
        mst = nx.minimum_spanning_tree(T, weight="weight")
        total_weight = sum([edge[2]['weight'] for edge in mst.edges(data=True)])
        print(f"spanning Tree:{total_weight}")
        return mst

    def add_offset(self, offset, start_p, end_p, path_p):
        # start = (start_p[0] + offset, start_p[1] + offset, start_p[2])
        start = tuple((x + offset, y + offset, z) for x, y, z in start_p)
        path = tuple((x + offset, y + offset, z) for x, y, z in path_p)
        end = tuple((x + offset, y + offset, z) for x, y, z in end_p)
        return start, path, end

    def get_information_grid(self):
        pass

    def greedy_algorithmus(self, G, start, end):
        G_directed = nx.DiGraph()
        for node, data in G.nodes(data=True):
            G_directed.add_node(node, **data)
        starts = sorted([n for n, data in G_directed.nodes(data=True) if data["type"] in {"source"}])
        ends = sorted([n for n, data in G_directed.nodes(data=True) if data["type"] in {"radiator"}])
        for start in starts:
            for end in ends:
                if end != start:
                    path = nx.dijkstra_path(G, start, end)
                    for i in range(len(path) - 1):
                        G_directed.add_edge(path[i], path[i + 1])
        return G_directed

    def add_graphs(self, graph_list, grid_type: str = "forward"):
        """

        Args:
            graph_list ():

        Returns:

        """
        combined_graph = nx.Graph()
        for subgraph in graph_list:
            combined_graph = nx.union(combined_graph, subgraph)
        combined_graph.graph["circulation_direction"] = grid_type
        return combined_graph

    def directed_graph(self, G, source_nodes, grid_type: str = "forward", color: str = "red"):
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
            D.add_edge(edges[0], edges[1], grid_type=grid_type, weight=length, color="indigo")
        D.graph["grid_type"] = grid_type
        return D

    def remove_edges_from_node(self, G, node, tol_value: float = 0.0):
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
        """print(node,  G.nodes[node]['pos'])
        for x in x_list:
            print("gesamt", G.nodes[x]['pos'])"""

        # z edges
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
                if G.has_edge(node, x):
                    G.remove_edge(node, x)
        # y edges
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
                if G.has_edge(node, y):
                    G.remove_edge(node, y)
        # , z_list, x_list, y_list
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

    def create_backward(self, G, grid_type: str = "backward"):
        G_reversed = G.reverse()
        G_reversed.graph["grid_type"] = grid_type
        for node in G_reversed.nodes():
            G_reversed.nodes[node]['circulation_direction'] = grid_type
            G_reversed = nx.relabel_nodes(G_reversed, {node: node.replace("forward", "backward")})
        return G_reversed


class IfcBuildingsGeometry():

    def __init__(self, ifc_file):
        self.model = ifcopenshell.open(ifc_file)

    def __call__(self):
        room = self.room_element_position()
        floor = self.sort_room_floor(spaces_dict=room)
        floor_elements, room_dict, element_dict = self.sort_space_data(floor)
        # self.visualize_spaces()
        self.write_buildings_json(data=floor, file="buildings_json.json")
        self.write_buildings_json(data=element_dict, file="delivery_json.json")

        return floor, element_dict
        # return floor_elements, room_dict,  element_dict

    def write_buildings_json(self, data: dict, file="buildings_json.json"):
        with open(file, "w") as f:
            json.dump(data, f)

    def get_geometry(self):
        spaces = self.model.by_type("IfcSpace")
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)

        # Geometrieinformationen der Spaces und Fenster extrahieren
        for space in spaces:
            shape = ifcopenshell.geom.create_shape(settings, space).geometry
            representation = space.Representation
            if representation:
                shape_representation = representation.Representations[0]
                if shape_representation.is_a("IfcShapeRepresentation"):
                    # Abrufen der Geometrieinformationen
                    items = shape_representation.Items
                    for item in items:
                        if item.is_a("IfcFacetedBrep"):
                            for face in item.Outer.CfsFaces:
                                for bound in face.Bounds:
                                    if bound.is_a("IfcFaceOuterBound"):
                                        bound_geometry = bound.Bound
                                        if bound_geometry.is_a("IfcPolyLoop"):
                                            polygon = bound_geometry.Polygon
                                            vertices = [vertex_coords for vertex_coords in polygon]
                                            global_vertices = ifcopenshell.geom.create_shape(self.model,
                                                                                             vertices).geometry

    def sort_space_data(self, floor_elements, ref_point: tuple = (0, 0, 0)):
        """
        Args:
            floor_elements ():
            ref_point ():
        Returns:

        """
        element_dict = {}
        room_dict = {}
        start_dict = {}
        floor_dict = {}
        r_point = tuple
        for floor in floor_elements:
            _dict_floor = {}
            _dict_floor["type"] = floor_elements[floor]["type"]
            _dict_floor["height"] = floor_elements[floor]["height"]
            _dict_floor["source"] = (ref_point[0], ref_point[1], floor_elements[floor]["height"])
            floor_dict[floor] = _dict_floor
            etage = floor_elements[floor]
            rooms = etage["rooms"]
            for room in rooms:
                _room_dict = {}
                _room_dict["type"] = rooms[room]["type"]
                _room_dict["global_corners"] = rooms[room]["global_corners"]
                _room_dict["belongs_to"] = rooms[room]["belongs_to"]
                room_dict[room] = _room_dict
                elements = rooms[room]["room_elements"]
                # room_points.extend(rooms[room]["global_corners"])
                # max_coords = np.amax(rooms[room]["global_corners"], axis=0)
                # min_coords = np.amin(rooms[room]["global_corners"], axis=0)
                # room_dict[room] =
                for element in elements:
                    _element_dict = {}
                    if elements[element]["type"] == "wall":
                        corner_points = elements[element]["global_corners"]
                    if elements[element]["type"] == "door":
                        corner_points = elements[element]["global_corners"]
                    if elements[element]["type"] == "window":
                        _element_dict["type"] = elements[element]["type"]
                        _element_dict["global_corners"] = elements[element]["global_corners"]
                        _element_dict["belongs_to"] = elements[element]["belongs_to"]
                        element_dict[element] = _element_dict

                        """corner_points = elements[element]["global_corners"]
                        end_point = tuple(np.mean(corner_points, axis=0))
                        p_rounded = tuple(round(coord, 2) for coord in end_point)
                        if p_rounded[0] > max_coords[0]:
                            x_window = max_coords[0]
                        elif p_rounded[0] < min_coords[0]:
                            x_window = min_coords[0]
                        else:
                            x_window = p_rounded[0]
                        if p_rounded[1] > max_coords[1]:
                            y_window = max_coords[1]
                        elif p_rounded[1] < min_coords[1]:
                            y_window = min_coords[1]
                        else:
                            y_window = p_rounded[1]
                        p_rounded = (x_window, y_window, etage["height"])
                        
                        room_points.append(p_rounded)"""

        return floor_dict, room_dict, element_dict

    def occ_core_global_points(self, element, reduce_flag: bool = True):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        shape = ifcopenshell.geom.create_shape(settings, element)
        verts = shape.geometry.verts
        grouped_verts = [(round(verts[i], 2), round(verts[i + 1], 2), round(verts[i + 2], 2)) for i in
                         range(0, len(verts), 3)]
        """grouped_verts = [(verts[i], verts[i + 1], verts[i + 2]) for i in
                         range(0, len(verts), 3)]"""
        if reduce_flag is True and len(grouped_verts) > 8:
            grouped_verts = np.array(grouped_verts)
            x_min = np.min(grouped_verts[:, 0])
            x_max = np.max(grouped_verts[:, 0])
            y_min = np.min(grouped_verts[:, 1])
            y_max = np.max(grouped_verts[:, 1])
            z_min = np.min(grouped_verts[:, 2])
            z_max = np.max(grouped_verts[:, 2])
            grouped_verts = [(x_min, y_min, z_min), \
                             (x_max, y_min, z_min), \
                             (x_max, y_max, z_min), \
                             (x_min, y_max, z_min), \
                             (x_min, y_min, z_max), \
                             (x_max, y_min, z_max), \
                             (x_max, y_max, z_max), \
                             (x_min, y_max, z_max)]
        else:
            points = np.array(grouped_verts)
            z_min = np.min(points[:, 2])

        return grouped_verts, z_min

    def visualize_spaces(self):
        import OCC.Core.TopoDS
        settings_display = ifcopenshell.geom.settings()
        settings_display.set(settings_display.USE_PYTHON_OPENCASCADE, True)
        settings_display.set(settings_display.USE_WORLD_COORDS, True)
        settings_display.set(settings_display.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings_display.set(settings_display.INCLUDE_CURVES, True)

        spaces = self.model.by_type("IfcSpace")
        windows = self.model.by_type("ifcWindow")
        display, start_display, add_menu, add_function_to_menu = init_display()
        for tz in spaces:
            color = 'blue'
            if tz.LongName:
                if 'Buero' in tz.LongName:
                    color = 'red'
                elif 'Besprechungsraum' in tz.LongName:
                    color = 'green'
                elif 'Schlafzimmer' in tz.LongName:
                    color = 'yellow'
            shape = ifcopenshell.geom.create_shape(settings_display, tz).geometry
            display.DisplayShape(shape, update=True, color=color,
                                 transparency=0.7)

        for space in windows:
            shape = ifcopenshell.geom.create_shape(settings_display, space).geometry
            display.DisplayShape(shape, update=True, transparency=0.7)
        display.FitAll()
        start_display()

    def get_pologons(self):
        import OCC.Core.TopExp as TopExp
        import OCC.Core.TopAbs as TopAbs
        import OCC.Core.BRep as BRep
        # IfcWall
        # IfcSpace
        _list = []
        walls = self.model.by_type("IfcWall")
        spaces = self.model.by_type("IfcSpace")
        doors = self.model.by_type("IfcDoor")
        window = self.model.by_type("IfcWindow")

        display, start_display, add_menu, add_function_to_menu = init_display()

        _list.append(walls)
        _list.append(spaces)
        # _list.append(doors)
        # _list.append(window)
        _list = list(walls + spaces + doors + window)
        for wall in _list:
            shape = ifcopenshell.geom.create_shape(settings, wall).geometry
            t = display.DisplayShape(shape, update=True, transparency=0.7)
            location = wall.ObjectPlacement.RelativePlacement.Location.Coordinates
            # faces = TopExp.TopExp_Explorer(shape, TopAbs.TopAbs_FACE)
            faces = TopExp.TopExp_Explorer(shape, TopAbs.TopAbs_FACE)
            while faces.More():
                # Rufen Sie die Geometrie und Position der Fläche ab
                face = faces.Current()
                face_geom = BRep.BRep_Tool.Surface(face)
                face_location = location

                # Extrahieren Sie die Koordinaten der Position
                x = face_location[0]
                y = face_location[1]
                z = face_location[2]

                # Geben Sie die Position aus
                print("Position der Wandfläche: ({}, {}, {})".format(x, y, z))

                # Zeigen Sie die Fläche in der Anzeige an
                # display.DisplayShape(face_location, update=True, transparency=0.7)

                faces.Next()

        display.FitAll()
        start_display()

        """# Iteriere über alle Wände und extrahiere Polygone
        for wall in walls:
            # Lese die Geometrie der Wand mit OpenCASCADE
            shape = ifcopenshell.geom.create_shape(settings, wall).geometry
            # Konvertiere die TopoDS_Shape in eine TopoDS_Face
            faces = OCC.Core.TopExp.TopExp_Explorer(shape, OCC.Core.TopAbs.TopAbs_FACE)
            # Iteriere über alle Faces
            while faces.More():
                face = OCC.Core.TopoDS.topods_Face(faces.Current())
                # Extrahiere Polygone
                tris = OCC.Core.BRep_Tool.BRep_Tool_Triangulation(face)
                if tris:
                    poly = OCC.Core.Poly_Triangulation.DownCast(tris)
                    # Gib die Koordinaten jedes Polygons aus
                    for i in range(1, poly.NbTriangles() + 1):
                        tri = poly.Triangle(i)
                        p1 = poly.Value(tri.Get().Get()).Coord()
                        p2 = poly.Value(tri.Get().GetNext()).Coord()
                        p3 = poly.Value(tri.Get().GetNext().GetNext()).Coord()
                faces.Next()"""

    def get_relative_matrix(self, relative_placement):
        # Definieren Sie die X-, Y- und Z-Achsen als 3x1 Spaltenvektoren.
        x_axis = np.array(relative_placement.RefDirection.DirectionRatios).reshape(3, 1)
        z_axis = np.array(relative_placement.Axis.DirectionRatios).reshape(3, 1)
        y_axis = np.cross(z_axis.T, x_axis.T).T

        # Kombinieren Sie die Achsen in eine 3x3 Rotationsmatrix.
        rotation_matrix = np.concatenate((x_axis, y_axis, z_axis), axis=1)
        # Erstellen Sie eine 4x4-Homogene Transformationsmatrix.
        relative_matrix = np.eye(4)
        relative_matrix[:3, :3] = rotation_matrix
        relative_matrix[:3, 3] = np.array(relative_placement.Location.Coordinates)
        return relative_matrix

    def get_global_matrix(self, element):
        if hasattr(element, 'ObjectPlacement'):
            if hasattr(element.ObjectPlacement.RelativePlacement.RefDirection, 'DirectionRatios'):
                matrix_chain = [self.get_relative_matrix(element.ObjectPlacement.RelativePlacement)]
                parent_placement = element.ObjectPlacement.PlacementRelTo
                if hasattr(parent_placement.RelativePlacement.RefDirection, 'DirectionRatios'):
                    while parent_placement is not None:
                        if parent_placement.RelativePlacement.RefDirection is None:
                            parent_placement = None
                        else:
                            parent_matrix = self.get_relative_matrix(parent_placement.RelativePlacement)
                            matrix_chain.insert(0, parent_matrix)
                            parent_placement = parent_placement.PlacementRelTo
                absolute_matrix = np.eye(4)
                for matrix in matrix_chain:
                    absolute_matrix = np.dot(absolute_matrix, matrix)

                return absolute_matrix
            else:
                absolute = np.array(element.ObjectPlacement.RelativePlacement.Location.Coordinates)
                placementrel = element.ObjectPlacement.PlacementRelTo
                while placementrel is not None:
                    absolute += np.array(placementrel.RelativePlacement.Location.Coordinates)
                    placementrel = placementrel.PlacementRelTo
                absolute_matrix = np.eye(4)
                absolute_matrix[:3, 3] = absolute
                return absolute_matrix

    def calc_global_position(self, element):
        if hasattr(element, 'ObjectPlacement'):
            absolute = np.array(element.ObjectPlacement.RelativePlacement.Location.Coordinates)
            placementrel = element.ObjectPlacement.PlacementRelTo
            while placementrel is not None:
                absolute += np.array(placementrel.RelativePlacement.Location.Coordinates)
                placementrel = placementrel.PlacementRelTo
        else:
            absolute = None
        return absolute

    def calc_bounding_box(self, element):
        from ifcopenshell.geom.occ_utils import get_bounding_box_center
        global_box = None
        for rep in element.Representation.Representations:
            if rep.RepresentationType == "BoundingBox":
                bound_box = rep.Items[0]
                box = bound_box.XDim, bound_box.YDim, bound_box.ZDim
                matrix = self.get_global_matrix(element=element)
                rot_matrix = matrix[:3, :3]
                global_box = np.dot(rot_matrix, box)[:3]
                break
            else:
                bbox = None
                if element.IsDefinedBy:
                    for rel in element.IsDefinedBy:

                        if rel.RelatingPropertyDefinition.is_a("IfcShapeAspect"):
                            shape_aspect = rel.RelatingPropertyDefinition
                            if shape_aspect.ShapeRepresentations:
                                for shape in shape_aspect.ShapeRepresentations:
                                    if shape.is_a("IfcProductDefinitionShape"):

                                        if shape.BoundingBox:
                                            bbox = shape.BoundingBox
                                            break
                if bbox:
                    return [
                        bbox.Corner[0].Coordinates[0],
                        bbox.Corner[0].Coordinates[1],
                        bbox.Corner[0].Coordinates[2],
                        bbox.Corner[1].Coordinates[0],
                        bbox.Corner[1].Coordinates[1],
                        bbox.Corner[1].Coordinates[2],
                    ]
        return global_box

    def ifc_path(self, element):
        path_elements = self.model.by_type("IfcPath")
        connected_paths = []
        # Durch alle IfcPath-Entitäten iterieren
        for path_element in path_elements:
            # if element.is_a("IfcWall"):
            """if element.GlobalId == path_element:
                relationship = path_element.RelatedFeatureElements[0]

                # Pfadelemente holen
                connected_path = relationship.RelatingElement.Name
                connected_paths.append(connected_path)
            # IfcRelConnectsPathElements-Beziehung abrufen
            relationship = path_element.RelatedFeatureElements[0]
            # Pfadelemente holen
            connected_path = relationship.RelatingElement.Name
            connected_paths.append(connected_path)"""

    def related_object_space(self, room):
        room_elements = []
        element_dict = {}
        for boundary_element in self.model.by_type("IfcRelSpaceBoundary"):
            if boundary_element.RelatingSpace == room:
                room_elements.append(boundary_element.RelatedBuildingElement)
        for element in room_elements:
            if element is not None:
                box = None
                if element.is_a("IfcWall"):
                    # global_corners, z_min = self.occ_core_global_points(element=element, reduce_flag=False)
                    global_corners, z_min = self.occ_core_global_points(element=element)
                    x_coords = [point[0] for point in global_corners]
                    y_coords = [point[1] for point in global_corners]
                    x_diff = np.max(x_coords) - np.min(x_coords)
                    y_diff = np.max(y_coords) - np.min(y_coords)
                    if x_diff > y_diff:
                        direction = "x"
                    else:
                        direction = "y"
                    connected_wall_ids = []
                    if element.ConnectedTo:
                        connected_wall_ids.extend([connected_wall.id() for connected_wall in element.ConnectedTo])
                    element_dict[element.GlobalId] = {"type": "wall",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      # "transformation_matrix": matrix,
                                                      # "Position": absolute_position,
                                                      "height": z_min,
                                                      # "Bounding_box": global_box,
                                                      "global_corners": global_corners,
                                                      "belongs_to": room.GlobalId,
                                                      "direction": direction,
                                                      "connected_element": connected_wall_ids
                                                      }
                if element.is_a("IfcDoor"):
                    global_corners, z_min = self.occ_core_global_points(element=element)
                    x_coords = [point[0] for point in global_corners]
                    y_coords = [point[1] for point in global_corners]
                    x_diff = np.max(x_coords) - np.min(x_coords)
                    y_diff = np.max(y_coords) - np.min(y_coords)
                    if x_diff > y_diff:
                        direction = "x"
                    else:
                        direction = "y"
                    element_dict[element.GlobalId] = {"type": "door",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      "height": z_min,
                                                      "global_corners": global_corners,
                                                      "belongs_to": room.GlobalId,
                                                      "direction": direction}
                if element.is_a("IfcWindow"):
                    global_corners, z_min = self.occ_core_global_points(element=element)
                    x_coords = [point[0] for point in global_corners]
                    y_coords = [point[1] for point in global_corners]
                    x_diff = np.max(x_coords) - np.min(x_coords)
                    y_diff = np.max(y_coords) - np.min(y_coords)
                    if x_diff > y_diff:
                        direction = "x"
                    else:
                        direction = "y"
                    element_dict[element.GlobalId] = {"type": "window",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      "height": z_min,
                                                      "global_corners": global_corners,
                                                      "belongs_to": room.GlobalId,
                                                      "direction": direction}
        return element_dict

    def floor_heights_position(self):
        floor_heights = {}
        for floor in self.model.by_type("IfcBuildingStorey"):
            floor_heights[floor.GlobalId] = {"Name": floor.Name,
                                             "height": floor.Elevation,
                                             "rooms": []}
        return floor_heights

    def absolute_points_room(self, element, matrix):
        points = []
        for rep in element.Representation.Representations:
            if rep.RepresentationType == "BoundingBox":
                bound_box = rep.Items[0]
                length, width, height = bound_box.XDim, bound_box.YDim, bound_box.ZDim
                corners = np.array(
                    [(0, 0, 0, 1), (length, 0, 0, 1), (length, width, 0, 1), (0, width, 0, 1), (0, 0, height, 1),
                     (length, 0, height, 1), (length, width, height, 1), (0, width, height, 1)])
                global_corners = corners.dot(matrix.T)
                for corner in global_corners[:, :3]:
                    c_rounded = tuple(round(coord, 2) for coord in corner)
                    points.append(tuple(c_rounded))
                return points

    def room_element_position(self):
        spaces_dict = {}
        global_box = None
        global_corners = None
        for space in self.model.by_type("IfcSpace"):
            # absolute_position = self.calc_global_position(element=space)
            # absolute position room
            # matrix = self.get_global_matrix(element=space)
            # relative_point = np.array([0, 0, 0, 1])
            # absolute_position = np.dot(matrix, relative_point)[:3]
            # Bounding box
            # global_box = self.calc_bounding_box(space)

            # global_corners = self.absolute_points_room(element=space, matrix=matrix)
            global_corners, z_min = self.occ_core_global_points(element=space)
            spaces_dict[space.GlobalId] = {"type": "space",
                                           "number": space.Name,
                                           "Name": space.LongName,
                                           "id": space.id(),
                                           "height": z_min,
                                           # "transformation_matrix": matrix,
                                           # "Position": absolute_position,
                                           # "Bounding_box": global_box,
                                           "global_corners": global_corners,
                                           "room_elements": []
                                           }
            room_elements = self.related_object_space(room=space)
            spaces_dict[space.GlobalId]["room_elements"] = room_elements
        return spaces_dict

    def sort_room_floor(self, spaces_dict):
        floor_elements = {}
        spaces_dict_copy = spaces_dict.copy()
        for floor in self.model.by_type("IfcBuildingStorey"):
            floor_elements[floor.GlobalId] = {"type": "floor",
                                              "Name": floor.Name,
                                              "height": floor.Elevation,
                                              "rooms": []}
            rooms_on_floor = {}
            for room in spaces_dict_copy:
                # space_height = spaces_dict[room]["Position"][2]
                space_height = spaces_dict[room]["height"]
                if floor.Elevation == space_height:
                    spaces_dict[room]["belongs_to"] = floor.GlobalId
                    rooms_on_floor[room] = spaces_dict[room]
            floor_elements[floor.GlobalId]["rooms"] = rooms_on_floor
        return floor_elements

    def visualzation_grid_3D(self, G):
        node_xyz = np.array([v for v in sorted(G)])
        edge_xyz = np.array([(u, v) for u, v in G.edges()])
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        # ax.scatter(*node_xyz.T, s=100, ec="w")
        for vizedge in edge_xyz:
            ax.plot(*vizedge.T, color="tab:gray")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        fig.tight_layout()
        plt.show()

    def visualzation_networkx_3D(self, G, minimum_tree, start_points, end_points):
        node_xyz = np.array([v for v in sorted(G)])
        edge_xyz = np.array([(u, v) for u, v in G.edges()])
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        # for i, coord in enumerate(points):
        #    t = tuple(round(p, 2) for p in coord)
        #    ax.text(coord[0], coord[1], coord[2], t, color='red')
        ax.scatter(*node_xyz.T, s=100, ec="w")
        for vizedge in edge_xyz:
            ax.plot(*vizedge.T, color="tab:gray")
        colors = ['r', 'g', 'b', 'y', 'm', 'c', 'w', 'r', 'g']
        for edge in minimum_tree.edges():
            xs = [edge[0][0], edge[1][0]]
            ys = [edge[0][1], edge[1][1]]
            zs = [edge[0][2], edge[1][2]]
            ax.plot(xs, ys, zs, color="red")
        for end in end_points:
            ax.scatter(*end, s=100, ec="w", color="black")
        # for start in start_points:
        #    ax.scatter(*start, s=100, ec="w", color="green")
        ax.scatter(*start_points, s=100, ec="w", color="green")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        fig.tight_layout()
        plt.show()

    def visualzation_networkx_2D(self, G, short_edges, other_edges, start_ref, end_points):
        pos = nx.spring_layout(G)
        for edge in other_edges:
            nx.draw_networkx_edges(G, pos, edgelist=edge, edge_color='black')
        for edge in short_edges:
            nx.draw_networkx_edges(G, pos, edgelist=edge, edge_color='red')
        nx.draw_networkx_nodes(G, pos)
        nx.draw_networkx_labels(G, pos)
        nx.draw_networkx_nodes(G, pos, nodelist=[start_ref], node_color='g')
        for end in end_points:
            nx.draw_networkx_nodes(G, pos, nodelist=[end], node_color='r')

    def create_grid(self, graph: nx.DiGraph, points: list):
        # self.reduce_nodes(graph=graph)
        graph = self.create_edges(graph=graph, room_points=points)
        graph = self.limit_neighbors(graph)
        self.export_graph_json(graph)
        self.load_json_pipes(graph)
        return graph

    def load_json_pipes(self, graph):
        import pandapipes as pp
        G = nx.Graph()
        G.add_edge(1, 2)
        G.add_edge(2, 3)
        net = pp.create_empty_network(name="MyNetwork")

        # Füge Knoten zum Netzwerk hinzu
        for node in G.nodes:
            pp.create_junction(net, node_name=str(node), pn_bar=1.0, tfluid_k=283.15)
        # Füge Kanten zum Netzwerk hinzu
        for edge in G.nodes:
            from_bus = str(edge[0])
            to_bus = str(edge[1])
            # Überprüfe, ob die Knoten existieren, bevor du eine Rohrleitung erstellst
            if from_bus in net.junction.index and to_bus in net.junction.index:
                pp.create_pipe_from_parameters(net, from_bus, to_bus, length_km=1, diameter_m=0.1)
            else:
                print(
                    f"Warning: Pipe {from_bus}-{to_bus} tries to attach to non-existing junction(s) {from_bus} or {to_bus}.")

        # Prüfe, ob das Netzwerk korrekt erstellt wurde

    def export_graph_json(self, G):
        data = nx.readwrite.json_graph.node_link_data(G)
        with open("graph.json", "w") as f:
            json.dump(data, f)

    def limit_neighbors(self, graph: nx.DiGraph):
        for node in graph.nodes():
            neighbors = {}
            for neighbor in graph.neighbors(node):
                direction = tuple(
                    [(neighbor[i] - node[i]) // abs(neighbor[i] - node[i]) if neighbor[i] != node[i] else 0 for i in
                     range(3)])
                if direction in neighbors and neighbors[direction]:
                    neighbors[direction].add(neighbor)
            neighbor_count = 0
            for direction in neighbors:
                direction_neighbors = sorted(list(neighbors[direction]),
                                             key=lambda neighbor: abs(neighbor[0] - node[0]) + abs(
                                                 neighbor[1] - node[1]) + abs(neighbor[2] - node[2]))
                for neighbor in direction_neighbors:
                    if neighbor_count >= 6:
                        graph.remove_edge(node, neighbor)
                    else:
                        neighbor_count += 1
        return graph

    def spanning_tree(self, graph: nx.DiGraph(), start, end_points):
        # Finden des kürzesten Pfades mit dem Dijkstra-Algorithmus für jeden Endknoten
        shortest_paths = {}
        for end_node in end_points:
            shortest_path = nx.dijkstra_path(graph, start, end_node)
            shortest_paths[end_node] = shortest_path

        # Kombinieren der Kanten der kürzesten Pfade zu einem Baum
        T = nx.Graph()
        for end_node, shortest_path in shortest_paths.items():
            for i in range(len(shortest_path) - 1):
                edge = (shortest_path[i], shortest_path[i + 1])
                T.add_edge(*edge, weight=graph.get_edge_data(*edge)['weight'])
        # Ausgabe des Ergebnisses
        mst = nx.minimum_spanning_tree(T)
        weights = [edge[2]['weight'] for edge in mst.edges(data=True)]
        total_weight = sum(weights)
        self.visualzation_networkx_3D(G=graph, minimum_tree=mst, start_points=start, end_points=end_points)
        return graph, mst, start, end_points

    def shortest_path(self, graph: nx.DiGraph(), start, end_points):
        # todo: Gewichtung: Doppelte wege
        # todo: zusätzliche Gewichtung: Z-Richtung
        # todo: https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html
        # Erstelle einen Graphen mit den Punkten als Knoten
        _short_path_edges = []
        _other_path_edges = []
        # todo: doppelte kanten verhindern
        for end in end_points:
            path = nx.dijkstra_path(graph, start, end, weight='weight')
            distance = nx.dijkstra_path_length(graph, start, end, weight='weight')
            _short_path_edges.append(list(zip(path, path[1:])))
            _other_path_edges.append([edge for edge in graph.edges() if edge not in list(zip(path, path[1:]))])
            print("Kürzester Pfad:", path)
            print("Distanz:", distance)
        return graph, _short_path_edges, _other_path_edges, start, end_points

    def calc_pipe_coordinates(self, floors, ref_point):
        # todo: referenzpunkt einer eckpunkte des spaces zu ordnen: for d in distance(x_ref, poin
        # todo: Konten reduzieren
        # todo: path_lengths = nx.multi_source_dijkstra_path_length(G, [start_node], target=end_nodes, weight='weight')
        G = nx.DiGraph()
        _short_path = []
        _other_path = []
        _end_points = []
        _room_points = []
        _start_points = []
        for floor in floors:
            room_points = []
            etage = floors[floor]
            rooms = etage["rooms"]
            r_point = (ref_point[0], ref_point[1], etage["height"])
            _start_points.append(tuple(r_point))
            room_points.append(r_point)
            # rooms[room]["Position"]
            # rooms[room]["global_corners"]
            # rooms[room]["Bounding_box"]
            # rooms[room]["room_elements"]
            room_floor_end_points = []
            # room_points_floor = []
            for room in rooms:
                elements = rooms[room]["room_elements"]
                room_points.extend(rooms[room]["global_corners"])
                max_coords = np.amax(rooms[room]["global_corners"], axis=0)
                min_coords = np.amin(rooms[room]["global_corners"], axis=0)
                for element in elements:
                    if elements[element]["type"] == "wall":
                        corner_points = elements[element]["global_corners"]
                        # x_midpoint = np.mean(corner_points[:, 0])
                        # y_midpoint = np.mean(corner_points[:, 1])
                        # z_low = np.min(corner_points[:, 2])
                        # end_point = np.array([x_midpoint, y_midpoint, z_low])
                        # end_points.append(end_point)
                    if elements[element]["type"] == "door":
                        corner_points = elements[element]["global_corners"]
                        # x_midpoint = np.mean(corner_points[:, 0])
                        # y_midpoint = np.mean(corner_points[:, 1])
                        # z_low = np.min(corner_points[:, 2])
                        # end_point = np.array([x_midpoint, y_midpoint, z_low])
                        # end_points.append(end_point)
                    if elements[element]["type"] == "window":
                        corner_points = elements[element]["global_corners"]
                        end_point = tuple(np.mean(corner_points, axis=0))
                        p_rounded = tuple(round(coord, 2) for coord in end_point)
                        if p_rounded[0] > max_coords[0]:
                            x_window = max_coords[0]
                        elif p_rounded[0] < min_coords[0]:
                            x_window = min_coords[0]
                        else:
                            x_window = p_rounded[0]
                        if p_rounded[1] > max_coords[1]:
                            y_window = max_coords[1]
                        elif p_rounded[1] < min_coords[1]:
                            y_window = min_coords[1]
                        else:
                            y_window = p_rounded[1]
                        p_rounded = (x_window, y_window, etage["height"])
                        room_floor_end_points.append(p_rounded)
                        room_points.append(p_rounded)
            G = self.create_grid(G, room_points)
            # result = self.shortest_path(graph=G, start=r_point, end_points=room_floor_end_points)
            result = self.spanning_tree(graph=G, start=r_point, end_points=room_floor_end_points)
            G = result[0]


class CalculateDistributionSystem():
    """    DIN EN 12828: Heizanlagen in Gebäuden - Planung, Installation und Betrieb
       DIN 1988: Technische Regeln für Trinkwasser-Installationen
       DIN 4751-1: Heizungsanlagen für Wärmeerzeugung - Teil 1: Bemessung
       DIN 4701: Heizlast in Gebäuden
       DIN EN 1717: Schutz des Trinkwassers in Trinkwasser-Installationen und allgemeinen Anforderungen an Sicherheitseinrichtungen"""
    """
        Berechnung der Volumenstromdichte (v):

    v = Q / (3600 * rho)

    Q: Wärmeleistung in Watt
    rho: Dichte des Mediums in kg/m³

    Berechnung des Innendurchmessers (d):

    d = 2 * sqrt(F * v / (pi * v_max))

    F: Reibungsfaktor (abhängig von der Rohroberfläche und der Strömungsgeschwindigkeit)
    v_max: Maximale Strömungsgeschwindigkeit (abhängig vom Medium)

    Berechnung des Druckverlusts (dp):

    dp = f * (L / d) * (v^2 / 2)

    f: Reibungskoeffizient (abhängig von der Rohroberfläche und der Strömungsgeschwindigkeit)
    L: Rohrlänge in Metern
    d: Rohrdurchmesser in Metern
    v: Strömungsgeschwindigkeit in m/s

    Berechnung des benötigten Pumpendrucks (p):

    p = dp + h_geod + h_zu + h_ab

    h_geod: Geodätische Höhe (Höhenunterschied zwischen Anfangs- und Endpunkt)
    h_zu: Höhendifferenz zur Pumpe (z.B. bei einem Heizkessel im Keller)
    h_ab: Höhendifferenz nach der Pumpe (z.B. bei einem höher gelegenen Heizkörper)

    Dimensionierung der Pumpe:

    Die benötigte Förderhöhe der Pumpe ergibt sich aus dem benötigten Pumpendruck (p) und dem spezifischen Gewicht des Mediums (g):

    H = p / (rho * g)

    Die benötigte Fördermenge ergibt sich aus dem Volumenstrom (Q) und der Dichte des Mediums (rho):

    Q = H * A * v

    A: Querschnittsfläche des Rohrs in m²C
    # 1. Massenstrom, Temperatur, Druck (Anfangs und Endpunkten) Ein Rohr: Δp = (128 * η * L * Q) / (π * d^4 * ρ)
    # 2. d (massenstrom, delta_p, l, v): d = (8 * Q * f * L) / (π^2 * Δp * ρ), Q = A * v = A * (volumetrische Durchflussrate) = (π * d^2 / 4) * v = (π * d^2 / 4) * (Q / A) = (π * d^2 / 4) * (2 * Δp / (ρ * v)^2)
    # 3. delta_P (d, l v, fluid)
    # 4. Massenstrom (d, delta_p) v = Q / A = (4 * Q) / (π * d^2)
    # 5. Iteration durchlaufen lassen -> Prüfen Δp = (ρ * v^2 / 2) * (1 - (A2 / A1)^2)
    """

    ureg = pint.UnitRegistry()
    m = ureg.meter
    s = ureg.second
    l = ureg.liter
    watt = ureg.watt
    kg = ureg.kg
    UNIT_CONVERSION_FACTOR = 3600

    def __init__(self,
                 c_p: float = 4.18,
                 g: float = 9.81,
                 rho: float = 1000,
                 f: float = 0.02,
                 v_mittel: float = 0.5,
                 v_max: float = 3,
                 p_max: float = 10,
                 kin_visco: float = 1.0 * 10 ** -6,
                 delta_T: int = 20):
        self.g = g
        self.rho = rho
        self.f = f
        self.v_max = v_max  # maximale Fließgeschwindigkeit (in m/s)
        self.p_max = p_max  # maximale Druckbelastung des Rohrs (i#
        self.c_p = c_p
        self.delta_T = delta_T
        self.v_mittel = v_mittel
        self.kin_visco = kin_visco

    def __call__(self, G):
        # Tiefensuche von jedem Source-Knoten aus durchführen
        """for source_node in source_nodes:
            result_nodes.extend(nx.dfs_postorder_nodes(graph, source=source_node))"""
        G = self.initilize_attribute_nodes(graph=G)
        start_node ="source_2eyxpyOx95m90jmsXLOuR0"
        # 1. Berechne Fläche der Radiatoren (Endpunkte)
        G = self.update_radiator_area_nodes(G=G, nodes=["radiator_forward"])
        # 2. Berechne Massenstrom an den Endpunkten
        G = self.update_radiator_mass_flow_nodes(G=G, nodes=["radiator_forward"])
        # 3. Iterriere von den Endknotne zum Anfangspunkt, summiere die Massenstrom an Knoten, Berechne Durchmesser der Knoten
        G = self.iterate_nodes_reverse(G=G)
        G = self.update_pipe_diameter_edges(G=G)
        # 4. Bestimmte Materialmenge: Wähle passendes Rohr aus Liste

        self.plot_nodes(G=G)
        netx.visulize_networkx(G=G)
        plt.show()
        """for node, data in G.nodes(data=True):
            print(node)
            print(data["massenstrom"])
            pass"""

        """result_nodes = list(nx.dfs_preorder_nodes(G, source=source_node))

        # Ergebnis überprüfen
        print(result_nodes)
        print(G.nodes(data=True))
        print(G.edges())
        for node in nx.dfs_postorder_nodes(G, source=source_node):
            print(node)
            if node != source_node:
                # Nachfolgende Knoten oder Kanten abrufen
                successors = G.successors(node)
                for succ in successors:
                    print(G.nodes[succ]['heat'])
                    # Q_total = sum(G.nodes[succ]['heat'])
                # Berechnung der benötigten Wärmeenergie auf Basis der nachfolgenden Knoten oder Kanten

                # Berechnung des Durchmessers basierend auf der benötigten Wärmeenergie (Verwende deine eigene Formel)
                # diameter = calculate_diameter(required_heat, total_heat)
                # diameter = self.calculate_diameter_DIN_EN_12828(Q_H=Q_total)
                # Weise den Durchmesser dem aktuellen Knoten zu
                # G.nodes[node]['diameter'] = diameter

        # Ergebnis überprüfen
        # for node in G.nodes():
        #    print(f"Knoten: {node}, Durchmesser: {G.nodes[node]['diameter']}")"""

    def update_pipe_diameter_edges(self, G):
        for edge in G.edges():
            m_flow_1 = G.nodes[edge[0]]["m_flow"]
            m_flow_2 = G.nodes[edge[1]]["m_flow"]
            G.edges[edge[0], edge[1]]['diameter'] = self.calculate_pipe_diameter(m_flow=m_flow_1)
        return G

    def iterate_nodes_reverse(self, G):
        """
        Args:
            G ():
        Returns:
        """
        # Iteriere über die Knoten in umgekehrter Reihenfolge (von den Endpunkten zum Startpunkt)
        for node in reversed(list(nx.topological_sort(G))):
            # Überprüfe, ob der Knoten Verzweigungen hat
            successors = list(G.successors(node))
            if len(successors) > 1:
                # Summiere die Massenströme der Nachfolgerknoten
                massenstrom_sum = sum(G.nodes[succ]['m_flow'] for succ in successors)
                # Speichere den summierten Massenstrom im aktuellen Knoten
                G.nodes[node]['m_flow'] = massenstrom_sum

                # Berechne den Durchmesser basierend auf dem größeren Massenfluss der Nachfolgerknoten
                m_flow_successors = [G.nodes[succ]['m_flow'] for succ in successors]
                max_m_flow = max(m_flow_successors)
                #G.edges[node, successors[0]]['diameter'] = max_m_flow
                #print(max_m_flow)
                #G.edges[node, successors[0]]['diameter'] = self.calculate_pipe_diameter(m_flow=max_m_flow)

            elif len(successors) == 1:
                # Kopiere den Massenstrom des einzigen Nachfolgerknotens
                G.nodes[node]['m_flow'] = G.nodes[successors[0]]['m_flow']
                #G.edges[node, successors[0]]['diameter'] = G.nodes[successors[0]]['m_flow']
                #print(G.nodes[successors[0]]['m_flow'])
                #G.edges[node, successors[0]]['diameter'] = self.calculate_pipe_diameter(m_flow=G.nodes[successors[0]]['m_flow'])
        # Zeige den berechneten Massenstrom für jeden Knoten an
        """for node in G.nodes:
            m_flow = G.nodes[node].get('m_flow', None)
            print(f"Knoten {G.nodes[node].get('pos', None)}  m_flow = {m_flow}")"""
        #for edge in G.edges():
        #    print("Edge:" ,G.nodes[edge[0]]["pos"] , G.nodes[edge[1]]["pos"],"- diameter:", G.edges[edge]['diameter'])
        return G

    def iterate_edges(self, G):
        for node_1, node_2 in G.edges():
            m_flow_1 = 0.1


    def plot_nodes(self, G):
        # Knotendiagramm erstellen
        t = nx.get_node_attributes(G, "pos")
        new_dict = {key: (x, y) for key, (x, y, z) in t.items()}
        node_sizes = [G.nodes[node]['m_flow'] * 1 for node in G.nodes()]  # Knotengrößen basierend auf m_flow festlegen
        node_color = ['red' if "radiator_forward" in set(G.nodes[node]['type']) else 'g' if 'source' in G.nodes[node][
            'type'] else 'b'
                      for node in G.nodes()]
        nx.draw(G,
                pos=new_dict,
                node_color=node_color,
                node_shape='o',
                node_size=node_sizes,
                font_size=12)
        edge_widths = [G.edges[edge]['diameter'] for edge in G.edges()]
        min_diameter = min(edge_widths)
        max_diameter = max(edge_widths)
        scaled_edge_widths = [(diameter - min_diameter) / (max_diameter - min_diameter) * 3 + 1 for diameter in
                              edge_widths]
        nx.draw_networkx_edges(G, pos=new_dict, width=scaled_edge_widths)
        plt.axis('off')
        plt.title('Knoten und m_flow')
        #plt.show()"""

    def calculate_massenstrom_reward(self, G, end_nodes):
        # Iteriere über die Endknoten
        for end_node in end_nodes:
            # Weise den bekannten Massenstrom am Endknoten zu
            G.nodes[end_node]['m_flow'] = 10
            # Füge die Predecessor-Knoten des Endknotens zur Warteschlange hinzu
            queue = list(G.predecessors(end_node))
            # Iteriere über die Knoten in der Warteschlange
            while queue:
                current_node = queue.pop(0)
                massenstrom = G.nodes[current_node]['m_flow']
                # Iteriere über die eingehenden Kanten des aktuellen Knotens
                for predecessor_node in G.predecessors(current_node):
                    edge = G.edges[(predecessor_node, current_node)]
                    #durchmesser = calculate_durchmesser(massenstrom)  # Funktion zur Berechnung des Rohrdurchmessers
                    # Weise den berechneten Durchmesser der Kante als Attribut zu
                    #edge['durchmesser'] = durchmesser
                    # Berechne den Massenstrom für den Vorgängerknoten
                    predecessor_massenstrom = self.calculate_successor_massenstrom(massenstrom)  # Funktion zur Berechnung des Massenstroms
                    # Wenn der Massenstrom noch nicht berechnet wurde, füge den Knoten zur Warteschlange hinzu
                    if 'm_flow' not in G.nodes[predecessor_node]:
                        queue.append(predecessor_node)
                    # Weise den berechneten Massenstrom dem Vorgängerknoten als Attribut zu
                    G.nodes[predecessor_node]['m_flow'] = predecessor_massenstrom


    def calculate_massenstrom(self, G, start_node):
        # Initialisiere den Massenstrom des Startknotens
        G.nodes[start_node]['massenstrom'] = 100
        # Erstelle eine Warteschlange und füge den Startknoten hinzu
        queue = [start_node]
        # Iteriere über die Knoten in der Warteschlange
        while queue:
            current_node = queue.pop(0)
            massenstrom = G.nodes[current_node]['massenstrom']
            # Iteriere über die ausgehenden Kanten des aktuellen Knotens
            for successor_node in G.successors(current_node):
                edge = G.edges[(current_node, successor_node)]
                #durchmesser = calculate_durchmesser(massenstrom)  # Funktion zur Berechnung des Rohrdurchmessers
                # Weise den berechneten Durchmesser der Kante als Attribut zu
                #edge['durchmesser'] = durchmesser
                # Berechne den Massenstrom für den Nachfolgeknoten
                successor_massenstrom = self.calculate_successor_massenstrom(massenstrom)  # Funktion zur Berechnung des Massenstroms
                if 'massenstrom' not in G.nodes[successor_node]:
                    # Wenn der Massenstrom noch nicht berechnet wurde, füge den Knoten zur Warteschlange hinzu
                    queue.append(successor_node)

                # Weise den berechneten Massenstrom dem Nachfolgeknoten als Attribut zu
                G.nodes[successor_node]['massenstrom'] = successor_massenstrom

    def calculate_successor_massenstrom(self, massenstrom):
        # Führe hier deine Berechnungen für den Massenstrom des Nachfolgeknotens basierend auf dem aktuellen Massenstrom und dem Durchmesser durch
        successor_massenstrom = massenstrom+massenstrom  # Berechnung des Massenstroms des Nachfolgeknotensmassenstrom
        return successor_massenstrom


    def update_radiator_mass_flow_nodes(self, G, nodes: list):
        radiator_nodes = [n for n, attr in G.nodes(data=True) if
                          any(t in attr.get("type", []) for t in nodes)]
        for node in radiator_nodes:
            Q_radiator = G.nodes[node]['heat_flow']
            m_flow = self.calculate_m_dot(Q_H=Q_radiator)
            G.nodes[node]['m_flow'] = m_flow
        return G

    def update_radiator_area_nodes(self, G, nodes: list):
        radiator_nodes = [n for n, attr in G.nodes(data=True) if
                          any(t in attr.get("type", []) for t in nodes)]
        for node in radiator_nodes:
            Q_radiator = G.nodes[node]['heat_flow']
            area = self.calculate_radiator_area(Q_H=Q_radiator)
            G.nodes[node]['area'] = area
        return G

    def initilize_attribute_nodes(self,
                                  graph):
        """

        Args:
            graph ():

        Returns:

        """
        for node in graph.nodes():
            if "radiator_forward" in graph.nodes[node]["type"]:
                Q_H = random.randint(10, 10000)
            else:
                Q_H = 0
            graph.nodes[node]['heat_flow'] = Q_H
            graph.nodes[node]['m_flow'] = self.calculate_m_dot(Q_H=Q_H)
            graph.nodes[node]['diameter'] = 0.0  # Beispiel-Durchmesser (initial auf 0 setzen)
            graph.nodes[node]['area'] = 0.0
            # Beispielattribute 'diameter' zu den Kanten hinzufügen
        for edge in graph.edges():
            graph.edges[edge]['diameter'] = 0.0  # Beispiel-Durchmesser (initial auf 0 setzen)
        return graph

    def calculate_pressure_lost(self, length, diameter):
        """
        f * (rho * v**2) / (2 * D * g)
        Args:
            length ():

        Returns:
        """
        return self.f * (self.rho * self.v_max ** 2) * length / (2 * diameter * self.g)



    def calculate_pipe_diameter(self, m_flow):
        """
        d_i = sqrt((4 * m_flow) / (pi * rho * v_max))
        Args:
            m_flow ():
        """
        return math.sqrt((4 * m_flow) / (math.pi * self.rho * self.v_max))


    def calculate_radiator_area(self, Q_H: float, alpha: float = 0.7, delta_T: int = 30):
        """
        Q_H = alpha * A * delta_T
        """
        return Q_H / (alpha * delta_T)

    def calculate_diameter_DIN_EN_12828(self, Q_H: float):
        """
        Args:
            Q_H ():
        Returns:
        """
        return 1.1 * (Q_H / (self.v_mittel * self.delta_T)) ** 0.5

    def calculate_diameter_VDI_2035(self, Q_H: float):
        # Q_vol = Q_H * Calc_pipes.watt/ (3600 * self.rho  * Calc_pipes.kg/Calc_pipes.m**3)
        Q_vol = Q_H / (3600 * self.rho)
        return (4 * self.f * Q_vol / (math.pi * self.kin_visco))

    def calculate_diameter(self, Q_H: float, delta_p: float, length: float):
        """
        Q_H = alpha *pi * (d**2 / 4) * delta_T
        d = 2 * ((m_dot / (rho * v_max * pi)) ** 0.5) * (p_max / p)
        d = (8fLQ^2)/(pi^2delta_p)
        d = (8 * Q * f * L) / (π^2 * Δp * ρ)
        """
        # return math.sqrt(4 * Q_H/(alpha * self.delta_T * math.pi))
        return (8 * self.f * length * Q_H ** 2) / (math.pi ** 2 * delta_p * self.rho)

    def calculate_m_dot(self, Q_H: float):
        """
        Q_H = m_dot * c_p * delta_T
        """
        return Q_H / (self.c_p * self.delta_T)


class PandaPipesSystem(object):

    def __init__(self, G):
        self.G = G

    def get_junction_coordinates(self, net):
        junction_data = {}
        for idx, junction in net.junction.iterrows():
            junction_coords = net.junction_geodata.loc[idx]
            junction_data[idx] = {"x": junction_coords["x"],
                                  "y": junction_coords["y"],
                                  "z": junction["height_m"]}
        return junction_data

    def calc_pipe_distance(self, x1, y1, z1, x2, y2, z2):
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)

    def create_empty_network(self):
        pass

    def connect_pipes_between_junctions(self, G, net):
        junction_data = self.get_junction_coordinates(net=net)
        for edge in G.edges:
            node_start, node_end = edge
            from_junc = None
            to_junc = None
            for id, coord in junction_data.items():
                if coord['x'] == node_start[0] and coord['y'] == node_start[1] and coord['z'] == node_start[2]:
                    from_junc = id
                if coord['x'] == node_end[0] and coord['y'] == node_end[1] and coord['z'] == node_end[2]:
                    to_junc = id
                if to_junc is not None and from_junc is not None:
                    distance = self.calc_pipe_distance(x1=junction_data[from_junc]["x"],
                                                       y1=junction_data[from_junc]["y"],
                                                       z1=junction_data[from_junc]["z"],
                                                       x2=junction_data[to_junc]["x"],
                                                       y2=junction_data[to_junc]["y"],
                                                       z2=junction_data[to_junc]["z"])
                    pp.create_pipe_from_parameters(net, from_junction=from_junc, to_junction=to_junc, diameter_m=0.5,
                                                   length_km=distance * 1e-3, k_mm=0.2, loss_coefficient=0.2,
                                                   sections=5, alpha_w_per_m2k=20,
                                                   text_k=293, qext_w=0)
                    """pp.create_pipe(net, from_junction=from_junc, to_junction=to_junc, std_type="315_PE_80_SDR_17",
                                   length_km=distance ** -3, k_mm=0.2, loss_coefficient=0.2,
                                   sections=5, alpha_w_per_m2k=20,
                                   text_k=293, qext_w=0)"""
                    break
        return net

    def create_networkx_junctions(self, G):
        net = pp.create_empty_network(fluid="water", name="Heating radiator district")
        for node in G.nodes:
            pp.create_junction(net, pn_bar=self.pressure, tfluid_k=self.temperature, geodata=(node[0], node[1]),
                               height_m=node[2])
        net = self.connect_pipes_between_junctions(G=G, net=net)

        return net

    def create_sink(self, net, end_points):
        for end in end_points:
            st_junc = pp.create_junction(net, pn_bar=self.pressure, tfluid_k=self.temperature,
                                         geodata=(end[0], end[1]), height_m=end[2], name=f"Junction{end[0]}")
            pp.create_sink(net, junction=st_junc, mdot_kg_per_s=self.m_dot)

    def create_valve(self, net):
        pp.create_valve()

    def create_source(self, net, start):
        st_junc = pp.create_junction(net, pn_bar=self.pressure, tfluid_k=self.temperature, geodata=(start[0], start[1]),
                                     height_m=start[2], name=f"Junction{start[0]}")
        pp.create_source(net, junction=st_junc, mdot_kg_per_s=self.m_dot, name="source")
        return net

    def create_pump(self, net, start):
        f_junc = pp.create_junction(net, pn_bar=self.pressure, tfluid_k=self.temperature, geodata=(start[0], start[1]),
                                    height_m=start[2], name=f"pump_1")
        t_junc = pp.create_junction(net, pn_bar=self.pressure, tfluid_k=self.temperature,
                                    geodata=(start[0], start[1] + 1),
                                    height_m=start[2], name=f"pump_2")
        """f_junc = pp.create_junction(net, pn_bar=self.pressure, tfluid_k=self.temperature, geodata=(0, 1),
                                    height_m=start[2], name=f"pump_1")
        t_junc = pp.create_junction(net, pn_bar=self.pressure, tfluid_k=self.temperature, geodata=(0, 2),
                                    height_m=start[2], name=f"pump_2")"""

        pp.create_pump(net, from_junction=f_junc, to_junction=t_junc, std_type="P1")
        return net

    def plot_systems(self, net):
        plot.simple_plot(net, plot_sinks=True, plot_sources=True, sink_size=4.0, source_size=4.0, respect_valves=True)
        pipe_results_1 = Pipe.get_internal_results(net, [0])
        Pipe.plot_pipe(net, 0, pipe_results_1)

    def hydraulic_balancing_results(self, net):
        pp.pipeflow(net, mode='all')

    def _get_attributes(self, net):
        # Rufen Sie die Junctions als DataFrame ab
        print(dir(net.junction))


if __name__ == '__main__':

    # todo: Create graph in pandapipes mit Pumpe, Valve, Heat Exchange,
    # todo: Bestimmte Druckunterschiede MIt PANDAPIPES
    # todo : Bestimme Leistung P = Q * delta_p / eta
    """start_point = ((0, 0, 0), (0, 0, 5))
    path_points = (
    (0, 0, 0), (0, 0, 5), (0, 4, 0), (0, 4, 5), (4, 4, 0), (4, 4, 5), (4, 0, 0), (4, 0, 5), (0, 0, 10), (4, 4, 10),
    (0, 4, 10), (4, 0, 10))
    end_points = ((1.5, 5, 0), (0, 6, 0), (4, 3, 0), (2, 5, 0), (1, 6, 0), (4, 3, 5), (2, 5, 5), (1, 6, 5), (0.5, 5, 0))
    floor_list = [0, 5]"""
    # ((-3.74, -1.98, 0.0), (0.66, -1.98, 2.5), [(-3.74, -1.98, 0.0), (0.66, -1.98, 2.5))

    # todo: Load ifc BuildingsGemoetry
    ifc = "C:/02_Masterarbeit/08_BIMVision/IFC_testfiles/AC20-FZK-Haus.ifc"
    #ifc ="C:/02_Masterarbeit/08_BIMVision/IFC_testfiles/AC20-Institute-Var-2.ifc"
    # ifc = "C:/02_Masterarbeit/08_BIMVision\IFC_testfiles\AC20-Institute-Var-2_with_SB-1-0.ifc"
    # ifc ="C:/02_Masterarbeit/08_BIMVision/IFC_testfiles/ERC_Mainbuilding_Arch.ifc"
    print("Load IFC modell.")
    ifc = IfcBuildingsGeometry(ifc_file=ifc)
    floor_dict, element_dict = ifc()
    height_list = [floor_dict[floor]["height"] for floor in floor_dict]
    # start_point = ((4.040, 5.990, 0), (4.040, 5.990, 2.7))
    #start_point = (4.040, 5.990, 0)
    #start_point = (4.040, 6.50, 0)
    start_point = (4.440, 6.50, 0)

    print("Load IFC modell complete.")
    #start_point = (23.9, 6.7, -2.50)

    # for i ,source in enumerate(self.source_data):
    #    G = self.create_nodes(G=G, id_name=f"{source}_{i}", points=source, color="green", type_node="source", element="source", belongs_to="floor", grid_type="forward")
    floor_dict = GeometryBuildingsNetworkx.read_buildings_json(file="buildings_json.json")
    element_dict = GeometryBuildingsNetworkx.read_buildings_json(file="delivery_json.json")
    height_list = [floor_dict[floor]["height"] for floor in floor_dict]
    netx = GeometryBuildingsNetworkx(source_data=start_point,
                                     building_data=floor_dict,
                                     delivery_data=element_dict,
                                     floor_data=height_list)

    heating_circle = netx()
    # todo: Argument belong_to mit übergeben, ID von Räumen in Knonten und Kanten etc. übergeben
    # todo: Vorkalkulation
    # Start
    calc = CalculateDistributionSystem()
    calc(G=heating_circle)
    Q_H_max = 20  # [kW]
    # m_dot_ges = calc.calculate_m_dot(Q_H=Q_H_max)
    # diameter = calc.calculate_diameter_DIN_EN_12828(Q_H=Q_H_max)
    # diameter = calc.calculate_diameter_VDI_2035(Q_H=Q_H_max)
    # heating_circle.nodes["forward_source_0"]["mass_flow"] = round(m_dot_ges, 2)
    # heating_circle.nodes["forward_source_0"]["diameter"] = round(diameter, 2)

    # delta_p(t), m_dot(t),
    for node in heating_circle.nodes(data=True):
        pass

    # for node in heating_circle.nodes(data=True)
    # for u, v, data in G.edges(data=True):

    """flow_rate = data['flow_rate']
    velocity = 1.5  # Beispielgeschwindigkeit
    diameter = calc.calculate_diameter(Q_H=Q_H, delta_p=delta_p, length=length)
    pressure_lost = calc.calculate_pressure_lost(flow_rate, diameter, 100, 0.01)

    # Füge berechnete Attribute hinzu
    data['diameter'] = diameter
    data['pressure_lost'] = pressure_lost"""
    # G.edges[u, v]['diameter'] = diameter
    # G.edges[u, v]['pressure_lost'] = pressure_lost

    # net = calc.create_networkx_junctions(G=mst)

    # calc.test_lindemayer()
    # calc._get_attributes(net=net)

    # net = netx.test_pipe(start_point=start_point, end_points=end_points, path_point=mst.edges)
    # net = netx.empty_network()
    # net = netx.create_source(net=net, start=list(mst.nodes())[0])
    # net = netx.create_pump(net=net, start=list(mst.nodes())[0])
    # calc.create_sink(net=net, end_points=end_points)

    # net = calc.create_own_network()
    # net = calc.test()
    # calc.hydraulic_balancing_results(net=net)
    # calc.plot_systems(net=net)
    # G = nx.compose(f_st, b_st)
