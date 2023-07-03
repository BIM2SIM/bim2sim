import pandas as pd
from openpyxl import load_workbook
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
from colorama import *
from mpl_toolkits.mplot3d import art3d

init(autoreset=True)
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
from pint import UnitRegistry
import os
from pathlib import Path
ureg = UnitRegistry()


class GeometryBuildingsNetworkx(object):

    def __init__(self,
                 network_building_json: Path,
                 network_heating_json: Path,
                 working_path: str,
                 ifc_model: str,
                 source_data,
                 building_data,
                 delivery_data,
                 floor_data):
        self.network_building_json = network_building_json
        self.network_heating_json = network_heating_json
        self.working_path = working_path
        self.ifc_model = ifc_model
        self.source_data = source_data
        self.building_data = building_data
        self.delivery_data = delivery_data
        self.floor_data = floor_data

    def __call__(self):
        print("Create Buildings network")
        """G = self.create_building_nx_network(floor_dict_data=self.building_data,
                                            grid_type="building",
                                            color="black",
                                            tol_value=0.0)"""

        # Delivery points

        G = self.read_json_graph(file=self.network_building_json)
        forward_graph = self.create_heating_circle(G=G,
                                                   type_delivery=["window"],
                                                   grid_type="forward")


        return forward_graph

    @staticmethod
    def read_buildings_json(file: Path = Path("buildings_json.json")):
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
            nx.set_node_attributes(G, {forward_node: {'color': 'red'}})
            nx.set_node_attributes(G, {backward_node: {'type': ['radiator_backward']}})
            nx.set_node_attributes(G, {backward_node: {'color': 'blue'}})
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
                                     color:str,
                                     start_source_point):
        source_dict = {}
        for i, floor in enumerate(floor_dict):
            _dict = {}
            pos = (start_source_point[0], start_source_point[1], floor_dict[floor]["height"])
            _dict["pos"] = pos
            _dict["type_node"] = ["heat_source"]
            _dict["element"] = f"source_{floor}"
            _dict["color"] = color
            _dict["belongs_to"] = floor
            source_dict[floor] = _dict
            if self.source_data == pos:
                _dict["type_node"] = ["heat_source", "start_node"]



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
                         same_type_flag:bool = True,
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
                                               color=color,
                                               #type_node="heat_source",
                                               type_node=type,
                                               element=element,
                                               belongs_to=floor,
                                               direction="y",
                                               update_node=True,
                                               floor_belongs_to=floor)
            print(source_node)
            source_list.append(source_node)

        G, nodes = self.connect_nodes_with_grid(  # General
            G=G,
            node_list=source_list,
            color="red",
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



    def connect_sources(self, G: nx.Graph()):
        """

        Args:
            G ():

        Returns:

        """
        element_nodes = {}
        for node, data in G.nodes(data=True):
            if "heat_source" in set(data["type"]):
                if "start_node" in set(data["type"]):
                    #if floor_belongs_to == data["floor_belongs_to"]:
                    element = data["floor_belongs_to"]
                    for ele in element:
                        if ele not in element_nodes:
                            element_nodes[ele] = []
                        element_nodes[ele].append(node)
        for element, nodes in element_nodes.items():
            length = abs(
                distance.euclidean(G.nodes[nodes[0]]["pos"], G.nodes[nodes[1]]["pos"]))
            G.add_edge(nodes[0], nodes[1],
                       color="orange",
                       type="radiator",
                       grid_type="heating_circle",
                       length=length)
        return G

    def create_heating_circle(self,
                              G: nx.Graph(),
                              grid_type: str,
                              type_delivery: list = ["window"]):

        # Erstelle Endpunkte: Hier Fenster Punkte
        delivery_forward_nodes, delivery_backward_nodes, forward_backward_edge = self.get_delivery_nodes(G=G,
                                                                                                         type_delivery=type_delivery)
        # Erstelle Anfangspunkte: Werden vorher angegeben
        # forward
        nodes_forward = ["center_wall_forward",
                         "snapped_nodes",
                         "window",
                         "radiator_forward",
                         "heat_source",
                         "door"]
        subgraph_nodes_forward = [node for node, data in G.nodes(data=True) if set(data["type"]) & set(nodes_forward)]
        forward_graph = G.subgraph(subgraph_nodes_forward)
        self.check_graph(G=forward_graph, type="forward_graph")
        forward_graph, source_forward_list = self.get_source_nodes(G=forward_graph,
                                                                   points=self.source_data,
                                                                   floor_dict=self.building_data,
                                                                   type="heat_source_forward",
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
        self.visulize_networkx(G=forward_graph, type_grid="sources")

        self.check_graph(G=forward_graph, type="forward_graph")
        # backward
        """nodes_backward = ["center_wall_backward",
                         "snapped_nodes",
                         "window",
                         "radiator_backward",
                         "heat_source",
                         "door"]
        subgraph_nodes_backward = [node for node, data in G.nodes(data=True) if set(data["type"]) & set(nodes_backward)]
        backward_graph = G.subgraph(subgraph_nodes_backward)
        self.check_graph(G=backward_graph, type="backward_graph")
        #self.visulize_networkx(G=backward_graph)
        backward_graph, source_backward_list = self.get_source_nodes(G=backward_graph,
                                                           points=self.source_data,
                                                           floor_dict=self.building_data,
                                                           type="heat_source_backward",
                                                           connect_type_edges=["center_wall_backward"],
                                                           type_node=["center_wall_backward"],
                                                           neighbor_nodes_collision_type=["center_wall_backward"],
                                                           edge_snapped_node_type="center_wall_backward",
                                                           remove_type_node=["center_wall_backward"],
                                                           grid_type="backward",
                                                           new_edge_type="center_wall_backward"
                                                            )
        self.check_graph(G=backward_graph, type="backward_graph")"""

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
            for source_node in source_forward_list:
                if forward_graph.nodes[source_node]["floor_belongs_to"] == floor:
                    element_nodes_forward.append(source_node)

            """for delivery_node in delivery_backward_nodes:
                if backward_graph.nodes[delivery_node]["floor_belongs_to"] == floor:
                    element_nodes_backward.append(delivery_node)
            # Pro Source Point pro Etage
            for source_node in source_backward_list:
                if backward_graph.nodes[source_node]["floor_belongs_to"] == floor:
                    element_nodes_backward.append(source_node)
            self.visulize_networkx(G=forward_graph)
            self.visulize_networkx(G=backward_graph)"""

            f_st, forward_total_length = self.steiner_tree(graph=forward_graph,
                                                           term_points=element_nodes_forward,
                                                           grid_type="forward")

            if forward_total_length != 0 and forward_total_length is not None:
                end_node = ["radiator_forward"]
                end_nodes = [n for n, attr in f_st.nodes(data=True) if
                             any(t in attr.get("type", []) for t in end_node)]
                f_st = self.reduce_path_nodes(G=f_st, color="red", start_nodes=[source_forward_list[i]],
                                              end_nodes=end_nodes)
                self.save_networkx_json(G=f_st,
                                        type_grid=f"heating_circle_floor_{source_forward_list[i]}",
                                        file=Path(self.working_path, self.ifc_model, f"heating_circle_floor_{source_forward_list[i]}.json"))
                self.visulize_networkx(G=forward_graph, type_grid="Building")
                self.visulize_networkx(G=f_st, type_grid="Vorlaufkreislauf")
                # self.visulize_networkx(G=forward_graph, type_grid="Vorlaufkreislauf")
                f_st = self.directed_graph(G=f_st, source_nodes=source_forward_list[i], grid_type=grid_type)
                self.check_directed_graph(G=f_st, type_graph=grid_type)
                ff_graph_list.append(f_st)
                #self.visualzation_networkx_3D(G=G, minimum_trees=[f_st], type_grid="Vorlaufkreislauf")
                #self.visulize_networkx(G=f_st, type_grid="Vorlaufkreislauf")
                #b_st = self.create_backward(G=f_st, grid_type="backward")
                #self.visulize_networkx(G=b_st, type_grid="Rückkreislauf")
                #bf_graph_list.append(b_st)
                # plt.show()

            """b_st, backward_total_length = self.steiner_tree(graph=backward_graph,
                                                            term_points=element_nodes_backward,
                                                            grid_type="backward")
            if backward_total_length != 0 and backward_total_length is not None:
                end_node = ["radiator_backward"]
                end_nodes = [n for n, attr in f_st.nodes(data=True) if
                             any(t in attr.get("type", []) for t in end_node)]
                b_st = self.reduce_path_nodes(G=b_st, color="grey", start_nodes=[source_backward_list[i]], end_nodes=end_nodes)
                #self.visulize_networkx(G=b_st)
                #self.visulize_networkx(G=backward_graph)
                b_st = self.directed_graph(G=b_st, source_nodes=source_backward_list[i], grid_type=grid_type)
                self.check_directed_graph(G=b_st, type_graph=grid_type)
                bf_graph_list.append(b_st)
                self.visualzation_networkx_3D(G=G, minimum_trees=[b_st])
                self.visulize_networkx(G=b_st)
                plt.show()"""

        f_st = self.add_graphs(graph_list=ff_graph_list)
        #b_st = self.add_graphs(graph_list=bf_graph_list)
        # Add rise tube
        self.visulize_networkx(G=f_st, type_grid="Vorlaufkreislauf")
        #self.visulize_networkx(G=b_st, type_grid="Rücklauf")

        f_st = self.add_rise_tube(G=f_st)
        #b_st = self.add_rise_tube(G=b_st)
        self.visulize_networkx(G=f_st, type_grid="Tube")
        #self.visulize_networkx(G=b_st, type_grid="Rücklaufkreislauf")
        f_st = self.add_component_nodes(G=f_st)
        #b_st = self.add_component_nodes(G=b_st)
        self.visulize_networkx(G=f_st, type_grid="Vorlaufkreislauf")
        #self.visulize_networkx(G=b_st, type_grid="Rücklaufkreislauf")

        self.check_graph(G=f_st, type="forward")
        #self.check_graph(G=b_st, type="backward")

        f_st = self.directed_graph(G=f_st, source_nodes=source_forward_list[0], grid_type=grid_type)
        b_st = self.create_backward(G=f_st, grid_type="backward", offset=0.2, color="blue")
        composed_graph = nx.disjoint_union(f_st, b_st)



        composed_graph = self.connect_sources(G=composed_graph)
        composed_graph = self.connect_forward_backward(G=composed_graph,
                                                        type_delivery="radiator_forward")

        #self.visulize_networkx(G=b_st, type_grid="Rücklaufkreislauf")
        self.visulize_networkx(G=f_st, type_grid="Vorlaufkreislauf")
        self.visulize_networkx(G=composed_graph, type_grid="Kreislauf")

        """heating_circle =  nx.disjoint_union(f_st, b_st)
        for edge in forward_backward_edge:
            heating_circle.add_edge(edge[0], edge[1])"""

        """for edge in forward_backward_edge:
            heating_circle.add_edge(edge[0], edge[1])"""

        # self.visualzation_networkx_3D(G=G, minimum_trees=[f_st])
        # self.visualize_node_order(G=f_st, type_grid="Vorlaufkreislauf")
        # self.visualize_node_order(G=b_st, type_grid="Rücklaufkreislauf")
        # self.visualzation_networkx_3D(G=G, minimum_trees=[f_st])
        # netx.visulize_networkx(G=f_st)
        # plt.show()
        # self.max_flow()
        # self.visualize_node_order(G=f_st)
        # exit(0)
        # self.check_directed_graph(G=f_st, type_graph=grid_type)

        self.save_networkx_json(G=composed_graph, file=self.network_heating_json, type_grid="heating_circle")
        plt.show()
        return f_st
        # return heating_circle

    def connect_forward_backward(self, G, type_delivery: str):
        element_nodes = {}
        for node, data in G.nodes(data=True):
            if type_delivery in set(data["type"]):
                element = data["element"]
                for ele in element:
                    if ele not in element_nodes:
                        element_nodes[ele] = []
                    element_nodes[ele].append(node)
        for element, nodes in element_nodes.items():
            length = abs(
                distance.euclidean(G.nodes[nodes[0]]["pos"], G.nodes[nodes[1]]["pos"]))
            G.add_edge(nodes[0], nodes[1],
                                    color="orange",
                                    type="radiator",
                                    grid_type="heating_circle",
                                    length=length)

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
            'red' if "radiator_forward" in set(G.nodes[node]['type']) else 'g' if 'heat_source' in G.nodes[node][
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
                            neg_neighbors: list) -> tuple[list, list]:
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
            netx.visulize_networkx(G=G,
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
                netx.visulize_networkx(G=G, type_grid=type)
                # plt.show()
                return G
            else:
                print(f"{Fore.BLACK + Back.RED} {type} Graph is not connected.")
                netx.visulize_networkx(G=G, type_grid=type)
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
            if "heat_source" in set(G.nodes[node]["type"]):
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

    def add_components_on_graph(self,
                                G,
                                node,
                                str_chain,
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
        x1, y1, z1 = G.nodes[node]["pos"]
        neighbors = list(G.neighbors(node))
        # Pro Strang des Knotens
        for k, neighbor in enumerate(neighbors):
            node_list = []
            if set(str_chain) & set(G.nodes[node]["type"]) or set(str_chain) & set(G.nodes[neighbor]["type"]):
                continue
            x2, y2, z2 = G.nodes[neighbor]["pos"]
            # Z Achse
            if z_direction is True:
                if abs(x1 - x2) <= tol_value and abs(y1 - y2) <= tol_value:
                    if G.has_edge(neighbor, node):
                        G.remove_edge(neighbor, node)
                    if G.has_edge(node, neighbor):
                        G.remove_edge(node, neighbor)
                    diff_z = (z1 - z2)
                    comp_diff = diff_z / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        id_name = f"{node}_{str_chain[i]}_{k}"
                        z = z1 - (i + 1) * comp_diff
                        pos = (x1, y1, z)
                        G, node_name = self.create_nodes(G=G,
                                                         points=pos,
                                                         color=G.nodes[node]["color"],
                                                         type_node=str_chain[i],
                                                         direction=G.nodes[node]["direction"],
                                                         update_node=True,
                                                         element=G.nodes[node]["element"],
                                                         belongs_to=G.nodes[node]["belongs_to"],
                                                         floor_belongs_to=G.nodes[node]["floor_belongs_to"])
                        node_list.append(node_name)
                    G = self.create_edges(G=G,
                                          node_list=node_list,
                                          color=G.nodes[node]["color"],
                                          edge_type="grid_type",
                                          grid_type="heating",
                                          direction_z=True,
                                          direction_x=False,
                                          direction_y=False,
                                          nearest_node_flag=True,
                                          all_node_flag=True,
                                          collision_flag=False)
            # X Achse
            if x_direction is True:
                if abs(z1 - z2) <= tol_value and abs(y1 - y2) <= tol_value:
                    if G.has_edge(neighbor, node):
                        G.remove_edge(neighbor, node)
                    if G.has_edge(node, neighbor):
                        G.remove_edge(node, neighbor)
                    diff_x = (x1 - x2)
                    comp_diff = diff_x / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        x = x1 - (i + 1) * comp_diff
                        id_name = f"{node}_{str_chain[i]}_{k}"
                        pos = (x, y1, z1)
                        G, node_name = self.create_nodes(G=G,
                                                         points=pos,
                                                         color=G.nodes[node]["color"],
                                                         type_node=str_chain[i],
                                                         direction=G.nodes[node]["direction"],
                                                         update_node=True,
                                                         element=G.nodes[node]["element"],
                                                         belongs_to=G.nodes[node]["belongs_to"],
                                                         floor_belongs_to=G.nodes[node]["floor_belongs_to"])
                        node_list.append(node_name)
                    G = self.create_edges(G=G,
                                          node_list=node_list,
                                          color=G.nodes[node]["color"],
                                          edge_type="grid_type",
                                          grid_type="heating",
                                          direction_z=False,
                                          direction_x=True,
                                          direction_y=False,
                                          nearest_node_flag=True,
                                          all_node_flag=True,
                                          collision_flag=False)

            # Y Achse
            if y_direction is True:
                if abs(z1 - z2) <= tol_value and abs(x1 - x2) <= tol_value:
                    if G.has_edge(neighbor, node):
                        G.remove_edge(neighbor, node)
                    if G.has_edge(node, neighbor):
                        G.remove_edge(node, neighbor)
                    diff_y = (y1 - y2)
                    comp_diff = diff_y / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        y = y1 - (i + 1) * comp_diff
                        id_name = f"{node}_{str_chain[i]}_{k}"
                        pos = (x1, y, z1)
                        G, node_name = self.create_nodes(G=G,
                                                         points=pos,
                                                         color=G.nodes[node]["color"],
                                                         type_node=str_chain[i],
                                                         direction=G.nodes[node]["direction"],
                                                         update_node=True,
                                                         element=G.nodes[node]["element"],
                                                         belongs_to=G.nodes[node]["belongs_to"],
                                                         floor_belongs_to=G.nodes[node]["floor_belongs_to"])
                        node_list.append(node_name)
                    G = self.create_edges(G=G,
                                          node_list=node_list,
                                          color=G.nodes[node]["color"],
                                          edge_type="grid_type",
                                          grid_type="heating",
                                          direction_z=False,
                                          direction_x=False,
                                          direction_y=True,
                                          nearest_node_flag=True,
                                          all_node_flag=True,
                                          collision_flag=False)

        return G

    def add_component_nodes(self, G: nx.Graph(), circulation_direction: str = "forward"):
        """
        Args:
            frozen_graph ():
            circulation_direction ():
        Returns:

        """
        # todo: gravity_brake, Luftsammelgefäß (höchster Strang), KFE Ventil, Rücklaufabsperrung,
        # todo: Absperrschieber, Elektrischer Stellantrieb, Rücklaufabsperrung, Differenzdruckregler,, Umwälzpumpe mit Pumpensteuerung
        # t doO. Schmutzfänger, Membranausdehnungsgefäß, Sicherheitsventil, Entwässerung

        radiator_dict = {}
        source_dict = {}
        source_nodes = None
        radiator_nodes = None
        for node, data in G.nodes(data=True):
            # first source
            if "heat_source" in data['type']:
                # l_rules = "source" + "-pipe-" + "pump" + "-vented"
                # l_rules = "source" +  "-pump-" + "vented"
                # l_rules  =  "-pump-" + "x[1]"
                l_rules = "pump"
                G.nodes[node]["type"].append("distributor")
                str_chain = l_rules.split("-")
                G = self.add_components_on_graph(G=G,
                                                 node=node,
                                                 str_chain=str_chain,
                                                 z_direction=False,
                                                 )
            elif "radiator_forward" in data['type']:
                # l_rules = "ventil" + "-pipe-" "radiator"
                l_rules = "thermostatic_valve"
                str_chain = l_rules.split("-")
                G = self.add_components_on_graph(G=G, node=node, str_chain=str_chain)
            # Other sources
            elif "radiator_backward" in data['type']:
                G.nodes[node]["type"].append("vented")
                l_rules = "shut_off_valve"
                # l_rules = "distributor" + "-pump-" + "pipe"
            # source_nodes = self.add_new_component_nodes(G=G, node=node, str_chain=str_chai)
            elif G.degree[node] == 1:
                pass
            elif G.degree[node] == 2:
                neighbor_list = list(G.neighbors(node))
                in_edge = neighbor_list[0]
                out_edge = neighbor_list[1]
                if self.is_linear_path(G=G,
                                       node1=in_edge,
                                       node2=node,
                                       node3=out_edge) is False:
                    G.nodes[node]["type"].append("deflection")
            elif G.degree[node] == 3:
                # l_rules = "three_way_valve"
                G.nodes[node]["type"].append("three_way_valve")
                # str_source_chain = l_rules.split("-")
                # source_nodes = self.add_components_on_graph(G=G, node=node, str_source_chain)
                # source_dict[node] = source_nodes

            elif G.degree[node] == 4:
                G.nodes[node]["type"].append("three_way_valve")

        # todo: Entlüfter, Verteiler, Ventilarten, Colletor für Backward Kreislauf

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

    def project_nodes_on_building(self, G: nx.Graph(), node_list: list, color: str):
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
                # node_id = int(node)
                # highest_id = max(highest_id, node_id)
                if node.startswith(prefix):
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
                     type_node: str or list,
                     element: str or list,
                     belongs_to: str or list,
                     floor_belongs_to: str,
                     direction: str,
                     tol_value: float = 0.0,
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
                   element=ele,
                   belongs_to=belongs,
                   direction=direction,
                   floor_belongs_to=floor_belongs_to)
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
                            color: str,
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
            id_name = f"{element_ID}_{type_node}_{element_belongs_to}_{i}"
            G, nodes = self.create_nodes(G=G,
                                         points=points,
                                         color=color,
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
                                                            node_list=element_nodes,
                                                            color=color)
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
                              pos: tuple,
                              type_node: list):

        G, intersect_node = self.create_nodes(G=G,
                                              points=pos,
                                              color=color,
                                              type_node=type_node,
                                              element=G.nodes[node]["element"],
                                              belongs_to=G.nodes[node]["belongs_to"],
                                              direction=G.nodes[node]["direction"],
                                              update_node=True,
                                              floor_belongs_to=G.nodes[node][
                                                  "floor_belongs_to"])
        return G, intersect_node

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
                                                        color="black",
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

                for element in room_elements:
                    element_data = room_elements[element]
                    element_global_corner = element_data["global_corners"]
                    type_node = element_data["type"]
                    # Erstellt Knoten für Wände
                    if room_elements[element]["type"] == "wall":
                        print(f"Create wall structure {element} for floor {floor_id}")
                        if room_elements[element]["global_corners"] is not None:
                            """G, wall_nodes = self.create_space_grid(G=G,
                                                                   room_data=room_elements[element],
                                                                   room_ID=element,
                                                                   color="black",
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
                                                                 color="red",
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
                            """G, center_wall = self.center_element(G=G,
                                                                 global_corners=room_elements[element]["global_corners"],
                                                                 color="blue",
                                                                 offset=0.25,
                                                                 belongs_to=room_elements[element]["belongs_to"],
                                                                 room_ID=element,
                                                                 edge_type="center_wall_backward",
                                                                 grid_type="center_wall_backward",
                                                                 node_type=["center_wall_backward"],
                                                                 floor_belongs_to=floor_id,
                                                                 tol_value=0.0,
                                                                 update_node=True,
                                                                 direction_x=True,
                                                                 direction_y=True,
                                                                 direction_z=False
                                                                 )"""
                # Jeder Space hat Elemente wie Fenster, Türen, Wände

                for element in room_elements:
                    print(f"Create element structure {element} for floor {floor_id}")
                    if room_elements[element]["type"] == "window":
                        if room_elements[element]["global_corners"] is not None:
                            # Projiziert Knoten auf nächstes Polygon
                            G, projected_nodes = self.create_element_grid(G=G,
                                                                          edge_type="window",
                                                                          element_data=room_elements[element],
                                                                          element_ID=element,
                                                                          tol_value=tol_value,
                                                                          color="orange",
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
                                                                          color="orange",
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

            """combined_y_list, combined_x_list, combined_z_list = [], [], []
            for node in G.nodes():
                G, z_list_1, x_list_1, y_list_1 = self.remove_edges_from_node(G=G,
                                                                              node=node)
                combined_y_list.extend(y_list_1)
                combined_x_list.extend(x_list_1)
                combined_z_list.extend(z_list_1)
            print(combined_y_list)"""
            # Kopiere die Knoten von G in forward
            print(f"Solve Overlapping edges for floor {floor_id}")
            G = self.edge_overlap(G=G,
                                  delete_degree=3,
                                  color="red",
                                  type_node=["center_wall_forward"],
                                  edge_type="center_wall_forward",
                                  grid_type="forward")
            """G = self.edge_overlap(G=G,
                                  delete_degree=3,
                                  color="blue",
                                  type_node=["center_wall_backward"],
                                  edge_type="center_wall_backward",
                                  grid_type="backward")"""

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
                                  color="red",
                                  col_tol=0.1,
                                  node_type=["center_wall_forward", "snapped_nodes"],
                                  no_neighbour_collision_flag=True,
                                  neighbor_nodes_collision_type=["space"])
            """nodes = ["center_wall_backward", "snapped_nodes"]
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
                                                    connect_type_edges=["center_wall_backward"],
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
                                                    type_node=["center_wall_backward"],
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
                                                    edge_snapped_node_type="center_wall_backward",
                                                    remove_type_node=["center_wall_backward"],
                                                    grid_type="backward",
                                                    new_edge_type="center_wall_backward",
                                                    create_snapped_edge_flag=True)
            print(f"Connect elements with center_wall_forward for floor {floor_id}")

            G = self.create_edges(G=G,
                                  node_list=snapped_nodes,
                                  edge_type="center_wall_backward",
                                  grid_type="forward",
                                  tol_value=tol_value,
                                  direction_x=True,
                                  direction_y=True,
                                  direction_z=True,
                                  connect_types=True,
                                  color="red",
                                  col_tol=0.1,
                                  node_type=["center_wall_backward", "snapped_nodes"],
                                  no_neighbour_collision_flag=True,
                                  neighbor_nodes_collision_type=["space"])"""

            """nodes = ["center_wall_forward", "center_wall_backward", "snapped_nodes", "door", "window"]
            subgraph_nodes = [n for n, attr in G.nodes(data=True) if any(t in attr.get("type", []) for t in nodes)]
            forward_H = forward.subgraph(subgraph_nodes)
            forward_H = forward_H.copy()
            attribute_type_to_remove = 'space'
            edges_to_remove = []
            for u, v, attr in forward_H.edges(data=True):
                if attr.get('type') == attribute_type_to_remove:
                    edges_to_remove.append((u, v))
            forward_H.remove_edges_from(edges_to_remove)"""
            self.save_networkx_json(G=G,
                                    file=Path(self.working_path, self.ifc_model, f"{floor_id}_floor_space.json"),
                                    type_grid="floor_with_space")
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
            # G = self.check_graph(G=G, type=f"Floor_{i}_backward")
            floor_graph_list.append(H)
            # floor_graph_backward_list.append(backward_H)
            # plt.show()
        # Ganzes Gebäude
        # forward = self.add_graphs(graph_list=floor_graph_list)
        # backward = self.add_graphs(graph_list=floor_graph_backward_list)
        G = self.add_graphs(graph_list=floor_graph_list)

        nodes = ["center_wall_forward"]
        center_wall_nodes = [n for n, attr in G.nodes(data=True) if any(t in attr.get("type", []) for t in nodes)]
        G = self.create_edges(G=G,
                              node_list=center_wall_nodes,
                              edge_type="center_wall_forward",
                              grid_type="forward",
                              tol_value=tol_value,
                              direction_x=False,
                              direction_y=False,
                              direction_z=True,
                              connect_types=True,
                              color="red",
                              col_tol=0.1,
                              node_type=["center_wall_forward"])

        """nodes = ["center_wall_backward"]
        center_wall_nodes = [n for n, attr in G.nodes(data=True) if any(t in attr.get("type", []) for t in nodes)]
        G = self.create_edges(G=G,
                              node_list=center_wall_nodes,
                              edge_type="center_wall_backward",
                              grid_type="backward",
                              tol_value=tol_value,
                              direction_x=False,
                              direction_y=False,
                              direction_z=True,
                              connect_types=True,
                              color="blue",
                              col_tol=0.1,
                              node_type=["center_wall_backward"])"""

        G = self.check_graph(G=G, type=f"Building")
        self.save_networkx_json(G=G,
                                type_grid="Building",
                                file=network_building_json)
        return G

    def is_collision(self, point1, point2, existing_edges):
        for edge in existing_edges:
            if (point1 == edge[0] and point2 == edge[1]) or (point1 == edge[1] and point2 == edge[0]):
                return True
        return False

    def create_snapped_nodes(self,
                             G: nx.Graph(),
                             node: nx.Graph().nodes(),
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
        arrow = length / 50
        ax.quiver(x, y, z, dx, dy, dz, color=color, arrow_length_ratio=arrow)
        #ax.quiver(x, y, z, dx, dy, dz, color=color, normalize=True)

    @staticmethod
    def visulize_networkx(G,
                          type_grid):
        """
        [[[0.2 4.2 0.2]
            [0.2 0.2 0.2]]
        Args:
            G ():

        """
        node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values(), key=lambda x: (x[0], x[1], x[2])))
        # node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values()))
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        ax.scatter(*node_xyz.T, s=50, ec="w")
        if G.is_directed():
            for u, v in G.edges():
                edge = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos'])])
                direction = edge[0][1] - edge[0][0]
                # ax.quiver(*edge[0][0], *direction, color=G.edges[u, v]['color'])
                length = G.edges[u, v]['length']
                arrow = length / 50
                GeometryBuildingsNetworkx.arrow3D(ax, *edge[0][0], *direction, arrowstyle="-|>", color=G.edges[u, v]['color'],
                             length=G.edges[u, v]['length'])
        else:
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
        plt.title(f'Graphennetzwerk vom Typ {type_grid}')
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
                       color: str,
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
                                               points=point,
                                               color=color,
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
                              color=color,
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

    def get_information_grid(self):
        pass

    def greedy_algorithmus(self, G, start, end):
        G_directed = nx.DiGraph()
        for node, data in G.nodes(data=True):
            G_directed.add_node(node, **data)
        starts = sorted([n for n, data in G_directed.nodes(data=True) if data["type"] in {"heat_source"}])
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
            # combined_graph = nx.disjoint_union(combined_graph, subgraph)
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
            D.add_edge(edges[0], edges[1], grid_type=grid_type, length=length, color="indigo")
        D.graph["grid_type"] = grid_type
        return D

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
        node_offset = {node: tuple(coord + offset for coord in pos) for node, pos in node_positions.items()}
        nx.set_node_attributes(G_reversed, node_offset, "pos")
        node_positions = nx.get_node_attributes(G_reversed, "pos")
        for node in G_reversed.nodes():
            G_reversed.nodes[node]['circulation_direction'] = grid_type
            G_reversed = nx.relabel_nodes(G_reversed, {node: node.replace("forward", "backward")})
        # Farbe der Kanten ändern
        edge_attributes = {(u, v): {"color": color} for u, v in G_reversed.edges()}
        nx.set_edge_attributes(G_reversed, edge_attributes)
        return G_reversed


class IfcBuildingsGeometry():

    def __init__(self, ifc_file, ifc_building_json, ifc_delivery_json):
        self.model = ifcopenshell.open(ifc_file)
        self.ifc_building_json = ifc_building_json
        self.ifc_delivery_json = ifc_delivery_json

    def __call__(self):
        room = self.room_element_position()
        floor = self.sort_room_floor(spaces_dict=room)
        floor_elements, room_dict, element_dict = self.sort_space_data(floor)
        # self.visualize_spaces()
        self.write_buildings_json(data=floor, file=self.ifc_building_json)
        self.write_buildings_json(data=element_dict, file=self.ifc_delivery_json)

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
            _dict_floor["heat_source"] = (ref_point[0], ref_point[1], floor_elements[floor]["height"])
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
            x_coords = [point[0] for point in global_corners]
            y_coords = [point[1] for point in global_corners]
            x_diff = np.max(x_coords) - np.min(x_coords)
            y_diff = np.max(y_coords) - np.min(y_coords)
            if x_diff > y_diff:
                direction = "x"
            else:
                direction = "y"
            spaces_dict[space.GlobalId] = {"type": "space",
                                           "number": space.Name,
                                           "Name": space.LongName,
                                           "id": space.id(),
                                           "height": z_min,
                                           "direction": direction,
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
                T.add_edge(*edge, length=graph.get_edge_data(*edge)['length'])
        # Ausgabe des Ergebnisses
        mst = nx.minimum_spanning_tree(T)
        lengths = [edge[2]['length'] for edge in mst.edges(data=True)]
        total_length = sum(lengths)
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
            path = nx.dijkstra_path(graph, start, end, length='length')
            distance = nx.dijkstra_path_length(graph, start, end, length='length')
            _short_path_edges.append(list(zip(path, path[1:])))
            _other_path_edges.append([edge for edge in graph.edges() if edge not in list(zip(path, path[1:]))])
            print("Kürzester Pfad:", path)
            print("Distanz:", distance)
        return graph, _short_path_edges, _other_path_edges, start, end_points

    def calc_pipe_coordinates(self, floors, ref_point):
        # todo: referenzpunkt einer eckpunkte des spaces zu ordnen: for d in distance(x_ref, poin
        # todo: Konten reduzieren
        # todo: path_lengths = nx.multi_source_dijkstra_path_length(G, [start_node], target=end_nodes, length='length')
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

    def __init__(self,
                 calc_building_json: Path,
                 calc_heating_json: Path,
                 c_p: float = 4.186,
                 g: float = 9.81,
                 rho: float = 1000,
                 f: float = 0.02,
                 v_mittel: float = 0.5,
                 v_max: float = 0.5,
                 p_max: float = 10,
                 kin_visco: float = 1.0 * 10 ** -6,
                 delta_T: int = 20):
        # Files
        self.calc_building_json = calc_building_json
        self.calc_heating_json = calc_heating_json
        ## Rohr Material
        # kupfer
        self.rho_cu = 8920 * (ureg.kilogram / ureg.meter ** 3)
        # Stahl
        self.rho_steel = 7850 * (ureg.kilogram / ureg.meter ** 3)
        # Kunststoff
        # Radiator Art/ Material
        self.g = g * (ureg.meter / ureg.second ** 2)
        self.rho = rho * (ureg.kilogram / ureg.meter ** 3)
        self.f = f
        self.v_max = v_max * (ureg.meter / ureg.second)  # maximale Fließgeschwindigkeit (in m/s)
        self.p_max = p_max * (ureg.meter / ureg.second)  # maximale Druckbelastung des Rohrs (i#
        self.c_p = c_p * (ureg.joule / (ureg.gram * ureg.kelvin))
        self.delta_T = delta_T * ureg.kelvin

        self.v_mittel = v_mittel * (ureg.meter / ureg.second)
        self.kin_visco = kin_visco * (ureg.kilogram / (ureg.meter * ureg.second))

    def __call__(self, G):
        # Tiefensuche von jedem Source-Knoten aus durchführen
        """for source_node in source_nodes:
            result_nodes.extend(nx.dfs_postorder_nodes(graph, source=source_node))"""
        ## Erste Grobe Auslegung

        G = self.initilize_attribute_nodes(graph=G)
        start_node = "source_2eyxpyOx95m90jmsXLOuR0"
        # 1. Berechne Fläche der Radiatoren (Endpunkte)
        G = self.update_radiator_area_nodes(G=G, nodes=["radiator_forward"])
        # 2. Berechne Massenstrom an den Endpunkten
        G = self.update_radiator_mass_flow_nodes(G=G, nodes=["radiator_forward"])
        G = self.update_radiator_volume_flow_nodes(G=G, nodes=["radiator_forward"])
        # 3. Iteriere von den Endknoten
        # zum Anfangspunkt, summiere die Massenstrom an Knoten, Berechne Durchmesser der Knoten
        G = self.iterate_nodes_mass_volume_flow(G=G)
        G = self.update_pipe_inner_diameter_edges(G=G)
        G = self.iterate_pressure_loss_edges(G=G, v_mid=self.v_max)
        G = self.iterate_pressure_loss_nodes(G=G)
        min_pressure, bottleneck_node = self.calculate_network_bottleneck(G=G,
                                                                          nodes=["radiator_forward"])
        # pump_power = self.calculate_pump_power(m_flow=m_flow, efficiency=0.9, pressure_difference=pressure_difference)

        # print(min_pressure)
        # print(G.nodes[bottleneck_node]["pos"])

        V_max_flow = self.get_maximal_volume_flow(G=G)
        flow_rates = np.linspace(0, V_max_flow, 10)

        self.calculate_pump_system_curve(G=G,
                                         start_nodes=start_node,
                                         end_node=bottleneck_node,
                                         flow_rates=flow_rates)
        self.save_networkx_json(G=G, file=self.calc_heating_json, type_grid="Calculate Heating Graph")

        nodes = ["radiator_forward"]
        radiator_nodes = [n for n, attr in G.nodes(data=True) if
                          any(t in attr.get("type", []) for t in nodes)]
        """for node in radiator_nodes:
            print(G.nodes[node]['m_flow'])"""
        """for node, data in G.nodes(data=True):
            print(node)
            print(data["pressure_in"])
            print(data["pressure_out"])"""
        """strands = self.get_strands(G=G)
        pressure_dict = self.calculate_network_bottleneck_strands(G=G, strands=strands, start_nodes=["pump"])
        
        
        print(min_pressure)
        start_nodes=["pump"]
        start_node = [n for n, attr in G.nodes(data=True) if
                      any(t in attr.get("type", []) for t in start_nodes)]
        for start in start_node:
            m_flow = G.nodes[start]["m_flow"]
            min_pressure = pressure_dict[start]
            pump_pressure = G.nodes[start]["pressure"]
            pressure_difference = abs(min_pressure-pump_pressure)
            print(m_flow)
            pump_power = self.calculate_pump_power(m_flow=m_flow, efficiency=0.9, pressure_difference=pressure_difference)
            print(start, pump_power)

        #self.write_component_list(G)
        self.create_bom_edges(G=G, filename="Materialmenge.xlsx")
        self.create_bom_nodes(G=G, filename="Materialmenge.xlsx")"""

        # G = self.hardy_cross_algorithm(graph=G)
        # print(nx.adjacency_matrix(G))
        # print(nx.incidence_matrix(G, oriented=True))
        # 4. Pumpleistung bestimmen
        # 4. Bestimmte Materialmenge: Wähle passendes Rohr aus Liste
        # 5. Bestimmen der Systemkennlinie
        # Volumenstrombereich
        # self.plot_3D_pressure(G=G)
        # self.plot_pressure(G=G)
        # self.plot_nodes(G=G)
        # netx.visulize_networkx(G=G)
        # plt.show()
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

    def read_radiator_material_excel(self,
                                     filename,
                                     sheet_name,
                                     calc_flow_volume
                                     ):
        pass

    def read_pipe_material_excel(self,
                                 filename,
                                 sheet_name,
                                 calc_inner_diameter: float = 11.5, ):
        calc_inner_diameter = calc_inner_diameter * ureg.millimeter
        data = pd.read_excel(filename, sheet_name=sheet_name)
        inner_diameter_list = []
        inner_diameter_list = {}
        for index, row in data.iterrows():
            data_wall = row['Abmessung Aussendurchmesser X Wanddicke (mm)'].split("x")
            outer_diameter = float(data_wall[0].strip().replace(',', '.')) * ureg.millimeter
            wall_thickness = float(data_wall[1].strip().replace(',', '.')) * ureg.millimeter
            inner_diameter = outer_diameter - 2 * wall_thickness
            if calc_inner_diameter <= inner_diameter:
                inner_diameter_list[inner_diameter] = outer_diameter
        inner_diameter = min(inner_diameter_list,
                             key=lambda x: abs(inner_diameter_list[x] - calc_inner_diameter))
        outer_diameter = inner_diameter_list[inner_diameter]
        return inner_diameter, outer_diameter

    def get_maximal_volume_flow(self, G):
        max_volumenstrom = 0

        # Iteration über alle Knoten
        for node in G.nodes:
            # Überprüfen, ob der Knoten einen Volumenstrom-Wert hat
            if 'V_flow' in G.nodes[node]:
                volumenstrom = G.nodes[node]['V_flow']
                # Aktualisieren des maximalen Volumenstroms, wenn ein größerer Wert gefunden wird
                if volumenstrom > max_volumenstrom:
                    max_volumenstrom = volumenstrom
        max_volumenstrom = 1.2 * max_volumenstrom  # * max_volumenstrom.units
        # max_volumenstrom += 0.2 * max_volumenstrom * max_volumenstrom.units
        # Ausgabe des maximalen Volumenstroms
        return max_volumenstrom

    def calculate_pump_system_curve(self,
                                    G,
                                    start_nodes,
                                    end_node,
                                    flow_rates):
        """

        Args:
            G ():
            flow_rates ():
        """
        # Berechnung der Pumpleistung für verschiedene Volumenströme
        flow_rates = flow_rates.to(ureg.meter ** 3 / ureg.hour)
        pump_power = []

        for flow in flow_rates:
            # flow = flow.to(ureg.meter ** 3 / ureg.hour)
            pump_power.append(self.pump_curve(flow))
        # Berechnung des Druckverlusts im Rohrsystem für verschiedene Volumenströme
        system_loss = []
        for flow in flow_rates:
            head = self.system_curve(G=G,
                                     start_node=start_nodes,
                                     end_node=end_node,
                                     flow_rate=flow)
            system_loss.append(head)
        # Bestimmung des Betriebspunkts (Schnittpunkt)
        pump_power_values = [value.magnitude for value in pump_power]
        system_loss_values = [value.magnitude for value in system_loss]
        index = np.argmin(np.abs(np.array(pump_power_values) - np.array(system_loss_values)))
        operating_flow_rate = flow_rates[index]

        operating_head = self.pump_curve(operating_flow_rate)
        self.plot_pump_system_curve(flow_rates=flow_rates,
                                    pump_power=pump_power_values,
                                    system_loss=system_loss_values,
                                    operating_flow_rate=operating_flow_rate,
                                    operating_head=operating_head)

    def plot_pump_system_curve(self,
                               flow_rates,
                               pump_power,
                               system_loss,
                               operating_flow_rate,
                               operating_head):
        """

        Args:
            flow_rate ():
            pump_power ():
            system_loss ():
        """
        # Plot der Leistungskurve und Systemkurve

        plt.plot(flow_rates, pump_power, label='Pump Curve')
        plt.plot(flow_rates, system_loss, label='System Curve')
        plt.plot(operating_flow_rate, operating_head, 'ro', label='Operating Point')
        plt.xlabel(f'Flow Rate [{flow_rates.units}]')
        plt.ylabel(f'Head / Power ')
        plt.legend()
        plt.show()
        print('Operating Flow Rate:', operating_flow_rate)
        print('Operating Head:', operating_head)

    def pump_curve(self, flow_rate):
        # Beispielhafte Leistungskurve (fiktive Werte)
        head = 100000 * (ureg.meter ** 3 / ureg.second) - 50000000 * flow_rate
        return head

    # Systemkurve basierend auf den berechneten Druckverlusten im Rohrsystem
    def system_curve(self,
                     G,
                     start_node,
                     end_node,
                     flow_rate):
        """

        Args:
            G ():
            start_node ():
            end_node ():
            flow_rate ():

        Returns:

        """
        # Beispielhafte Systemkurve (fiktive Werte)
        if flow_rate == 0:
            return 0 * ureg.pascal
        else:
            path = nx.dijkstra_path(G, start_node, end_node)
            for i in range(len(path) - 1):
                node1 = path[i]
                node2 = path[i + 1]
                # todo: Druckverlust Höhe fehlt + Rücklauf fehlt
                # 1. pressure_out node1
                # 2. rohrreibung berechnen dp_r
                inner_diameter = G[node1][node2]["inner_diameter"]
                length = G[node1][node2]["length"]
                v_mid = flow_rate / ((math.pi * inner_diameter ** 2) / 4)
                delta_p_friction = self.calculate_friction_pressure_loss(inner_diameter=inner_diameter,
                                                                         v_mid=v_mid,
                                                                         length=length)
                # 3. pressure_in(node2) = pressure_out(node1) - dr_r
                G.nodes[node2]['pressure_in'] = G.nodes[node1]["pressure_out"] - delta_p_friction
                # 4. Berechne dp_e

                pressure_loss_node = self.calculate_pressure_loss_fittings(
                    coefficient_resistance=G.nodes[node2]['coefficient_resistance'],
                    mid_velocity=v_mid)
                # 5. pressure_out(node2) = pressure_in(node2) - dp_e
                G.nodes[node2]['pressure_out'] = G.nodes[node2]['pressure_in'] - pressure_loss_node
            # 6. pressure_start - pressure end
            head_loss = G.nodes[start_node]['pressure_out'] - G.nodes[end_node]['pressure_out']
            return head_loss

    def pump(self, G):
        pump_nodes = [node for node, data in G.nodes(data=True) if 'pump' in set(data.get('type'))]
        strands = []
        for pump_node in pump_nodes:
            successors = nx.dfs_successors(G, pump_node)
            strand = []
            for end_node in successors.keys():
                if G.out_degree(end_node) == 0:  # Prüfen, ob der Knoten ein Endknoten ist
                    strand.append(nx.shortest_path(G, pump_node, end_node))
            strands.append(strand)
        network_weakest_points = []
        for strand in strands:
            weakest_node = min(strand, key=lambda node: G.nodes[node]['pressure'])
            network_weakest_points.append(weakest_node)

        return G

    def pressure_loss(self, length, inner_diameter, flow_rate):
        # Füge hier deine Berechnungslogik für den Druckverlust ein
        return 0.1 * length * inner_diameter * flow_rate

    def get_strands(self, G):
        # Initialisiere eine leere Liste für die Stränge
        # source_nodes = [node for node, data in G.nodes(data=True) if 'source' in set(data.get('type'))]
        source_nodes = [node for node, data in G.nodes(data=True) if 'pump' in set(data.get('type'))]
        end_nodes = [node for node, data in G.nodes(data=True) if 'radiator_forward' in set(data.get('type'))]
        strands = []
        for source in source_nodes:
            # Suche alle Endknoten im Graphen
            # end_nodes = [node for node in G.nodes() if G.out_degree(node) == 0]

            # Führe eine Tiefensuche von jedem Endknoten aus, um die Stränge zu identifizieren
            for end_node in end_nodes:
                paths = nx.all_simple_paths(G, source=source, target=end_node)  # Annahme: Anfangsknoten ist 1
                for path in paths:
                    strands.append(path)

        return strands

    def iterate_pressure_node(self, G):
        pass

    def iterate_pressure_loss_nodes(self,
                                    G,
                                    initial_pressure=(1.5 * 10 ** 5)):
        # Berechnung des Drucks entlang des Pfades
        initial_pressure = initial_pressure * ureg.pascal
        nx.set_node_attributes(G, initial_pressure, 'pressure_in')
        while True:
            updated = False
            for node in nx.topological_sort(G):
                # Berechnung des Drucks anhand der eingehenden Kanten
                incoming_pressures = []
                for predecessor in G.predecessors(node):
                    # pressure = G.nodes[predecessor]['pressure_in']
                    pressure = G.nodes[predecessor]['pressure_out']
                    pressure_loss = G[predecessor][node]['pressure_loss']
                    incoming_pressures.append(pressure - pressure_loss)
                # Berücksichtigung des Druckabfalls an bestimmten Knoten
                if 'pressure_loss' in G.nodes[node]:
                    pressure_drop = G.nodes[node]['pressure_loss']
                    new_pressure = min(incoming_pressures) - pressure_drop if incoming_pressures else initial_pressure
                else:
                    new_pressure = min(incoming_pressures) if incoming_pressures else initial_pressure
                if new_pressure != G.nodes[node]['pressure_in']:
                    G.nodes[node]['pressure_in'] = new_pressure
                    updated = True
                # Berücksichtigung des Druckabfalls des Knotens selbst für pressure_out
                pressure_out = new_pressure - G.nodes[node].get('pressure_loss', 0)
                if pressure_out != G.nodes[node].get('pressure_out'):
                    G.nodes[node]['pressure_out'] = pressure_out
                    updated = True
            if not updated:
                break
        return G

    # Funktion zur Berechnung des maximalen Druckunterschieds
    def calculate_max_pressure_difference(self, G, start_node, end_nodes):
        # Initialisiere die Druckwerte für alle Knoten
        nx.set_node_attributes(G, float('inf'), 'pressure')
        G.nodes[start_node]['pressure'] = 100  # Startdruck des Anfangsknotens

        # Berechne den Druck an jedem Knoten im Netzwerk
        for _ in range(len(G.nodes)):
            for node in G.nodes:
                for predecessor in G.predecessors(node):
                    length = G[predecessor][node]['length']
                    inner_diameter = G[predecessor][node]['inner_diameter']
                    flow_rate = G.nodes[predecessor]['m_flow']
                    pressure_loss_value = self.pressure_loss(length, inner_diameter, flow_rate)

                    G.nodes[node]['pressure'] = min(G.nodes[node]['pressure'],
                                                    G.nodes[predecessor]['pressure'] - pressure_loss_value)

        # Berechne den maximalen Druckunterschied zwischen dem Anfangsknoten und den Endknoten
        max_pressure_difference = 0
        for end_node in end_nodes:
            pressure_difference = G.nodes[end_node]['pressure'] - G.nodes[start_node]['pressure']
            max_pressure_difference = max(max_pressure_difference, pressure_difference)

        return max_pressure_difference

    def hardy_cross_algorithm(self, graph, iterations=100, convergence_threshold=0.001):
        num_nodes = len(graph.nodes)
        pressures = np.zeros(num_nodes)  # Array zur Speicherung der Drücke an jedem Knoten

        for _ in range(iterations):
            prev_pressures = np.copy(pressures)
            for node in graph.nodes():
                """for pred in graph.predecessors(node):
                    print(graph.nodes[pred]['m_flow'])"""
                # inflows = [graph.nodes[pred][node]['m_flow'] for pred in graph.predecessors(node)]
                inflows = [graph.nodes[pred]['m_flow'] for pred in graph.predecessors(node)]
                outflows = [graph.nodes[succ]['m_flow'] for succ in graph.successors(node)]
                inflow_sum = sum(inflows)
                outflow_sum = sum(outflows)
                pressures = inflow_sum - outflow_sum
                # pressures[node] = inflow_sum - outflow_sum

            max_delta = np.abs(pressures - prev_pressures).max()
            if max_delta < convergence_threshold:
                break

        return pressures

    def calculate_pump_power(self, m_flow, efficiency, pressure_difference):
        """

        Args:
            m_flow ():
            efficiency ():
            pressure_difference ():

        Returns:

        """
        return round((m_flow * pressure_difference) / (efficiency * self.rho), 2)

    def update_pipe_inner_diameter_edges(self, G):
        for edge in G.edges():
            m_flow_1 = G.nodes[edge[0]]["m_flow"]
            m_flow_2 = G.nodes[edge[1]]["m_flow"]
            #print(m_flow_1)
            G.edges[edge[0], edge[1]]['inner_diameter'] = self.calculate_pipe_inner_diameter(m_flow=m_flow_1)
        return G

    def iterate_nodes_mass_volume_flow(self, G):
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

                volumen_flow_sum = sum(G.nodes[succ]['V_flow'] for succ in successors)
                # Speichere den summierten Massenstrom im aktuellen Knoten
                G.nodes[node]['m_flow'] = massenstrom_sum
                G.nodes[node]['V_flow'] = volumen_flow_sum
                # Berechne den Durchmesser basierend auf dem größeren Massenfluss der Nachfolgerknoten
                m_flow_successors = [G.nodes[succ]['m_flow'] for succ in successors]
                max_m_flow = max(m_flow_successors)
            elif len(successors) == 1:
                # Kopiere den Massenstrom des einzigen Nachfolgerknotens
                G.nodes[node]['m_flow'] = G.nodes[successors[0]]['m_flow']
                G.nodes[node]['V_flow'] = G.nodes[successors[0]]['V_flow']
        # Zeige den berechneten Massenstrom für jeden Knoten an
        return G

    def iterate_edges(self, G):
        for node_1, node_2 in G.edges():
            m_flow_1 = 0.1

    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D

    def plot_3D_pressure(self, G):
        # Positionen der Knoten im Diagramm
        t = nx.get_node_attributes(G, "pos")
        new_dict = {key: (x, y, z) for key, (x, y, z) in t.items()}
        node_size = 10
        # Zeichnen des Rohrnetzwerks
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        # Zeichnen der Knoten mit entsprechender Farbe und Druck als Label
        # node_pressure_in = {node: round((G.nodes[node]['pressure_in'] * 10 ** -5), 1) for node in G.nodes()}
        node_pressure_out = {node: round((G.nodes[node]['pressure_in'] * 10 ** -5), 1) for node in G.nodes()}
        node_colors = []
        for node in G.nodes():
            node_colors.append(node_pressure_out[node].magnitude)

        cmap = plt.cm.get_cmap('cool')  # Farbkarte für Druckverlauf
        # node_colors = [node_pressure_in[node] for node in G.nodes()]
        ax.scatter([x for x, y, z in new_dict.values()], [y for x, y, z in new_dict.values()],
                   [z for x, y, z in new_dict.values()], c=node_colors, cmap='cool', s=node_size, label='Pressure')

        # Zeichnen der Kanten mit Farben entsprechend dem Druck
        edge_colors = [G[u][v]['pressure_loss'] for u, v in G.edges()]
        edge_colors_normalized = [(c - min(edge_colors)) / (max(edge_colors) - min(edge_colors)) for c in edge_colors]
        edge_colors_mapped = plt.cm.get_cmap('cool')(edge_colors_normalized)
        edge_colors_mapped = cmap(edge_colors_normalized)

        for u, v in G.edges():
            ax.plot([new_dict[u][0], new_dict[v][0]], [new_dict[u][1], new_dict[v][1]],
                    [new_dict[u][2], new_dict[v][2]], alpha=0.6, color="grey")

        # Anpassen der Farblegende basierend auf dem Druckverlauf
        sm = plt.cm.ScalarMappable(cmap=cmap)
        # sm.set_array(list(node_pressure_out.values()))
        sm.set_array(node_colors)
        plt.colorbar(sm, label='Druck [bar]')
        # sm = plt.cm.ScalarMappable(cmap='cool')
        # sm.set_array(node_colors)
        # plt.colorbar(sm, label='Druck')

        # Anzeigen des Diagramms
        plt.title('Positionsbasierter Druckverlauf in einem Rohrnetzwerk')
        plt.show()

    def plot_pressure(self, G):
        """

        Args:
            G ():
        """
        # Positionen der Knoten im Diagramm
        # Zeichnen des Rohrnetzwerks
        t = nx.get_node_attributes(G, "pos")
        new_dict = {key: (x, y) for key, (x, y, z) in t.items()}
        node_size = 100
        nx.draw_networkx(G, pos=new_dict, with_labels=False, node_size=node_size)
        node_pressure = {}
        for node in G.nodes():
            node_pressure[node] = round((G.nodes[node]['pressure_out'] * 10 ** -5).magnitude, 1)

        # Zeichnen des Druckverlaufs als Positions  basiertes Diagramm
        # node_sizes = [100 * node_pressure[node] for node in G.nodes()]
        cmap = plt.cm.get_cmap('cool')  # Farbkarte für Druckverlauf
        nx.draw_networkx_nodes(G,
                               pos=new_dict,
                               node_size=node_size,
                               node_color=list(node_pressure.values()),
                               cmap=cmap)
        nx.draw_networkx_labels(G, pos=new_dict, labels={node: str(node_pressure[node]) for node in G.nodes})
        # Zeichnen der Kanten mit Farben entsprechend dem Druck
        # Zeichnen der Kanten mit Farben entsprechend dem Druck
        edge_colors = [G[u][v]['pressure_loss'] for u, v in G.edges()]
        edge_colors_normalized = [(c - min(edge_colors)) / (max(edge_colors) - min(edge_colors)) for c in edge_colors]
        edge_colors_mapped = cmap(edge_colors_normalized)
        # nx.draw_networkx_edges(G, pos=new_dict, edge_color=edge_colors_mapped)
        nx.draw_networkx_edges(G, pos=new_dict, edge_color="grey")

        # Anpassen der Farblegende basierend auf dem Druckverlauf
        sm = plt.cm.ScalarMappable(cmap=cmap)
        sm.set_array(list(node_pressure.values()))
        plt.colorbar(sm, label='Druck')

        # Anzeigen des Diagramms
        plt.title('Positionsbasierter Druckverlauf in einem Rohrnetzwerk')
        plt.axis('on')
        plt.show()

    def plot_nodes(self, G):
        # Knotendiagramm erstellen
        t = nx.get_node_attributes(G, "pos")
        new_dict = {key: (x, y) for key, (x, y, z) in t.items()}
        node_sizes = [G.nodes[node]['m_flow'].magnitude for node in
                      G.nodes()]  # Knotengrößen basierend auf m_flow festlegen
        node_color = [
            'red' if "radiator_forward" in set(G.nodes[node]['type']) else 'g' if 'heat_source' in G.nodes[node][
                'type'] else 'b'
            for node in G.nodes()]
        nx.draw(G,
                pos=new_dict,
                node_color=node_color,
                node_shape='o',
                node_size=node_sizes,
                font_size=12)
        edge_widths = [G.edges[edge]['inner_diameter'] for edge in G.edges()]
        min_diameter = min(edge_widths)
        max_diameter = max(edge_widths)
        scaled_edge_widths = [(diameter - min_diameter) / (max_diameter - min_diameter) * 3 + 1 for diameter in
                              edge_widths]
        nx.draw_networkx_edges(G, pos=new_dict, width=scaled_edge_widths)
        plt.axis('off')
        plt.title('Knoten und m_flow')
        # plt.show()"""

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
                    # durchmesser = calculate_durchmesser(massenstrom)  # Funktion zur Berechnung des Rohrdurchmessers
                    # Weise den berechneten Durchmesser der Kante als Attribut zu
                    # edge['durchmesser'] = durchmesser
                    # Berechne den Massenstrom für den Vorgängerknoten
                    predecessor_massenstrom = self.calculate_successor_massenstrom(
                        massenstrom)  # Funktion zur Berechnung des Massenstroms
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
                # durchmesser = calculate_durchmesser(massenstrom)  # Funktion zur Berechnung des Rohrdurchmessers
                # Weise den berechneten Durchmesser der Kante als Attribut zu
                # edge['durchmesser'] = durchmesser
                # Berechne den Massenstrom für den Nachfolgeknoten
                successor_massenstrom = self.calculate_successor_massenstrom(
                    massenstrom)  # Funktion zur Berechnung des Massenstroms
                if 'massenstrom' not in G.nodes[successor_node]:
                    # Wenn der Massenstrom noch nicht berechnet wurde, füge den Knoten zur Warteschlange hinzu
                    queue.append(successor_node)

                # Weise den berechneten Massenstrom dem Nachfolgeknoten als Attribut zu
                G.nodes[successor_node]['massenstrom'] = successor_massenstrom

    def calculate_successor_massenstrom(self, massenstrom):
        # Führe hier deine Berechnungen für den Massenstrom des Nachfolgeknotens basierend auf dem aktuellen Massenstrom und dem Durchmesser durch
        successor_massenstrom = massenstrom + massenstrom  # Berechnung des Massenstroms des Nachfolgeknotensmassenstrom
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
        """
        Args:
            G ():
            nodes ():
        Returns:
        """
        # todo: Abhängig vom Space belongs_to / Teilen des Wärmestroms
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
                coefficient_resistance = 4.0
                # Q_H = random.randint(10, 10000)
                # Q_H = 1000 *  ureg.joule
                Q_H = 1000 * ureg.watt
            else:
                Q_H = 0 * ureg.watt
            # todo: Knoten kann mehrere Komponenten enthalten, Entweder Knoten auflösen und trennen oder coefficient resitance durchiterieren
            if "heat_source" in graph.nodes[node]["type"]:
                coefficient_resistance = 4.0
            elif "distributor" in graph.nodes[node]["type"]:
                coefficient_resistance = 1.5
            elif "pump" in graph.nodes[node]["type"]:
                coefficient_resistance = 0.0
            elif "thermostatic_valve" in graph.nodes[node]["type"]:
                coefficient_resistance = 4.0
            elif "deflection" in graph.nodes[node]["type"]:
                coefficient_resistance = 1.0


            else:
                coefficient_resistance = 0.0
            graph.nodes[node]['heat_flow'] = Q_H
            graph.nodes[node]['V_flow'] = 0.0
            graph.nodes[node]['m_flow'] = self.calculate_m_dot(Q_H=Q_H)
            # graph.nodes[node]['V_flow'] = self.calculate_m_dot(Q_H=Q_H)
            # graph.nodes[node]['diameter'] = 0.0 * ureg.meter # Beispiel-Durchmesser (initial auf 0 setzen)
            graph.nodes[node]['area'] = 0.0 * ureg.meter ** 2
            # graph.nodes[node]['pressure_loss'] = 0.0
            graph.nodes[node]['pressure_loss'] = self.calculate_pressure_loss_fittings(
                coefficient_resistance=coefficient_resistance,
                mid_velocity=self.v_max)
            graph.nodes[node]['coefficient_resistance'] = coefficient_resistance
            graph.nodes[node]['pressure_in'] = 1.0 * 10 ** 5 * ureg.pascal
            graph.nodes[node]['pressure_out'] = 1.0 * 10 ** 5 * ureg.pascal

            # Beispielattribute 'diameter' zu den Kanten hinzufügen
        for edge in graph.edges():
            graph.edges[edge]['inner_diameter'] = 0.0 * ureg.meter  # Beispiel-Durchmesser (initial auf 0 setzen)
            graph.edges[edge]['outer_diameter'] = 1.0 * ureg.meter
            graph.edges[edge]['pressure_loss'] = 0.0 * 10 ** 5 * ureg.pascal
            length = graph.edges[edge]["length"] * ureg.meter
            graph.edges[edge]["length"] = length

        return graph

    def calculate_pressure_loss(self, G):
        # todo: Problem lösen
        for edge in G.edges():
            start_node, end_node = edge
            pressure_loss_pipe = G[edge[0]][edge[1]]['pressure_loss']
            # Berechne den Druckverlust basierend auf dem Druckwert an den verbundenen Knoten
            pressure_loss = G.nodes[start_node]['pressure_loss'] + pressure_loss_pipe
            # Aktualisiere den Druckwert am Endpunkt der Kante
            G.nodes[end_node] = G.nodes[start_node] - pressure_loss
            # Iteriere über jeden Knoten im Netzwerk und berechne den Druckverlust
        for node in G.nodes():
            if 'component_pressure_loss' in G.nodes[node]:
                component_pressure_loss = G.nodes[node]['component_pressure_loss']

                # Berechne den Druckverlust basierend auf dem Druckwert des Knotens
                pressure_loss = pressure_values[node] * component_pressure_loss

                # Aktualisiere den Druckwert des Knotens
                pressure_values[node] -= pressure_loss

    def create_bom_nodes(self, G, filename):
        bom_nodes = {}  # Stückliste für Knoten (Komponenten)

        for node, data in G.nodes(data=True):
            node_type = data.get('type')
            # Füge hier weitere Informationen von den Knotenattributen hinzu, die du speichern möchtest

            bom_nodes[node] = {
                'Typ': node_type,
                # Füge hier weitere Informationen hinzu
            }

        # Erstelle ein DataFrame aus dem Dictionary
        df = pd.DataFrame.from_dict(bom_nodes, orient='index')

        # Erstelle ein DataFrame aus dem Dictionary
        df = pd.DataFrame.from_dict(bom_nodes, orient='index')

        # Lade das bestehende Excel-File
        with pd.ExcelWriter(filename, engine='openpyxl', mode='a') as writer:
            writer.book = load_workbook(filename)

            # Schreibe das DataFrame in das gewünschte Sheet
            df.to_excel(writer, sheet_name='Knoten', index_label='Knoten')

            # Speichere die Änderungen im Excel-File
            writer.save()

    def create_bom_edges(self, G, filename):
        bom_edges = {}  # Stückliste für Kanten (Rohre)
        for u, v in G.edges():
            length = G.edges[u, v]['length']
            inner_diameter = G.edges[u, v]['inner_diameter']
            outer_diameter = G.edges[u, v]['outer_diameter']
            m_flow = G.nodes[u]['m_flow']
            # Berechne die Materialmenge basierend auf den Kantenattributen (Beispielberechnung)
            material_quantity = length * (outer_diameter - inner_diameter)
            pos = f'{G.nodes[u]["pos"]} - {G.nodes[v]["pos"]}'
            # bom_edges[(pos)] = material_quantity
            bom_edges[pos] = {
                # 'Rohr': pos,
                'Materialmenge [kg]': material_quantity,
                'inner_diameter [m]': inner_diameter,
                'outer_diameter [m]': outer_diameter,
                'm_flow [kg/h]': m_flow,
                'Länge [m]': length
            }
        # df = pd.DataFrame(list(bom_edges.items()), columns=['Kante', 'Materialmenge'])
        df = pd.DataFrame.from_dict(bom_edges, orient='index')
        # Schreibe das DataFrame in eine Excel-Tabelle
        df.to_excel(filename, sheet_name='Rohre', index_label='Rohre')
        # Schreibe die Stückliste in eine Datei
        """with open(filename, 'w') as file:
            file.write("Kante\tMaterialmenge\n")
            for edge, quantity in bom_edges.items():
                file.write(f'{G.nodes[edge[0]]["pos"]} - {G.nodes[edge[1]]["pos"]}\t{quantity}\n')"""

    def write_component_list(self, G):
        bom = {}  # Stückliste (Komponente: Materialmenge)

        for node in G.nodes():
            component_type = G.nodes[node].get('type')
            if component_type:
                if component_type in bom:
                    bom[component_type] += 1  # Erhöhe die Materialmenge für die Komponente um 1
                else:
                    bom[component_type] = 1  # Initialisiere die Materialmenge für die Komponente mit 1

        return bom

    def find_network_critical_point(self, G, initial_pressure):
        pressure_values = self.calculate_pressure_loss(G, initial_pressure)
        critical_point = min(pressure_values, key=pressure_values.get)
        return critical_point, pressure_values[critical_point]

    def calculate_pressure_pipe_lost(self, length, inner_diameter):
        """
        f * (rho * v**2) / (2 * D * g)
        Args:
            length ():

        Returns:
        """
        return self.f * (self.rho * self.v_max ** 2) * length / (2 * inner_diameter * self.g)

    def update_radiator_volume_flow_nodes(self, G, nodes: list):
        radiator_nodes = [n for n, attr in G.nodes(data=True) if
                          any(t in attr.get("type", []) for t in nodes)]
        for node in radiator_nodes:
            m_flow = G.nodes[node]['m_flow']
            V_flow = m_flow / self.rho
            G.nodes[node]['V_flow'] = V_flow.to(ureg.meter ** 3 / ureg.second)
        return G

    def calculate_pipe_inner_diameter(self, m_flow):
        """
        d_i = sqrt((4 * m_flow) / (pi * rho * v_max))
        Args:
            m_flow ():
        """
        # result = (4 * m_flow / (math.pi * self.rho * self.v_max)).to_base_units()  # in SI-Basiseinheiten umwandeln
        # innter_diameter = math.sqrt(result.magnitude) * result.units**0.5 # in SI-Basiseinheiten umwandeln
        inner_diameter = (4 * m_flow / (math.pi * self.rho * self.v_max)) ** 0.5
        return round(inner_diameter, 5)

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

    def calculate_inner_diameter(self, Q_H: float, delta_p: float, length: float):
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
        return round((Q_H / (self.c_p * self.delta_T)).to(ureg.kilogram / ureg.second), 2)

    def calculate_network_bottleneck_strands(self, G, strands, start_nodes: list):
        """end_node = [n for n, attr in G.nodes(data=True) if
                 any(t in attr.get("type", []) for t in end_nodes)]"""
        start_node = [n for n, attr in G.nodes(data=True) if
                      any(t in attr.get("type", []) for t in start_nodes)]

        pressure_dict = {}
        for start in start_node:
            min_pressure = float('inf')
            for strand in strands:
                if start in set(strand):
                    # Iteration über die Endpunkte
                    # for node in end_node:
                    for strang in strand:
                        pressure = G.nodes[strang]['pressure']
                        if pressure < min_pressure:
                            min_pressure = pressure
            pressure_dict[start] = min_pressure
        return pressure_dict

    def calculate_network_bottleneck(self, G, nodes: list):
        nodes = [n for n, attr in G.nodes(data=True) if
                 any(t in attr.get("type", []) for t in nodes)]

        bottleneck_node = None
        min_pressure = float('inf')
        # Iteration über die Endpunkte
        for node in nodes:
            pressure = G.nodes[node]['pressure_out'].magnitude
            if pressure < min_pressure:
                min_pressure = pressure
                bottleneck_node = node
        return min_pressure, bottleneck_node

    def calculate_reynold(self, inner_diameter: float, mid_velocity: float):
        """

        Args:
            inner_diameter ():
            mid_velocity ():
        """
        return (mid_velocity * inner_diameter * self.rho) / (self.kin_visco)

    def calculate_friction_pressure_loss(self, inner_diameter, v_mid, length):
        print(inner_diameter)
        pipe_friction_coefficient = 64 / self.calculate_reynold(inner_diameter=inner_diameter,
                                                                mid_velocity=v_mid)
        # print(pipe_friction_coefficient)
        delta_p_friction = self.darcy_weisbach_equation(pipe_friction_coefficient=pipe_friction_coefficient,
                                                        mid_velocity=v_mid,
                                                        length=length,
                                                        inner_diameter=inner_diameter)
        return delta_p_friction

    def iterate_pressure_loss_edges(self, G, v_mid):
        for edge in G.edges():
            edge_data = G.get_edge_data(edge[0], edge[1])
            length = edge_data['length'] * ureg.meter
            inner_diameter = edge_data['inner_diameter']
            delta_p_friction = self.calculate_friction_pressure_loss(inner_diameter=inner_diameter,
                                                                     v_mid=v_mid,
                                                                     length=length)
            h = abs(G.nodes[edge[0]]['pos'][2] - G.nodes[edge[1]]['pos'][2]) * ureg.meter
            delta_p_hydro = self.calculate_pressure_hydro(delta_h=h)
            G.edges[edge[0], edge[1]]['pressure_loss'] = delta_p_friction + delta_p_hydro
        return G

    # Druckverluste Rohr
    def darcy_weisbach_equation(self,
                                pipe_friction_coefficient: float,
                                mid_velocity: float,
                                length: float,
                                inner_diameter: float):
        """

        Args:
            pipe_friction_coefficient ():
        """
        return 0.5 * self.rho * (length / inner_diameter) * pipe_friction_coefficient * mid_velocity ** 2

    def calculate_pressure_hydro(self, delta_h):
        """

        Args:
            delta_h ():

        Returns:

        """
        return self.rho * self.g * delta_h

    def calculate_pressure_loss_fittings(self, coefficient_resistance: float, mid_velocity: float):
        """
        Druckverluste Einbauten Widerstandsbeiwerts
        Args:
            coefficient_resistance ():
        """
        return 0.5 * self.rho * coefficient_resistance * mid_velocity ** 2


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
    # file=f"{self.working_path}{os}{self.ifc_model}
    # file=f"{self.working_path}{os}{self.ifc_model}_building.json"
    # heating_networkx_file=f"{working_path}{os}{ifc_model}_building.json")
    # todo: Load ifc BuildingsGemoetry
    ifc = "C:/02_Masterarbeit/08_BIMVision/IFC_testfiles/AC20-FZK-Haus.ifc"
    #ifc = "C:/02_Masterarbeit/08_BIMVision/IFC_testfiles/AC20-Institute-Var-2.ifc"
    # ifc = "C:/02_Masterarbeit/08_BIMVision\IFC_testfiles\AC20-Institute-Var-2_with_SB-1-0.ifc"
    # ifc ="C:/02_Masterarbeit/08_BIMVision/IFC_testfiles/ERC_Mainbuilding_Arch.ifc"
    # C:\02_Masterarbeit\12_result\Verteilungssysteme\AC20-Institute-Var-2

    ifc_model = "AC20-FZK-Haus"
    #ifc_model = "AC20-Institute-Var-2"

    working_path = "C:/02_Masterarbeit/12_result/Verteilungssysteme"
    # "C:\02_Masterarbeit\12_result\Verteilungssysteme\AC20-Institute-Var-2"

    ifc_building_json = Path(working_path, ifc_model, "ifc_building.json")
    ifc_delivery_json = Path(working_path, ifc_model, "ifc_delivery.json")
    network_building_json = Path(working_path, ifc_model, "network_building.json")
    network_heating_json = Path(working_path, ifc_model, "network_heating.json")
    calc_building_json = Path(working_path, ifc_model, "calculation_building.json")
    calc_heating_json = Path(working_path, ifc_model, "calculation_heating.json")

    # network_heating_json = f"{working_path}/{ifc_model}/network_build.json"
    print("Create Working Path ")
    # Überprüfen, ob der Ordner bereits vorhanden ist
    folder_path = Path(working_path, ifc_model)
    if not os.path.exists(folder_path):
        # Ordner erstellen
        os.makedirs(folder_path)
        print("Ordner wurde erfolgreich erstellt.")
    else:
        print("Der Ordner existiert bereits.")


    print("Load IFC model.")
    ifc = IfcBuildingsGeometry(ifc_file=ifc,
                               ifc_building_json=ifc_building_json,
                               ifc_delivery_json=ifc_delivery_json
                               )
    floor_dict, element_dict = ifc()
    height_list = [floor_dict[floor]["height"] for floor in floor_dict]
    start_point = (4.040, 5.990, 0)
    # start_point = (4.040, 6.50, 0)
    # start_point = (4.440, 6.50, 0)
    #start_point = (23.9, 6.7, -2.50)

    print("Load IFC model complete.")

    floor_dict = GeometryBuildingsNetworkx.read_buildings_json(file=ifc_building_json)
    element_dict = GeometryBuildingsNetworkx.read_buildings_json(file=ifc_delivery_json)
    height_list = [floor_dict[floor]["height"] for floor in floor_dict]

    """netx = GeometryBuildingsNetworkx(network_building_json=network_building_json,
                                     network_heating_json=network_heating_json,
                                     working_path=working_path,
                                     ifc_model=ifc_model,
                                     source_data=start_point,
                                     building_data=floor_dict,
                                     delivery_data=element_dict,
                                     floor_data=height_list)

    heating_circle = netx()"""
    heating_circle = GeometryBuildingsNetworkx.read_json_graph(file=network_heating_json)
    # Start
    GeometryBuildingsNetworkx.visulize_networkx(G=heating_circle, type_grid="Heizkreislauf")
    plt.show()
    calc = CalculateDistributionSystem(calc_heating_json=calc_heating_json,
                                       calc_building_json=calc_building_json)
    calc(G=heating_circle)
    calc.read_pipe_material_excel(filename="C:/02_Masterarbeit/13_Datenbank/distribution_system.xlsx",
                                  sheet_name='Kupferrohre')
    # diameter = calc.calculate_diameter_DIN_EN_12828(Q_H=Q_H_max)
    # diameter = calc.calculate_diameter_VDI_2035(Q_H=Q_H_max)
    # heating_circle.nodes["forward_source_0"]["mass_flow"] = round(m_dot_ges, 2)
    # heating_circle.nodes["forward_source_0"]["diameter"] = round(diameter, 2)

    # delta_p(t), m_dot(t),
    # for node in heating_circle.nodes(data=True)
    # for u, v, data in G.edges(data=True):

    """flow_rate = data['flow_rate']
    velocity = 1.5  # Beispielgeschwindigkeit
    diameter = calc.calculate_diameter(Q_H=Q_H, delta_p=delta_p, length=length)
    pressure_lost = calc.calculate_pressure_lost(flow_rate, diameter, 100, 0.01)

    # Füge berechnete Attribute hinzu
    data['diameter'] = diameter
    data['pressure_lost'] = pressure_lconnect_nodes_with_gridost"""
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
