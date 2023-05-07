import networkx as nx

import matplotlib.pyplot as plt

from pandapipes.component_models import Pipe
import pandapipes.plotting as plot
import pandapipes as pp

import numpy as np
import math
from scipy.spatial import distance

from shapely.geometry import Point, LineString
from shapely.geometry import Polygon, Point

from OCC.Display.SimpleGui import init_display
import pint

import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.STEPControl
import OCC.Core.Interface

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.geom.occ_utils as geom_utils

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_PYTHON_OPENCASCADE, True)
settings.set(settings.USE_WORLD_COORDS, True)
settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
settings.set(settings.INCLUDE_CURVES, True)

class GeometryBuildingsNetworkx():
    # todo: Kanten Kollision vermeiden
    # todo : unit checker mit einbauen
    # todo: polygon bilden -> Nachsten polygon finden -> Knoten projezieren -> Alten Knoten löschen
    # todo : Komponten -> Radiator: L-System Z richtung --|
    # todo: direction_flow für radiator einbauen
    # todo: Zusätzliche punkte einzeichen, damit radiatoren auch erreicht werden können, falls nicht

    def __init__(self, source_data, building_data,  delivery_data, floor_data):
        self.source_data = source_data
        self.building_data = building_data
        self.delivery_data = delivery_data
        self.floor_data = floor_data

    def __call__(self):
        G = nx.Graph(circulation_direction="building")
        G = self.create_nx_network(G=G, edge_name="space", point_data=self.building_data, circulation_direction="building")

        #G = self.nearest_polygon(G, node, room_points)
        netx.visulize_networkx(G=G)
        plt.show()

        fs = nx.Graph(circulation_direction="forward")
        fs = self.create_nx_network(G=fs, edge_name="room", point_data=self.building_data, circulation_direction="building")
        fs = self.create_nx_network(G=fs, edge_name="pipe", point_data=self.source_data, circulation_direction="forward", direction_z=False)  # Add Source
        fs = self.create_nx_network(G=fs, edge_name="pipe", point_data=self.delivery_data, circulation_direction="forward", direction_z=False)  # Add radiators
        netx.visulize_networkx(G=fs)
        plt.show()
        """
        ff_graph_list = []
        for height in self.floor_data:
            f_st = self.steiner_tree(fs, circulation_direction="forward", floor_height=height)
            ff_graph_list.append(f_st)
        fs = self.add_graphs(graph_list=ff_graph_list)
        fs = self.add_rise_tube(G=fs, circulation_direction="forward")
        fs = self.add_component_nodes(frozen_graph=fs, circulation_direction="forward")
        fs = self.remove_edges(G=fs)
        fs = self.directed_graph(G=fs)
        fb = self.create_backward(G=fs)
        heating_circle = self.add_graphs(graph_list=[fs, fb])
        netx.visulize_networkx(G=fs)
        netx.visualzation_networkx_3D(G=G, minimum_trees=[heating_circle])
        plt.show()
        return heating_circle"""


    def nearest_polygon(self,G, node):
        point = Point(G.nodes[node]["pos"])
        _list = []
        element = G.nodes[node]["belongs_to"]
        for node in G.nodes():
            if G.nodes[node]["element"] == element:
                _list.append(G.nodes[node]["pos"])
        coords = np.array(_list)
        node_positions = nx.get_node_attributes(G, 'pos')
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
        poly_list = list(poly_dict.values())
        point_array = np.array([point.x, point.y, point.z])
        rectangles_array = np.array([np.array(rectangle.exterior.coords) for rectangle in poly_list])
        distances = np.linalg.norm(rectangles_array.mean(axis=1) - point_array, axis=1)

        nearest_rectangle = poly_list[np.argmin(distances)]
        projected_point_on_boundary = nearest_rectangle.exterior.interpolate(nearest_rectangle.exterior.project(point))
        projected_point = None
        for poly_key, poly_val in poly_dict.items():
            if nearest_rectangle == poly_val:
                if poly_key == "wall_x_pos" or poly_key == "wall_x_neg":
                    projected_point = Point(projected_point_on_boundary.x, point.y, point.z)
                if poly_key == "wall_y_pos" or poly_key == "wall_y_neg":
                    projected_point = Point(point.x, projected_point_on_boundary.y, point.z)
                if poly_key == "floor" or poly_key == "roof":
                    projected_point = Point(point.x, point.y, projected_point_on_boundary.z)
        return projected_point.coords[0]



    def nearest_neighbour_edge(self, G, node,  type_name, direction, color: str = "red", circulation_direction: str = "forward", tol_value: float = 0):
        # todo: edge element hinzufügen
        # todo: Erst kanten nach elementen ziehen -> Dann die unter elemente -> Dann die gesamtkanten ziehen

        """
        Args:
            G ():
            node ():
            direction ():
            circulation_direction ():
            tol_value ():
        Returns:
        """
        pos_neighbors = []
        neg_neighbors = []
        node_pos = G.nodes[node]["pos"]
        for neighbor, data in G.nodes(data=True):
            if G.nodes[node]["type"] == "radiator" and data["type"] == "radiator":
                continue
            if G.nodes[node]["type"] == "window" and data["type"] == "window" and G.nodes[node]["element"] != data["element"]:
                continue
            if G.nodes[node]["type"] == "window" and  data["element"] == G.nodes[node]["belongs_to"] :
                pass

            if neighbor != node:
                neighbor_pos = data["pos"]
                if abs(node_pos[0] - neighbor_pos[0]) <= tol_value or abs(node_pos[1] - neighbor_pos[1]) <= tol_value or abs(
                        node_pos[2] - neighbor_pos[2]) <= tol_value:
                    if direction == "x":
                        if (neighbor_pos[0] - node_pos[0]) < 0 and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and abs(neighbor_pos[2] - node_pos[2]) <= tol_value:
                            pos_neighbors.append(neighbor)
                        if (neighbor_pos[0] - node_pos[0]) > 0 and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and abs(neighbor_pos[2] - node_pos[2]) <= tol_value:
                            neg_neighbors.append(neighbor)
                    if direction == "y":
                        if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and (neighbor_pos[1] - node_pos[1]) < 0 and abs(neighbor_pos[2] - node_pos[2]) <= tol_value:
                            pos_neighbors.append(neighbor)
                        if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and (neighbor_pos[1] - node_pos[1]) > 0 and abs(neighbor_pos[2] - node_pos[2]) <= tol_value:
                            neg_neighbors.append(neighbor)
                    if direction == "z":
                        if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and (neighbor_pos[2] - node_pos[2])<0:
                            pos_neighbors.append(neighbor)
                        if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and (neighbor_pos[2] - node_pos[2]) >0:
                            neg_neighbors.append(neighbor)
        if pos_neighbors:
            nearest_neighbour = sorted(pos_neighbors, key=lambda p: distance.euclidean(G.nodes[p]["pos"], node_pos))[0]
            length = abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos))
            if nearest_neighbour is not None:
                G.add_edge(node, nearest_neighbour, color=color, type=type_name, circulation_direction=circulation_direction,  direction=direction, weight=length)
        if neg_neighbors:
            nearest_neighbour = sorted(neg_neighbors, key=lambda p: distance.euclidean(G.nodes[p]["pos"], node_pos))[0]
            length = abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos))
            if nearest_neighbour is not None:
                G.add_edge(node, nearest_neighbour, color=color, type=type_name, circulation_direction=circulation_direction, direction=direction,    weight=length)
        return G

    def nearest_edge(self, point, edges):
        """

        Args:
            point ():
            edges ():

        Returns:

        """
        point = Point(point)
        lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges]
        nearest_line = min(lines, key=lambda line: line.distance(point))
        nearest_point = nearest_line.interpolate(nearest_line.project(point))
        new_node = (nearest_point.x, nearest_point.y, nearest_point.z)
        return new_node, (nearest_line.coords[0], nearest_line.coords[-1])

    def nearest_edges(self, point, edges):
        """

        Args:
            point ():
            edges ():

        Returns:

        """
        point = Point(point)
        x_lines, y_lines, z_lines = [], [], []
        for (x1, y1, z1), (x2, y2, z2) in edges:
            if y1 == y2 and z1 == z2:
                x_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
            elif x1 == x2 and z1 == z2:
                y_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
            elif x1 == x2 and y1 == y2:
                z_lines.append(LineString([(x1, y1, z1), (x2, y2, z2)]))
        nearest_x_line = min(x_lines, key=lambda line: line.distance(point)) if x_lines else None
        nearest_y_line = min(y_lines, key=lambda line: line.distance(point)) if y_lines else None
        nearest_z_line = min(z_lines, key=lambda line: line.distance(point)) if z_lines else None
        new_node_x = new_node_y = new_node_z = None
        nearest_edges_x = nearest_edges_y = nearest_edges_z = None
        if nearest_x_line:
            nearest_point = nearest_x_line.interpolate(nearest_x_line.project(point))
            new_node_x = (nearest_point.x, nearest_point.y, nearest_point.z)
            nearest_edges_x = (nearest_x_line.coords[0], nearest_x_line.coords[-1])
        if nearest_y_line:
            nearest_point = nearest_y_line.interpolate(nearest_y_line.project(point))
            new_node_y = (nearest_point.x, nearest_point.y, nearest_point.z)
            nearest_edges_y = (nearest_y_line.coords[0], nearest_y_line.coords[-1])
        if nearest_z_line:
            nearest_point = nearest_z_line.interpolate(nearest_z_line.project(point))
            new_node_z = (nearest_point.x, nearest_point.y, nearest_point.z)
            nearest_edges_z = (nearest_z_line.coords[0], nearest_z_line.coords[-1])
        return new_node_x, new_node_y, new_node_z, nearest_edges_x, nearest_edges_y, nearest_edges_z


    def add_rise_tube(self, G, circulation_direction:str = "forward"):
        """

        Args:
            G ():
            circulation_direction ():

        Returns:

        """
        for node, data in G.nodes(data=True):
            if G.nodes[node]["type"] == "source":
                self.nearest_neighbour_edge(G=G, node=node, type_name="rise_tube", direction="z", circulation_direction=circulation_direction)
        return G


    def delete_duplicate_nodes(self, G):
        """Entfernt Knoten aus einem networkx-Graphen, die dieselbe Position haben, außer einem."""
        nodes_to_remove = set()  # Set der Knoten, die entfernt werden sollen
        pos_to_node = {}  # Dict zur Speicherung des Knotens mit der jeweiligen Position

        # Durchlaufen Sie alle Knoten und suchen Sie nach Duplikaten
        for node, attrs in G.nodes(data=True):
            if attrs["type"] == "window":
                pos = attrs["pos"]
                if pos in pos_to_node:
                    # Markieren Sie den Knoten, der entfernt werden soll
                    nodes_to_remove.add(node)
                else:
                    pos_to_node[pos] = node
        # Entfernen Sie die doppelten Knoten
        G.remove_nodes_from(nodes_to_remove)
        return G


    def snapping(self, G, node, belongs_to_edge_list, circulation_direction):
        """
        Args:
            G ():
            no_path_list ():
            circulation_direction ():

        Returns:

        """
        node_list = []
        point = G.nodes[node]["pos"]

        new_node_x, new_node_y, new_node_z, nearest_edge_x, nearest_edge_y, nearest_edge_z = self.nearest_edges(point, belongs_to_edge_list)
        if self.add_node_if_not_exists(G, new_node_x) is False:
            if new_node_x is not None:
                #print(new_node_x)
                #print(nearest_edge_x)
                node_id = f"{node}_x_space"
                G.add_node(node_id, pos=new_node_x,  type="space", element=G.nodes[node]["belongs_to"],  circulation_direction=circulation_direction)
                node_list.append(node_id)
        if self.add_node_if_not_exists(G, new_node_y) is False:
            if new_node_y is not None:
                #print(new_node_y)
                #print(nearest_edge_y)
                node_id = f"{node}_y_space"
                G.add_node(node_id, pos=new_node_y, type="space", element=G.nodes[node]["belongs_to"], circulation_direction=circulation_direction)
                node_list.append(node_id)
        if self.add_node_if_not_exists(G, new_node_z) is False:
            if new_node_z is not None:
                #print(new_node_z)
                node_id = f"{node}_z_space"
                G.add_node(node_id, pos=new_node_z,  type="space",element=G.nodes[node]["belongs_to"],  circulation_direction=circulation_direction)
                node_list.append(node_id)
        if node_list is None:
            pass
            #print(node)
        if node == "25nJxEpYf8LRDJNkMUVO0m_window_4_projection":
            new_node_x, new_node_y, new_node_z, nearest_edge_x, nearest_edge_y, nearest_edge_z = self.nearest_edges(
                point, belongs_to_edge_list)
            #print(belongs_to_edge_list)
            #print(new_node_x)


        return node_list

    # todo: ids ändern auf die im reader, einfacher nachzuverfolgen: 25nJxEpYf8LRDJNkMUVO0m_window_4_projection
    def remove_edge_overlap(self, G, circulation_direction):
        """

        Args:
            G ():
            circulation_direction ():

        Returns:

        """
        edges_to_remove = []
        new_nodes = []
        new_edges = []
        for i, e1 in enumerate(G.edges()):
            for e2 in G.edges():
                if e1 != e2:
                    if G.nodes[e1[0]]['pos'] != G.nodes[e2[0]]['pos'] and G.nodes[e1[1]]['pos'] != G.nodes[e2[1]]['pos']:
                        l1 = LineString([G.nodes[e1[0]]['pos'], G.nodes[e1[1]]['pos']])
                        l2 = LineString([G.nodes[e2[0]]['pos'], G.nodes[e2[1]]['pos']])
                        if l1.crosses(l2):
                            intersection = l1.intersection(l2)
                            node_name = f"{circulation_direction}_multi_space_{i}"
                            new_node = (node_name, {"pos": (intersection.x, intersection.y, intersection.z), "type": "space", "circulation_direction": circulation_direction})
                            new_nodes.append(new_node)
                            edges_to_remove.append(e1)
                            edges_to_remove.append(e2)
                            if G.has_edge(e1[0], e1[1]):
                                new_edges.append((e1[0], node_name, {"weight":  abs(distance.euclidean(G.nodes[e1[0]]["pos"], (intersection.x, intersection.y, intersection.z)))}))
                                new_edges.append((e1[1], node_name, {"weight":  abs(distance.euclidean(G.nodes[e1[1]]["pos"], (intersection.x, intersection.y, intersection.z)))}))
                            if G.has_edge(e2[0], e2[1]):
                                new_edges.append((e2[0], node_name, {"weight":  abs(distance.euclidean(G.nodes[e2[0]]["pos"], (intersection.x, intersection.y, intersection.z)))}))
                                new_edges.append((e2[1], node_name, {"weight":  abs(distance.euclidean(G.nodes[e2[1]]["pos"], (intersection.x, intersection.y, intersection.z)))}))
        for e in edges_to_remove:
            if G.has_edge(e[0], e[1]):
                G.remove_edge(e[0], e[1])
        G.add_nodes_from(new_nodes)
        G.add_edges_from(new_edges)
        return G

    def add_new_component_nodes(self, G, frozen_graph, node, str_chain):
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
        i = 0
        for edge in frozen_graph.edges(node, data=True):
            v = G.nodes[edge[0]]['pos']
            u = G.nodes[edge[1]]['pos']
            if frozen_graph.edges[edge[0], edge[1]]["direction"] == "x" or frozen_graph.edges[edge[0], edge[1]]["direction"] == "y":
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
                    node_dictionary[f"{edge[0]}_{str_chain[i]}_{i}"] = {"direction_flow":  direction_flow, "pos": (x, y, z), "type": str_chain[i] }
                    i = i + 1
        return node_dictionary


    def add_component_nodes(self, frozen_graph, circulation_direction: str = "forward"):
        """

        Args:
            frozen_graph ():
            circulation_direction ():

        Returns:

        """
        G = nx.Graph(frozen_graph)
        radiator_dict = {}
        source_dict = {}
        source_nodes = None
        radiator_nodes = None
        for node, attributes in G.nodes(data=True):
            if attributes.get('type') == 'source':
                l_rules = "junction" + "-source-" + "junction" + "-pipe-" + "junction" + "-pump-" + "junction"
                str_source_chain = l_rules.split("-")
                source_nodes = self.add_new_component_nodes(G, frozen_graph, node,  str_source_chain)
                source_dict[node] = source_nodes
            if attributes.get('type') == 'radiator':
                l_rules = "junction" + "-ventil-" + "junction" + "-pipe-" + "junction" + "-radiator"
                str_radi_chain = l_rules.split("-")
                radiator_nodes = self.add_new_component_nodes(G, frozen_graph, node, str_radi_chain)
                radiator_dict[node] = radiator_nodes
        if source_nodes is not None:
            for source in source_dict:
                for node in source_dict[source]:
                    G.add_node(node, pos=source_dict[source][node]["pos"], type=source_dict[source][node]["type"], circulation_direction=circulation_direction)
                    G = self.nearest_neighbour_edge(G=G, type_name="pipe", node=node, direction="x", circulation_direction=circulation_direction)
                    G = self.nearest_neighbour_edge(G=G, type_name="pipe", node=node, direction="y", circulation_direction=circulation_direction)
        if radiator_nodes is not None:
            for rad in radiator_dict:
                for node in radiator_dict[rad]:
                    G.add_node(node, pos=radiator_dict[rad][node]["pos"], type=radiator_dict[rad][node]["type"], circulation_direction=circulation_direction)
                    G = self.nearest_neighbour_edge(G=G, type_name="pipe",node=node, direction="y",  circulation_direction=circulation_direction)
        G = self.remove_edge_overlap(G, circulation_direction=circulation_direction)  # check if edges are overlapping, if build point in intersection and remove the old egdes and build new
        return G

    def add_node_if_not_exists(self, G, point):
        """

        Args:
            G ():
            point ():

        Returns:

        """
        for n in G.nodes():
            if G.nodes[n]['pos'] == point:
                return True
        else:
            return False

    def is_node_element_on_space_path(self, G, node):
        # todo: Window 8 Punkte auf 4 reduzieren
        """
        Args:
            G ():
            # Überprüfen, ob ein Fensterknoten eine Verbindung zu einem Spaceknoten hat
            circulation_direction ():
        Returns:
        """
        for neighbor in G.neighbors(node):
            if G.nodes[neighbor]['type'] == 'space':
                return True
        return False


    def get_room_edges(self, G, node):
        """

        Args:
            G ():

        Returns:

        """
        edge_list = []
        x_lines, y_lines, z_lines = [], [], []
        for edge in G.edges(data=True):
            #if G.nodes[edge[0]]["type"] == "radiator" or G.nodes[edge[1]]["type"] == "radiator":
            #    continue
            if G.nodes[edge[0]]["element"] == G.nodes[node]["belongs_to"] and G.nodes[edge[1]]["element"] == G.nodes[node]["belongs_to"]:
            #else:
               edge_list.append((G.nodes[edge[0]]["pos"], G.nodes[edge[1]]["pos"]))
        #print(len(edge_list))
        return edge_list

    def add_missing_edges(self, G,  circulation_direction:str = "forward"):
        """

        Args:
            G ():
            type_node ():
            circulation_direction ():

        Returns:
        """

        _list = []
        window_nodes = [node for node in G.nodes() if G.nodes[node]['type'] == 'window']
        for window_node in window_nodes:
            if self.is_node_element_on_space_path(G=G, node=window_node) is False:
                _list.append(window_node)

        if len(_list) > 0:
            for i, node in enumerate(_list):
                projected_point = self.nearest_polygon(G, node)
                G.add_node(f"{node}_projection", pos=projected_point, type=G.nodes[node]["type"], element=G.nodes[node]["element"],
                           circulation_direction=circulation_direction, belongs_to=G.nodes[node]["belongs_to"])
                G.remove_node(node)

        G = self.delete_duplicate_nodes(G=G)
        projection_list = [n for n in G.nodes() if G.nodes[n]['type'] == 'window']
        G = self.create_edges(G=G, node_list=projection_list,   type_name="space_boundary", circulation_direction=circulation_direction, tol_value=0.0, direction_x=True, direction_y=True, direction_z=True)
        node_list = []
        for node in projection_list:
            edge_space_list = self.get_room_edges(G=G, node=node)
            if len(edge_space_list) > 0:
                _node_list = self.snapping(G=G, node=node, belongs_to_edge_list=edge_space_list,
                              circulation_direction=circulation_direction)
                node_list.extend(_node_list)

        #if len(node_list) > 0:
        #    for nodes in node_list:
                """G = self.nearest_neighbour_edge(G=G, node=nodes, type_name="room_border", direction="y", circulation_direction=circulation_direction,
                                                tol_value=0)
                G = self.nearest_neighbour_edge(G=G, node=nodes, type_name="room_border", direction="y", circulation_direction=circulation_direction,
                                                tol_value=0)"""
        #        G = self.nearest_neighbour_edge(G=G, node=nodes, type_name="room_border", direction="z", circulation_direction=circulation_direction,
        #                                        tol_value=0)
        return G

    def create_edges(self, G, node_list,  type_name, circulation_direction, direction_x: bool = True , direction_y:bool = True, direction_z: bool= True, tol_value:float = 0.0):
        """
        # todo: Kanten nicht direkt anhand der Position sondern vorallem nach den IDS
        Args:
            G ():
            node_list ():
            type_name ():
            circulation_direction ():
            direction_x ():
            direction_y ():
            direction_z ():
            tol_value ():
        Returns:
        """
        for node in node_list:
            if direction_x is True:
                G = self.nearest_neighbour_edge(G=G, type_name=type_name, node=node,  direction="x", circulation_direction=circulation_direction, tol_value=tol_value)
            if direction_y is True:
                G = self.nearest_neighbour_edge(G=G, type_name=type_name, node=node,  direction="y", circulation_direction=circulation_direction, tol_value=tol_value)
            if direction_z is True:
                G = self.nearest_neighbour_edge(G=G, type_name=type_name,  node=node, direction="z", circulation_direction=circulation_direction, tol_value=tol_value)
        return G

    def create_nodes(self, G , color,  point_data, circulation_direction):
        # todo: Attrobite hinzufügen: Name, ID, Abhöngigkeiten, Höhe.
        # todo: circulation_direction nicht immer mit rein
        """
        room_points = [room_dict[room]["global_corners"] for room in room_dict]
        room_tup_list = [tuple(p) for points in room_points for p in points]
        building_points = tuple(room_tup_list)
        Args:
            G ():
            points ():
            circulation_direction ():
            type_node ():
        Returns:
        """
        element_node_dict = {}
        node_list = []
        for p in point_data:
            room_points = point_data[p]["global_corners"]
            if room_points is not None:
                for i, points in enumerate(room_points):
                    type_node = point_data[p]["type"]
                    G.add_node(f"{p}_{type_node}_{i}", pos=points, color=color, type=type_node, element=p ,
                                circulation_direction=circulation_direction, belongs_to=point_data[p]["belongs_to"])
                    node_list.append(f"{p}_{type_node}_{i}")
        return G, node_list

    def create_nx_network(self, G, point_data, edge_name, circulation_direction,  color:str ="red" , direction_x: bool = True , direction_y:bool = True, direction_z: bool= True):
        """
        Args:
            G ():
            points ():
            circulation_direction ():
            type_node ():
            **args ():
        Returns:
        """
        print("Build nodes")

        G, node_list = self.create_nodes(G=G, point_data=point_data, color=color, circulation_direction=circulation_direction)
        print("Create edges")
        G = self.create_edges(G=G, node_list=node_list,   type_name=edge_name, circulation_direction=circulation_direction, tol_value=0, direction_x=direction_x, direction_y=direction_y, direction_z=direction_z)
        print(G )
        print("Add missing edges")
        G = self.add_missing_edges(G=G,    circulation_direction=circulation_direction)  # Check if all points are connected, if not add new node from the nearest exisiting edge and connect
        print("Remove overlapping edges")

        G = self.remove_edge_overlap(G, circulation_direction=circulation_direction)  # check if edges are overlapping, if build point in intersection and remove the old egdes and build new"""

        return G


    def visulize_networkx(self, G):
        """
        [[[0.2 4.2 0.2]
            [0.2 0.2 0.2]]
        Args:
            G ():

        """
        edge_xyz = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos']) for u, v in G.edges()])
        node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values()))
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        ax.scatter(*node_xyz.T, s=50, ec="w")
        for vizedge in edge_xyz:
            ax.plot(*vizedge.T, color="tab:gray")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        fig.tight_layout()

    def visualzation_networkx_3D(self, G, minimum_trees: list):
        """

        Args:
            G ():
            minimum_trees ():
        """
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values()))
        edge_xyz = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos']) for u, v in G.edges()])
        ax.scatter(*node_xyz.T, s=50, ec="w")
        for vizedge in edge_xyz:
            ax.plot(*vizedge.T, color="tab:gray")
        for minimum_tree in minimum_trees:
            node_xyz = np.array(sorted([data["pos"] for n, data in minimum_tree.nodes(data=True) if data["type"] in {"source"}]))
            ax.scatter(*node_xyz.T, s=100, ec="green")
            node_xyz = np.array(sorted([data["pos"] for n, data in minimum_tree.nodes(data=True) if data["type"] in {"radiator"}]))
            ax.scatter(*node_xyz.T, s=100, ec="red")
            node_xyz = np.array(sorted([data["pos"] for n, data in minimum_tree.nodes(data=True) if data["type"] not in  {"source"} and{"radiator"} ]))
            ax.scatter(*node_xyz.T, s=100, ec="yellow")
        for minimum_tree in minimum_trees:
            edge_xyz = np.array([(minimum_tree.nodes[u]['pos'], minimum_tree.nodes[v]['pos']) for u, v in minimum_tree.edges()])
            for vizedge in edge_xyz:
                if minimum_tree.graph["circulation_direction"] == "forward":
                    ax.plot(*vizedge.T, color="tab:red")
                else:
                    ax.plot(*vizedge.T, color="blue")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        fig.tight_layout()


    def steiner_tree(self, graph: nx.Graph(), circulation_direction:str = "forward", floor_height : int = 0):
        """
        Args:
            graph ():
            circulation_direction ():
            floor_height ():

        Returns:
        """
        term_points = sorted([n for n, data in graph.nodes(data=True) if data["type"] in {"radiator", "source"} and data["pos"][2] == floor_height])
        steinerbaum = nx.algorithms.approximation.steinertree.steiner_tree(graph, term_points, method="kou")
        total_weight = sum([edge[2]['weight'] for edge in steinerbaum.edges(data=True)])
        print(f"Steiner Tree: {circulation_direction} {total_weight}")
        steinerbaum.graph["circulation_direction"] = circulation_direction
        return steinerbaum

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
        #start = (start_p[0] + offset, start_p[1] + offset, start_p[2])
        start = tuple((x + offset, y + offset, z ) for x, y, z in start_p)
        path = tuple((x + offset, y + offset, z ) for x, y, z in path_p)
        end = tuple((x + offset, y + offset, z ) for x, y, z in end_p)
        return start, path , end

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

    def add_graphs(self,  graph_list):
        for i in range(0, len(graph_list)-1):
            G = nx.compose(graph_list[i], graph_list[i+1])
        return G

    def connect_forward_to_backward(self):
        pass

    def directed_graph(self, G):
        # todo: Attribute übergebe
        D = nx.DiGraph(circulation_direction="forward")
        D.add_nodes_from(G.nodes(data=True))
        T = nx.bfs_tree(G, "forward_source_0")
        for edges in T.edges():
            D.add_edge(edges[0], edges[1])
        return D



    def greedy_path(self, G, start_node, end_node):
        path = [start_node]
        current_node = start_node
        while current_node != end_node:
            neighbors = list(G.neighbors(current_node))
            if len(neighbors) == 0:
                break
            distances = [nx.shortest_path_length(G, neighbor, end_node) for neighbor in neighbors]
            index = distances.index(min(distances))
            current_node = neighbors[index]
            path.append(current_node)
        return path

        # Beispiel: Ungerichteter Graph
        G = nx.Graph()
        G.add_edges_from([(1, 2), (2, 3), (3, 4), (4, 5), (3, 5), (5, 6), (4, 6)])

        # Umwandlung in gerichteten Graphen mit dem Greedy-Algorithmus
        D = nx.DiGraph()
        for node in G.nodes:
            D.add_node(node)
        for edge in G.edges:
            path = greedy_path(G, edge[0], edge[1])
            for i in range(len(path) - 1):
                D.add_edge(path[i], path[i + 1])


        """node_xyz = np.array(sorted(nx.get_node_attributes(D, "pos").values()))
        edge_xyz = np.array([(D.nodes[u]['pos'], D.nodes[v]['pos']) for u, v in D.edges()])
        ax.scatter(*node_xyz.T, s=100, ec="w")
        for vizedge in edge_xyz:
            print(vizedge[0])
            arrowprops = dict(facecolor='black', arrowstyle="-|>")
            #ax.plot(*vizedge.T, color="tab:gray")
            ax.annotate("text", vizedge[0], vizedge[1], arrowprops=arrowprops)
            # Kanten mit Pfeilen plotten
            #u, v = edge
            #arrowprops = dict(facecolor='black', arrowstyle="-|>")
            #ax.annotate("", pos[v], pos[u], arrowprops=arrowprops)"""
        return D

    def remove_edges(self, G):
        node_dict = {}
        edge_dict = {}

        for node in G.nodes():
            if 'pos' in G.nodes[node]:
                edge_dict[node] =  list(G.edges(node))
                node_dict[node] = list(G.neighbors(node))
        G.remove_edges_from(list(G.edges()))
        for node in node_dict:
            z_list = []
            x_list = []
            y_list = []
            x_1, y_1, z_1 = G.nodes[node]['pos']
            for neigh in node_dict[node]:
                x_2, y_2, z_2 = G.nodes[neigh]['pos']
                if x_1 == x_2 and y_1 == y_2:
                    z_list.append(neigh)
                if y_1 == y_2 and z_1 == z_2:
                    x_list.append(neigh)
                if x_1 == x_2 and z_1 == z_2:
                    y_list.append(neigh)
            if len(z_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_z_neighbor = None
                pos_z_neighbor = None
                for z in z_list:
                    diff  = z_1 - G.nodes[z]['pos'][2]
                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_z_neighbor = z
                    elif diff < 0 and abs(diff) < min_neg_diff:
                        min_neg_diff = abs(diff)
                        pos_z_neighbor = z
                if neg_z_neighbor is not None:
                    G.add_edge(node, neg_z_neighbor)
                if pos_z_neighbor is not None:
                    G.add_edge(node, pos_z_neighbor)
            if len(x_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_x_neighbor = None
                pos_x_neighbor = None
                for x in x_list:
                    diff = x_1 - G.nodes[x]['pos'][0]
                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_x_neighbor = x
                    elif diff < 0 and abs(diff) < min_neg_diff:
                        min_neg_diff = abs(diff)
                        pos_x_neighbor = x
                if neg_x_neighbor is not None:
                    G.add_edge(node, neg_x_neighbor)
                if pos_x_neighbor is not None:
                    G.add_edge(node, pos_x_neighbor)

            if len(y_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_y_neighbor = None
                pos_y_neighbor = None
                for y in y_list:
                    diff = y_1 - G.nodes[y]['pos'][1]
                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_y_neighbor = y
                    elif diff < 0 and abs(diff) < min_neg_diff:
                        min_neg_diff = abs(diff)
                        pos_y_neighbor = y
                if neg_y_neighbor is not None:
                    G.add_edge(node,neg_y_neighbor)
                if pos_y_neighbor is not None:
                    G.add_edge(node, pos_y_neighbor)
        return G


    def create_backward(sel, G, circulation_direction:str = "backward"):
        G_reversed = G.reverse()
        G_reversed.graph["circulation_direction"] = circulation_direction
        for node in G_reversed.nodes():
            G_reversed.nodes[node]['circulation_direction'] = circulation_direction
            G_reversed = nx.relabel_nodes(G_reversed, {node: node.replace("forward", "backward")})
        return G_reversed


class IfcBuildingsGeometry():



    def __init__(self, ifc_file):
        self.model = ifcopenshell.open(ifc_file)

    def __call__(self):
        room = self.room_element_position()
        floor = self.sort_room_floor(spaces_dict=room)
        floor_elements, room_dict,  element_dict = self.sort_space_data(floor)
        #self.visualize_spaces()
        return floor_elements, room_dict,  element_dict

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
                                            global_vertices = ifcopenshell.geom.create_shape(self.model, vertices).geometry


    def sort_space_data(self, floor_elements, ref_point: tuple = (0,0,0)):
        """
        Args:
            floor_elements ():
            ref_point ():
        Returns:

        """
        # todo: Als Dicitonary umwandeln besonders für die Elements {windows_1: {pos: (x,y,z), (x,y,z) ,(x,y,z), "from" : Space_1, }
        # todo: Form ändern ((0,0,0), ((1,1,1))
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
                #room_points.extend(rooms[room]["global_corners"])
                #max_coords = np.amax(rooms[room]["global_corners"], axis=0)
                #min_coords = np.amin(rooms[room]["global_corners"], axis=0)
                #room_dict[room] =
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

        return floor_dict, room_dict,  element_dict

    def visualize_spaces(self):
        spaces = self.model.by_type("IfcSpace")
        display, start_display, add_menu, add_function_to_menu = init_display()
        for space in spaces:
            shape = ifcopenshell.geom.create_shape(settings, space).geometry
            display.DisplayShape(shape, update=True,    transparency=0.7)
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
        window= self.model.by_type("IfcWindow")

        display, start_display, add_menu, add_function_to_menu = init_display()


        _list.append(walls)
        _list.append(spaces)
        #_list.append(doors)
        #_list.append(window)
        _list = list(walls + spaces + doors + window)
        for wall in _list:
            shape = ifcopenshell.geom.create_shape(settings, wall).geometry
            t = display.DisplayShape(shape, update=True,    transparency=0.7)
            location = wall.ObjectPlacement.RelativePlacement.Location.Coordinates
            #faces = TopExp.TopExp_Explorer(shape, TopAbs.TopAbs_FACE)
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
                #display.DisplayShape(face_location, update=True, transparency=0.7)

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

    def related_object_space(self, room):
        room_elements = []
        element_dict = {}
        for boundary_element in self.model.by_type("IfcRelSpaceBoundary"):
            if boundary_element.RelatingSpace == room:
                room_elements.append(boundary_element.RelatedBuildingElement)
        for element in room_elements:
            if element is not None:
                # wohl korrekt
                box = None
                if element.is_a("IfcWall"):
                    matrix = self.get_global_matrix(element)
                    relative_point = np.array([0, 0, 0, 1])
                    absolute_position = np.dot(matrix, relative_point)[:3]
                    global_box = self.calc_bounding_box(element)
                    global_corners = self.absolute_points_room(element=element, matrix=matrix)
                    element_dict[element.GlobalId] = {"type": "wall",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      # "transformation_matrix": matrix,
                                                      "Position": absolute_position,
                                                      # "Bounding_box": global_box,
                                                      "global_corners": global_corners,
                                                      "belongs_to":  room.GlobalId
                                                      }
                if element.is_a("IfcDoor"):
                    matrix = self.get_global_matrix(element)
                    relative_point = np.array([0, 0, 0, 1])
                    absolute_position = np.dot(matrix, relative_point)[:3]
                    global_box = self.calc_bounding_box(element)
                    global_corners = self.absolute_points_room(element=element, matrix=matrix)
                    element_dict[element.GlobalId] = {"type": "door",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      # "transformation_matrix": matrix,
                                                      "Position": absolute_position,
                                                      # "Bounding_box": global_box,
                                                      "global_corners": global_corners,
                                                      "belongs_to":  room.GlobalId}
                # todo: Fenster Koordianten noch nicht korrekt: die bounding box wird falsch addiert, allerdings scheint die Transformationsmatrix auch nicht korrekt zu sein.
                if element.is_a("IfcWindow"):
                    matrix = self.get_global_matrix(element)
                    relative_point = np.array([0, 0, 0, 1])
                    absolute_position = np.dot(matrix, relative_point)[:3]
                    global_box = self.calc_bounding_box(element)
                    global_corners = self.absolute_points_room(element=element, matrix=matrix)
                    element_dict[element.GlobalId] = {"type": "window",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      # "transformation_matrix": matrix,
                                                      "Position": absolute_position,
                                                      # "Bounding_box": global_box,
                                                      "global_corners": global_corners,
                                                      "belongs_to":  room.GlobalId}
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
            matrix = self.get_global_matrix(element=space)
            relative_point = np.array([0, 0, 0, 1])
            absolute_position = np.dot(matrix, relative_point)[:3]
            # Bounding box
            global_box = self.calc_bounding_box(space)
            global_corners = self.absolute_points_room(element=space, matrix=matrix)
            spaces_dict[space.GlobalId] = {"type": "space",
                                           "number": space.Name,
                                           "Name": space.LongName,
                                           "id": space.id(),
                                           # "transformation_matrix": matrix,
                                           "Position": absolute_position,
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
                space_height = spaces_dict[room]["Position"][2]
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
        #ax.scatter(*node_xyz.T, s=100, ec="w")
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
        #for i, coord in enumerate(points):
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
        #for start in start_points:
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
        #self.reduce_nodes(graph=graph)
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
            pp.create_junction(net,  node_name=str(node), pn_bar=1.0, tfluid_k=283.15)
        # Füge Kanten zum Netzwerk hinzu
        print(G.edges)
        for edge in G.nodes:
            print(edge)
            print(edge[0])
            from_bus = str(edge[0])
            print(from_bus)
            to_bus = str(edge[1])
            # Überprüfe, ob die Knoten existieren, bevor du eine Rohrleitung erstellst
            if from_bus in net.junction.index and to_bus in net.junction.index:
                pp.create_pipe_from_parameters(net, from_bus, to_bus, length_km=1, diameter_m=0.1)
            else:
                print(
                    f"Warning: Pipe {from_bus}-{to_bus} tries to attach to non-existing junction(s) {from_bus} or {to_bus}.")

        # Prüfe, ob das Netzwerk korrekt erstellt wurde
        print(net)


    def export_graph_json(self, G):
        data = nx.readwrite.json_graph.node_link_data(G)
        with open("graph.json", "w") as f:
            json.dump(data, f)


    def reduce_nodes(self, graph: nx.DiGraph):
        from sklearn.cluster import KMeans
        X = np.array(list(graph.nodes))
        print(X)
        kmeans = KMeans(n_clusters=2, random_state=0).fit(X)
        centers = kmeans.cluster_centers_
        print(centers)



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
        return graph, mst,  start, end_points



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
            #room_points_floor = []
            for room in rooms:
                elements = rooms[room]["room_elements"]
                room_points.extend(rooms[room]["global_corners"])
                max_coords = np.amax(rooms[room]["global_corners"], axis=0)
                min_coords = np.amin(rooms[room]["global_corners"], axis=0)
                for element in elements:
                    if elements[element]["type"] == "wall":
                        corner_points = elements[element]["global_corners"]
                        # print(elements[element]["number"])
                        # print(corner_points)
                        # x_midpoint = np.mean(corner_points[:, 0])
                        # y_midpoint = np.mean(corner_points[:, 1])
                        # z_low = np.min(corner_points[:, 2])
                        # end_point = np.array([x_midpoint, y_midpoint, z_low])
                        # end_points.append(end_point)
                    if elements[element]["type"] == "door":
                        corner_points = elements[element]["global_corners"]
                        # print(elements[element]["number"])
                        # print(corner_points)
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

    def __init__(self, c_p: float = 4.18, g:float = 9.81, rho: float =  1000, f:float = 0.02, v_mittel:float =0.5,
                     v_max:float =3, p_max:float = 10, kin_visco: float = 1.0*10**-6,
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


    def calculate_pressure_lost(self, length, diameter):
        """
        f * (rho * v**2) / (2 * D * g)
        Args:
            length ():

        Returns:

        """
        return self.f * (self.rho * self.v_max**2) * length / (2 * diameter * self.g)





    def calculate_radiator_area(self, Q_H: float, alpha: float = 0.25, delta_T: int = 50):
        """
        Q_H = alpha * A + delta_T
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
        #Q_vol = Q_H * Calc_pipes.watt/ (3600 * self.rho  * Calc_pipes.kg/Calc_pipes.m**3)
        Q_vol = Q_H  / (3600 * self.rho )
        return (4* self.f * Q_vol / (math.pi * self.kin_visco))


    def calculate_diameter(self, Q_H: float, delta_p: float, length: float):
        """
        Q_H = alpha *pi * (d**2 / 4) * delta_T
        d = 2 * ((m_dot / (rho * v_max * pi)) ** 0.5) * (p_max / p)
        d = (8fLQ^2)/(pi^2delta_p)
        d = (8 * Q * f * L) / (π^2 * Δp * ρ)
        """
        #return math.sqrt(4 * Q_H/(alpha * self.delta_T * math.pi))
        return (8 * self.f  * length * Q_H ** 2)/(math.pi**2 * delta_p*self.rho)

    def calculate_m_dot(self, Q_H: float):
        """
        Q_H = m_dot * c_p * delta_T
        """
        return Q_H / (self.c_p * self.delta_T)



class PandaPipesSystem(object):


    def __init__(self,G):
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
    # todo : Welche Informationen sollte die Knonten bekommen: R
    """start_point = ((0, 0, 0), (0, 0, 5))
    path_points = (
    (0, 0, 0), (0, 0, 5), (0, 4, 0), (0, 4, 5), (4, 4, 0), (4, 4, 5), (4, 0, 0), (4, 0, 5), (0, 0, 10), (4, 4, 10),
    (0, 4, 10), (4, 0, 10))
    end_points = ((1.5, 5, 0), (0, 6, 0), (4, 3, 0), (2, 5, 0), (1, 6, 0), (4, 3, 5), (2, 5, 5), (1, 6, 5), (0.5, 5, 0))
    floor_list = [0, 5]"""
    #((-3.74, -1.98, 0.0), (0.66, -1.98, 2.5), [(-3.74, -1.98, 0.0), (0.66, -1.98, 2.5))

    # todo: Load ifc BuildingsGemoetry
    ifc = "C:/02_Masterarbeit/08_BIMVision/IFC_testfiles/AC20-FZK-Haus.ifc"
    #ifc ="C:/02_Masterarbeit/08_BIMVision/IFC_testfiles/AC20-Institute-Var-2.ifc"
    #ifc ="C:/02_Masterarbeit/08_BIMVision/IFC_testfiles/ERC_Mainbuilding_Arch.ifc"
    ifc = IfcBuildingsGeometry(ifc_file=ifc)
    floor_dict, room_dict,  element_dict = ifc()
    height_list = [floor_dict[floor]["height"] for floor in floor_dict]
    room_dict.update(element_dict)
    element_points = [element_dict[element]["global_corners"] for element in element_dict]


    #element_tup_list = [tuple(p) for points in element_points for p in points]
    #element_tuple = tuple(element_tup_list)
    start_point = ((4.040, 5.990, 0), (4.040, 5.990, 2.7))

    # todo: Create Network from BuildingGeometry
    #netx = GeometryBuildingsNetworkx(source_points=start_point, building_points=path_points,  delivery_points=end_points, floor_heights=floor_list)
    netx = GeometryBuildingsNetworkx(source_data=start_point, building_data=room_dict, delivery_data=element_dict,
                                     floor_data=height_list)
    heating_circle = netx()
    # todo: Argument belong_to mit übergeben, ID von Räumen in Knonten und Kanten etc. übergeben
    # todo: Vorkalkulation
    # Start
    calc = CalculateDistributionSystem()
    Q_H_max = 20 # [kW]
    m_dot_ges = calc.calculate_m_dot(Q_H=Q_H_max)
    diameter = calc.calculate_diameter_DIN_EN_12828(Q_H=Q_H_max)
    diameter = calc.calculate_diameter_VDI_2035(Q_H=Q_H_max)
    heating_circle.nodes["forward_source_0"]["mass_flow"] = round(m_dot_ges, 2)
    heating_circle.nodes["forward_source_0"]["diameter"] = round(diameter, 2)
    # delta_p(t), m_dot(t),



    #for node in heating_circle.nodes(data=True)
    #for u, v, data in G.edges(data=True):



    """flow_rate = data['flow_rate']
    velocity = 1.5  # Beispielgeschwindigkeit
    diameter = calc.calculate_diameter(Q_H=Q_H, delta_p=delta_p, length=length)
    pressure_lost = calc.calculate_pressure_lost(flow_rate, diameter, 100, 0.01)

    # Füge berechnete Attribute hinzu
    data['diameter'] = diameter
    data['pressure_lost'] = pressure_lost"""
    #G.edges[u, v]['diameter'] = diameter
    #G.edges[u, v]['pressure_lost'] = pressure_lost




    #net = calc.create_networkx_junctions(G=mst)

    #calc.test_lindemayer()
    # calc._get_attributes(net=net)

    #net = netx.test_pipe(start_point=start_point, end_points=end_points, path_point=mst.edges)
    #net = netx.empty_network()
    #net = netx.create_source(net=net, start=list(mst.nodes())[0])
    #net = netx.create_pump(net=net, start=list(mst.nodes())[0])
    #calc.create_sink(net=net, end_points=end_points)


    # net = calc.create_own_network()
    # net = calc.test()
    # calc.hydraulic_balancing_results(net=net)
    #calc.plot_systems(net=net)
    #calc.visualzation_networkx_3D(G=graph, minimum_tree=mst, start_points=start_point, end_points=end_points)
    #G = nx.compose(f_st, b_st)
    # calc.visulize_networkx(G=b_graph)
    #calc.visulize_networkx(G=f_graph)
    #calc.visualzation_networkx_3D(G=G, minimum_trees=[f_st])
    #calc.visualzation_networkx_3D(G=b_graph, minimum_trees=[b_st])
    #calc.visualzation_networkx_3D(G=G, minimum_trees=[b_st, f_st])

    #calc.visualzation_networkx_3D(G=f_graph, minimum_tree=f_st, start_points=start_point, end_points=end_points)


