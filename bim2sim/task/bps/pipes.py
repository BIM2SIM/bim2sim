import pandapipes as pp
import networkx as nx
import pandapipes.plotting as plot
import matplotlib.pyplot as plt
import numpy as np
#from PyQt5.QtCore.QByteArray import length
from openalea.plantgl.math import direction
from pandapipes.component_models import Pipe
import pandapipes.networks
import math
import random
from scipy.spatial.distance import cdist
from scipy.spatial import distance
from shapely.geometry import Polygon, Point
from shapely.geometry import Point, LineString
import pint


class Calc_pipes():
    ureg = pint.UnitRegistry()
    m = ureg.meter
    s = ureg.second
    l = ureg.liter
    watt = ureg.watt
    kg = ureg.kg
    UNIT_CONVERSION_FACTOR = 3600

    def __init__(self, color:str ="red", diameter: float = 0.5, pressure: float = 1.0, temperature: float = 293.15,
                 c_p: float = 4.18,
                 m_dot: float = 0.6, g:float = 9.81, rho: float =  1000, f:float = 0.02, v_mittel:float =0.5,
                 v_max:float =3, p_max:float = 10, kin_visco: float = 1.0*10**-6,
                 delta_T: int = 20):
        self.diameter = diameter
        self.pressure = pressure
        self.temperature = temperature
        self.m_dot = m_dot
        self.color = color

        self.g = g
        self.rho = rho
        self.f =  f
        self.v_max = v_max  # maximale Fließgeschwindigkeit (in m/s)
        self.p_max = p_max  # maximale Druckbelastung des Rohrs (i#
        self.c_p = c_p
        self.delta_T = delta_T
        self.v_mittel = v_mittel
        self.kin_visco = kin_visco



    def nearest_neighbour_edge(self, G, node,  type_name, direction, circulation_direction:str = "forward", tol_value: float = 0, **kwargs):
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
                # or data["type"] == "source"
                continue
            if neighbor != node:
                neighbor_pos = data["pos"]
                if abs(node_pos[0] - neighbor_pos[0]) <= tol_value or abs(node_pos[1] - neighbor_pos[1]) <= tol_value or abs(
                        node_pos[2] - neighbor_pos[2]) <= tol_value:
                    if "direction_flow" in G.nodes[node]:
                        pass
                        """if G.nodes[node]["direction_flow"] == "x" and direction == "x":
                            if (neighbor_pos[0] - node_pos[0]) < 0 and abs(neighbor_pos[1] - node_pos[1])  <= tol_value and abs(neighbor_pos[2] - node_pos[2]) <= tol_value:
                                pos_neighbors.append(neighbor)
                            if (neighbor_pos[0] - node_pos[0]) > 0 and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and abs(neighbor_pos[2] - node_pos[2]) <= tol_value:
                                neg_neighbors.append(neighbor)
                        if G.nodes[node]["direction_flow"] == "y" and direction == "y":
                            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and (neighbor_pos[1] - node_pos[1]) < 0 and abs(neighbor_pos[2] - node_pos[2]) <= tol_value:
                                pos_neighbors.append(neighbor)
                            if abs(neighbor_pos[0] - node_pos[0]) <=tol_value and (neighbor_pos[1] - node_pos[1]) > 0 and abs(neighbor_pos[2] - node_pos[2]) <= tol_value:
                                neg_neighbors.append(neighbor)
                        if G.nodes[node]["direction_flow"] == "z" and direction == "z":
                            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and (neighbor_pos[2] - node_pos[2])<0:
                                pos_neighbors.append(neighbor)
                            if abs(neighbor_pos[0] - node_pos[0]) <= tol_value and abs(neighbor_pos[1] - node_pos[1]) <= tol_value and (neighbor_pos[2] - node_pos[2]) >0:
                                neg_neighbors.append(neighbor)"""
                    else:
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
            if nearest_neighbour is not None:
                G.add_edge(node, nearest_neighbour, color=self.color, type=type_name, circulation_direction=circulation_direction,  direction=direction, weight=abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos)))
        if neg_neighbors:
            nearest_neighbour = sorted(neg_neighbors, key=lambda p: distance.euclidean(G.nodes[p]["pos"], node_pos))[0]
            length = abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos))
            if nearest_neighbour is not None:
                G.add_edge(node, nearest_neighbour, color=self.color, type=type_name, circulation_direction=circulation_direction, direction=direction,    weight=abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos)))
        return G

    def calculate_pressure_lost(self, length, diameter):
        """
        f * (rho * v**2) / (2 * D * g)

        Args:
            length ():

        Returns:

        """
        return self.f * (self.rho * self.v_max**2) * length / (2 * diameter * self.g)



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
        point = Point(point)
        x_lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges if y1 == y2 and z1 == z2 and z1 == point.z]
        y_lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges if x1 == x2 and z1 == z2 and z1 == point.z]
        z_lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges if x1 == x2 and y1 == y2 and z1 == point.z]
        nearest_x_line = min(x_lines, key=lambda line: line.distance(point)) if x_lines else None
        nearest_y_line = min(y_lines, key=lambda line: line.distance(point)) if y_lines else None
        nearest_z_line = min(z_lines, key=lambda line: line.distance(point)) if z_lines else None
        new_node_x = None
        new_node_y = None
        new_node_z = None
        nearest_edges_x = None
        nearest_edges_y = None
        nearest_edges_z = None
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
        return new_node_x, new_node_y, new_node_z, nearest_edges_x, nearest_edges_y,  nearest_edges_z


    def add_rise_tube(self, G, circulation_direction:str = "forward"):
        for node, data in G.nodes(data=True):
            if G.nodes[node]["type"] == "source":
                self.nearest_neighbour_edge(G=G, node=node, type_name="rise_tube", direction="z", circulation_direction=circulation_direction)
        return G


    def snapping(self, G, no_path_list, circulation_direction):
        node_list = []
        edge_list = self.get_room_edges(G=G)
        for node in no_path_list:
            point = G.nodes[node]["pos"]
            new_node_x, new_node_y, new_node_z, nearest_edge_x, nearest_edge_y, nearest_edge_z = self.nearest_edges(point, edge_list)
            if self.add_node_if_not_exists(G, new_node_x) is False:
                if new_node_x is not None:
                    node_id = f"{node}_x_space"
                    G.add_node(node_id, pos=new_node_x, type="room", circulation_direction=circulation_direction)
                    node_list.append(node_id)
            if self.add_node_if_not_exists(G, new_node_y) is False:
                if new_node_y is not None:
                    node_id = f"{node}_y_space"
                    G.add_node(node_id, pos=new_node_y, type="room", circulation_direction=circulation_direction)
                    node_list.append(node_id)
            if self.add_node_if_not_exists(G, new_node_z) is False:
                if new_node_z is not None:
                    node_id = f"{node}_z_space"
                    G.add_node(node_id, pos=new_node_z, type="room", circulation_direction=circulation_direction)
                    node_list.append(node_id)
            node_list.append(node)
        for nodes in node_list:
            G = self.nearest_neighbour_edge(G=G, node=nodes, type_name="connection", direction="x", circulation_direction=circulation_direction,
                                            tol_value=0.0)
            G = self.nearest_neighbour_edge(G=G, node=nodes, type_name="connection", direction="y", circulation_direction=circulation_direction,
                                            tol_value=0.0)
            G = self.nearest_neighbour_edge(G=G, node=nodes, type_name="connection", direction="z", circulation_direction=circulation_direction,
                                            tol_value=0.0)
        return G

    def remove_edge_overlap(self, G, circulation_direction):
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
        G = nx.Graph(frozen_graph)
        # todo: Richtung angeben. sollte ja innerhalb des Gebäudes bleiben
        # todo: KOMponenten sollten nicht auf der gebäudelinie liege
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
        #G = self.remove_edge_overlap(G, circulation_direction=circulation_direction)  # check if edges are overlapping, if build point in intersection and remove the old egdes and build new
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

    def is_node_on_path(self, G,node,  type: str = None):
        """
        Args:
            G ():
            circulation_direction ():
        Returns:
        """
        if G.nodes[node]["type"] == type or type is None:
            for node_2 in G.nodes():
                if node != node_2:
                    path = nx.has_path(G, source=node, target=node_2)
                    if path is False:
                        return False
        return True

    def get_room_edges(self, G):
        """

        Args:
            G ():

        Returns:

        """
        edge_list = []
        for edge in G.edges(data=True):
            if G.nodes[edge[0]]["type"] == "radiator" or G.nodes[edge[1]]["type"] == "radiator":
                continue
            if G.get_edge_data(edge[0], edge[1])["type"] == "room":
                edge_list.append((G.nodes[edge[0]]["pos"], (G.nodes[edge[1]]["pos"])))
        return edge_list

    def add_missing_edges(self, G, type_node: str = None, circulation_direction:str = "forward"):
        """

        Args:
            G ():
            type_node ():
            circulation_direction ():

        Returns:

        """
        no_path_list = []
        for node in G.nodes():
            if self.is_node_on_path(G=G, node=node, type=type_node) is False:
                no_path_list.append(node)
        if len(no_path_list) > 0:
            G = self.snapping(G=G, no_path_list=no_path_list, circulation_direction=circulation_direction)
        return G

    def create_edges(self, G,node_list,  type_name, circulation_direction, direction_x: bool = True , direction_y:bool = True, direction_z: bool= True, tol_value:float = 0.0):
        """

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

    def create_nodes(self, G , points,circulation_direction, type_node,  **kwargs):
        """

        Args:
            G ():
            points ():
            circulation_direction ():
            type_node ():
            **kwargs ():

        Returns:

        """
        node_list = []
        for i, p in enumerate(points):
            G.add_node(f"{circulation_direction}_{type_node}_{i}", pos=p, color=self.color,  type=type_node, power=1000, circulation_direction=circulation_direction)
            node_list.append(f"{circulation_direction}_{type_node}_{i}")
        return G, node_list

    def create_nx_network(self, G, points, edge_name, circulation_direction, type_node,  direction_x: bool = True , direction_y:bool = True, direction_z: bool= True, **kwargs):
        """
        Args:
            G ():
            points ():
            circulation_direction ():
            type_node ():
            **args ():
        Returns:
        """
        G, node_list = self.create_nodes(G=G, points=points, circulation_direction=circulation_direction, type_node=type_node, **kwargs)

        G = self.create_edges(G=G, node_list=node_list,   type_name=edge_name, circulation_direction=circulation_direction, tol_value=0.0, direction_x=direction_x, direction_y=direction_y, direction_z=direction_z)
        G = self.add_missing_edges(G=G, type_node=type_node,   circulation_direction=circulation_direction)  # Check if all points are connected, if not add new node from the nearest exisiting edge and connect
        G = self.remove_edge_overlap(G, circulation_direction=circulation_direction)  # check if edges are overlapping, if build point in intersection and remove the old egdes and build new
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
        ax.scatter(*node_xyz.T, s=100, ec="w")
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
        ax.scatter(*node_xyz.T, s=100, ec="w")
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
        # todo: Eimheitenchecker
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
                        print(path[i])
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



class PipeSystem(object):


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
    # todo : unit checker mit einbauen
    # todo: Kanten Kollision vermeiden
    # todo; wenn punkt nicht auf z achse liegt mit kanten gibt priobleme oder wenn Punkte hintereinander liegen
    # todo: Komponenten vor Radiator legen, Komponenten nach Source legen
    # todo: Load graph from networkx in pandapipes
    # todo: Steigrohre zusätzlich gewichten
    # todo: Create graph in pandapipes mit Pumpe, Valve, Heat Exchange,
    # todo : Bestimme Leistung P = Q * delta_p / eta
    # todo: Bestimmte Druckunterschiede MIt PANDAPIPES
    # todo : Welche Informationen sollte die Knonten bekommen: R
    # todo: direction_flow für radiator einbauen
    # todo: Zusätzliche punkte einzeichen, damit radiatoren auch erreicht werden können, falls nicht
    # todo: Steigrohr und steiner baum pro etage iterrieren
    # todo: Forward und backward zusammenschließen
    calc = Calc_pipes(diameter=0.5, pressure=1.0, temperature=293.15, color="red")
    start_point = ((0, 0, 0), (0, 0, 5))
    path_points = ((0, 0, 0) , (0 ,0 ,5), (0, 4, 0), (0, 4, 5), (4, 4, 0), (4, 4, 5), (4,0,0), (4,0,5), (0,0,10) , (4,4,10), (0,4,10), (4, 0, 10))
    end_points = ((1.5, 5, 0), (0, 6, 0), (4, 3, 0), (2, 5, 0), (1, 6, 0), (4, 3, 5), (2, 5, 5), (1, 6, 5) ,  (0.5, 5, 0))
    floor_list = [0, 5]
    # Building Geometry



    G = nx.Graph(circulation_direction="building")
    G = calc.create_nx_network(G=G, edge_name="room", points=path_points,  circulation_direction="building",  type_node="space")

    #todo: Forwards
    fs = nx.Graph(circulation_direction="forward")
    fs = calc.create_nx_network(G=fs, edge_name="room",  points=path_points, circulation_direction="building", type_node="space")
    fs = calc.create_nx_network(G=fs, edge_name="pipe",  points=start_point, circulation_direction="forward", type_node="source", direction_z=False)  # Add Source
    fs = calc.create_nx_network(G=fs, edge_name="pipe",  points=end_points,  circulation_direction="forward", type_node="radiator", direction_z=False)   # Add radiators
    ff_graph_list = []
    for height in floor_list:
        f_st = calc.steiner_tree(fs, circulation_direction="forward", floor_height=height)
        ff_graph_list.append(f_st)
    fs = calc.add_graphs(graph_list=ff_graph_list)
    fs = calc.add_rise_tube(G=fs, circulation_direction="forward")
    fs = calc.add_component_nodes(frozen_graph=fs, circulation_direction="forward")
    fs = calc.remove_edges(G=fs)
    fs = calc.directed_graph(G=fs)
    fb = calc.create_backward(G=fs)
    heating_circle = calc.add_graphs(graph_list=[fs, fb])
    #pressure_lost = self.calculate_pressure_lost(D=D, length=length)
    #  Q_H=Q_H, D=self.calculate_diameter(Q_H=Q_H, length=length, delta_p=pressure_lost),
    # pressure_lost=pressure_lost,
    # pressure_lost=self.calculate_pressure_lost(length=abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos)))
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
    """
    # todo: Vorkalkulation
    print(heating_circle)
    # Start
    Q_H_max = 20 # [kW]
    m_dot_ges = calc.calculate_m_dot(Q_H=Q_H_max)
    diameter = calc.calculate_diameter_DIN_EN_12828(Q_H=Q_H_max)
    diameter = calc.calculate_diameter_VDI_2035(Q_H=Q_H_max)
    heating_circle.nodes["forward_source_0"]["mass_flow"] = round(m_dot_ges, 2)
    heating_circle.nodes["forward_source_0"]["diameter"] = round(diameter, 2)

    print(heating_circle.nodes(data=True))

    #for node in heating_circle.nodes(data=True)

    for u, v, data in G.edges(data=True):
        # 1. Massenstrom, Temperatur, Druck (Anfangs und Endpunkten) Ein Rohr: Δp = (128 * η * L * Q) / (π * d^4 * ρ)
        # 2. d (massenstrom, delta_p, l, v): d = (8 * Q * f * L) / (π^2 * Δp * ρ), Q = A * v = A * (volumetrische Durchflussrate) = (π * d^2 / 4) * v = (π * d^2 / 4) * (Q / A) = (π * d^2 / 4) * (2 * Δp / (ρ * v)^2)
        # 3. delta_P (d, l v, fluid)
        # 4. Massenstrom (d, delta_p) v = Q / A = (4 * Q) / (π * d^2)
        # 5. Iteration durchlaufen lassen -> Prüfen Δp = (ρ * v^2 / 2) * (1 - (A2 / A1)^2)

        """flow_rate = data['flow_rate']
        velocity = 1.5  # Beispielgeschwindigkeit
        diameter = calc.calculate_diameter(Q_H=Q_H, delta_p=delta_p, length=length)
        pressure_lost = calc.calculate_pressure_lost(flow_rate, diameter, 100, 0.01)

        # Füge berechnete Attribute hinzu
        data['diameter'] = diameter
        data['pressure_lost'] = pressure_lost"""
        #G.edges[u, v]['diameter'] = diameter
        #G.edges[u, v]['pressure_lost'] = pressure_lost

    calc.visulize_networkx(G=fs)
    calc.visualzation_networkx_3D(G=G, minimum_trees=[fs])
    calc.visualzation_networkx_3D(G=G, minimum_trees=[fb])
    calc.visualzation_networkx_3D(G=G, minimum_trees=[fs, fb])
    calc.visualzation_networkx_3D(G=G, minimum_trees=[heating_circle])

    plt.show()


    #net = calc.create_networkx_junctions(G=mst)

    #calc.test_lindemayer()
    # calc._get_attributes(net=net)

    # net = calc.test_pipe(start_point=start_point, end_points=end_points, path_point=mst.edges)
    # net = calc.empty_network()
    # net = calc.create_source(net=net, start=list(mst.nodes())[0])
    # net = calc.create_pump(net=net, start=list(mst.nodes())[0])
    # calc.create_sink(net=net, end_points=end_points)


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


