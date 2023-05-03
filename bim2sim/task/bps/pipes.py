import pandapipes as pp
import networkx as nx
import pandapipes.plotting as plot
import matplotlib.pyplot as plt
import numpy as np
from openalea.plantgl.math import direction
from pandapipes.component_models import Pipe
import pandapipes.networks
import math
import random
from scipy.spatial.distance import cdist
from scipy.spatial import distance
from shapely.geometry import Polygon, Point
from shapely.geometry import Point, LineString

class Calc_pipes():


    def __init__(self, color:str ="red", diameter: float = 0.5, pressure: float = 1.0, temperature: float = 293.15, m_dot: float = 0.6):
        self.diameter = diameter
        self.pressure = pressure
        self.temperature = temperature
        self.m_dot = m_dot
        self.color = color

    def nearest_neighbour_edge(self, G, node,  type_name, direction, circulation_direction:str = "forward", tol_value: float = 0):
        """
        Args:
            G ():
            node ():
            direction ():
            circulation_direction ():
            tol_value ():
        Returns:
        """
        # todo: Beschränkung einführen: Radiatoren nicht dreitk miteinander verbinden
        # todo: mit flow direction nochmal überdenken. Besser wenn ich das mit einem gerichteten grafen mache
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
                G.add_edge(node, nearest_neighbour, color=self.color, type=type_name, circulation_direction=circulation_direction, direction=direction, weight=abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos)))
        if neg_neighbors:
            nearest_neighbour = sorted(neg_neighbors, key=lambda p: distance.euclidean(G.nodes[p]["pos"], node_pos))[0]
            if nearest_neighbour is not None:
                G.add_edge(node, nearest_neighbour, color=self.color, type=type_name, circulation_direction=circulation_direction, direction=direction,
                           weight=abs(distance.euclidean(G.nodes[nearest_neighbour]["pos"], node_pos)))
        return G

    def nearest_edge(self, point, edges):
        # todo: in jeder suchrichtung suchen und kanten vermeiden auf denen am endpunkt ein radiator liegt
        point = Point(point)
        lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges]
        nearest_line = min(lines, key=lambda line: line.distance(point))
        nearest_point = nearest_line.interpolate(nearest_line.project(point))
        new_node = (nearest_point.x, nearest_point.y, nearest_point.z)
        return new_node, (nearest_line.coords[0], nearest_line.coords[-1])

    def nearest_edges(self, point, edges):
        # todo: nur auf die Raumgeometrie beziehen?
        point = Point(point)


        x_lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges if y1 == y2 and z1 == z2 and z1 == point.z]
        y_lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges if x1 == x2 and z1 == z2 and z1 == point.z]
        z_lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges if x1 == x2 and y1 == y2 and z1 == point.z]
        #x_lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges if x1 == x2]
        #y_lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges if y1 == y2]
        #z_lines = [LineString([(x1, y1, z1), (x2, y2, z2)]) for ((x1, y1, z1), (x2, y2, z2)) in edges if z1 == z2]
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

    def remove_edges(self):
        pass

    def add_component_nodes(self, frozen_graph, circulation_direction: str = "forward"):
        #G = nx.Graph(circulation_direction=circulation_direction)
        G = nx.Graph(frozen_graph)
        # todo: Richtung angeben. sollte ja innerhalb des Gebäudes bleiben
        # todo: KOMponenten sollten nicht auf der gebäudelinie liege
        radiator_dict = {}
        source_dict = {}
        source_nodes = None
        radiator_nodes = None
        """for node, data in frozen_graph.nodes(data=True):
            G.add_node(node, **data)"""
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
                    #G = self.nearest_neighbour_edge(G=G, node=node, direction="x", circulation_direction=circulation_direction)
                    G = self.nearest_neighbour_edge(G=G, type_name="pipe",node=node, direction="y",  circulation_direction=circulation_direction)



        #G = self.remove_edge_overlap(G, circulation_direction=circulation_direction)  # check if edges are overlapping, if build point in intersection and remove the old egdes and build new

        return G

    def create_undirected_network(self, G):
        H = nx.Graph()
        # Konvertieren der gerichteten Kanten in ungerichtete Kanten
        for u, v, data in G.edges(data=True):
            weight = data['weight']
            H.add_edge(u, v, weight=weight)
            H.add_edge(v, u, weight=weight*2)
        return H

    def add_node_if_not_exists(self, G, point):
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
        edge_list = []
        for edge in G.edges(data=True):
            if G.nodes[edge[0]]["type"] == "radiator" or G.nodes[edge[1]]["type"] == "radiator":
                continue
            if G.get_edge_data(edge[0], edge[1])["type"] == "room":
                edge_list.append((G.nodes[edge[0]]["pos"], (G.nodes[edge[1]]["pos"])))
        return edge_list

    def add_missing_edges(self, G, type_node: str = None, circulation_direction:str = "forward"):
        no_path_list = []
        for node in G.nodes():
            if self.is_node_on_path(G=G, node=node, type=type_node) is False:
                no_path_list.append(node)
        if len(no_path_list) > 0:
            G = self.snapping(G=G, no_path_list=no_path_list, circulation_direction=circulation_direction)
        return G

    def create_edges(self, G,node_list,  type_name, circulation_direction, direction_x: bool = True , direction_y:bool = True, direction_z: bool= True, tol_value:float = 0.0):
        for node in node_list:
            if direction_x is True:
                G = self.nearest_neighbour_edge(G=G, type_name=type_name, node=node,  direction="x", circulation_direction=circulation_direction, tol_value=tol_value)
            if direction_y is True:
                G = self.nearest_neighbour_edge(G=G, type_name=type_name, node=node,  direction="y", circulation_direction=circulation_direction, tol_value=tol_value)
            if direction_z is True:
                G = self.nearest_neighbour_edge(G=G, type_name=type_name,  node=node, direction="z", circulation_direction=circulation_direction, tol_value=tol_value)
        return G

    def create_nodes(self, G , points,circulation_direction, type_node,  **kwargs):
        node_list = []
        for i, p in enumerate(points):
            G.add_node(f"{circulation_direction}_{type_node}_{i}", pos=p, color=self.color,  type=type_node, power=1000, circulation_direction=circulation_direction)
            node_list.append(f"{circulation_direction}_{type_node}_{i}")
        return G, node_list

    def create_nx_network(self, G, points, edge_name, circulation_direction, type_node,  direction_x: bool = True , direction_y:bool = True, direction_z: bool= True):
        """
        Args:
            G ():
            points ():
            circulation_direction ():
            type_node ():
            **args ():
        Returns:
        """
        G, node_list = self.create_nodes(G=G, points=points, circulation_direction=circulation_direction, type_node=type_node)
        G = self.create_edges(G=G, node_list=node_list,   type_name=edge_name, circulation_direction=circulation_direction, tol_value=0.0, direction_x=direction_x, direction_y=direction_y, direction_z=direction_z)
        G = self.add_missing_edges(G=G, type_node=type_node,   circulation_direction=circulation_direction)  # Check if all points are connected, if not add new node from the nearest exisiting edge and connect
        G = self.remove_edge_overlap(G, circulation_direction=circulation_direction)  # check if edges are overlapping, if build point in intersection and remove the old egdes and build new
        return G


    def visulize_networkx(self, G):
        """
            [[[0.2 4.2 0.2]
            [0.2 0.2 0.2]]
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
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")

        node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values()))
        edge_xyz = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos']) for u, v in G.edges()])
        ax.scatter(*node_xyz.T, s=100, ec="w")
        for vizedge in edge_xyz:
            ax.plot(*vizedge.T, color="tab:gray")
        for minimum_tree in minimum_trees:
            #node_xyz = np.array(sorted(nx.get_node_attributes(minimum_tree, "pos").values()))
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
        # todo pro etage + dann steigrohr + dann nächste etage
        term_points = sorted([n for n, data in graph.nodes(data=True) if data["type"] in {"radiator", "source"} and data["pos"][2] == floor_height])
        steinerbaum = nx.algorithms.approximation.steinertree.steiner_tree(graph, term_points, method="kou")
        total_weight = sum([edge[2]['weight'] for edge in steinerbaum.edges(data=True)])
        print(f"Steiner Tree: {circulation_direction} {total_weight}")
        steinerbaum.graph["circulation_direction"] = circulation_direction
        return steinerbaum

    def spanning_tree(self, graph: nx.DiGraph(), start, end_points):
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


    def draw_l_system(self, turtle, axiom, angle, distance):
        stack = []
        for char in axiom:
            if char == 'F':
                turtle.forward(distance)
            elif char == '+':
                turtle.right(angle)
            elif char == '-':
                turtle.left(angle)
            elif char == '[':
                stack.append((turtle.position(), turtle.heading()))
            elif char == ']':
                position, heading = stack.pop()
                turtle.penup()
                turtle.goto(position)
                turtle.setheading(heading)
                turtle.pendown()


    def test_lindemayer(self):
        import networkx as nx

        # Erstellen des Graphen
        G = nx.Graph()
        G.add_nodes_from([(0, 1), (0, 3), (0, 4)])
        G.add_edges_from([((0, 1), (0, 3)), ((0, 3), (0, 4))])

        # Identifizieren des Anfangsknotens und der Kante
        start_node = (0, 1)
        edge = (start_node, (0, 3))
        # Teilen der Kante in drei Abschnitte
        start_pos = G.nodes[start_node]['pos']
        end_pos = G.nodes[(0, 3)]['pos']
        section_length = (end_pos[0] - start_pos[0]) / 3

        section1_pos = (start_pos[0] + section_length, start_pos[1])
        section2_pos = (start_pos[0] + 2 * section_length, start_pos[1])

        # Hinzufügen der neuen Knoten für die drei Komponenten
        comp1_node = (0, 2)
        G.add_node(comp1_node, pos=section1_pos, comp_type='Kessel')
        comp2_node = (0, 3)
        G.add_node(comp2_node, pos=section2_pos, comp_type='Rohr')
        comp3_node = (0, 4)
        G.add_node(comp3_node, pos=end_pos, comp_type='Pumpe')

        # Aktualisieren der Kanten
        G.remove_edge(*edge)
        G.add_edges_from([(start_node, comp1_node), (comp1_node, comp2_node),
                          (comp2_node, comp3_node), (comp3_node, (0, 4))])

        # Hinzufügen der Kanten für den erweiterten Anfangsknoten
        G.add_edges_from([(start_node, comp1_node), (start_node, comp2_node),
                          (start_node, comp3_node)])

        # Ausgabe des Graphen
        # Erstelle Graph
        G = nx.Graph()

        # Erstelle Anfangsknoten mit Komponentenattributen
        G.add_node(0, heat_exchanger=True, pumpe=True, rohr=True)

        # Erstelle Entknoten mit Attributen für Ventil, Pumpe und Radiator
        G.add_node(1, ventil=True)
        G.add_node(2, pumpe=True)
        G.add_node(3, radiator=True)

        # Füge Kanten zwischen den Knoten hinzu
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        G.add_edge(2, 3)

        # Wende den Lindenmayer-Algorithmus an, um eine Zeichenkette zu erzeugen
        start = 'H'
        rules = {
            'H': 'HPH',
            'P': 'P',
            'R': 'R',
        }
        depth = 1
        final_string = self.apply_rules(start, rules, depth)
        # Konvertiere die Zeichenkette in ein Netzwerk
        current_node = 0
        for char in final_string:
            if char == 'H':
                next_node = G.number_of_nodes()
                G.add_node(next_node, heat_exchanger=True, rohr=True, pumpe=True)
                G.add_edge(current_node, next_node)
                current_node = next_node
            elif char == 'P':
                next_node = G.number_of_nodes()
                G.add_node(next_node, pumpe=True)
                G.add_edge(current_node, next_node)
                current_node = next_node
            elif char == 'R':
                next_node = G.number_of_nodes()
                G.add_node(next_node, rohr=True)
                G.add_edge(current_node, next_node)
                current_node = next_node

    def apply_rules(self, axiom, rules, depth):
        for i in range(depth):
            new_axiom = ''
            for char in axiom:
                new_axiom += rules.get(char, char)
            axiom = new_axiom
        return axiom



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

    def calculate_diameter(self, Q_H: float, alpha: float = 0.25, delta_T: int = 50):
        """
        Q_H = alpha *pi * (d**2 / 4) * delta_T
        """
        return math.sqrt(4 * Q_H/(alpha * delta_T * math.pi))

    def calculate_m_dot(self, Q_H: float, c_p: float = 4.18, delta_T: int = 50):
        """
        Q_H = m_dot * c_p * delta_T
        """
        return Q_H / (c_p * delta_T)

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
        D = nx.DiGraph()
        for node, data in G.nodes(data=True):
            D.add_node(node, **data)
        for u, v in G.edges():
            D.add_edge(u, v)
        for u, v, data in G.edges(data=True):
            D.add_edge(u, v, **data)
        pos = nx.spring_layout(G, dim=3)
        # Initialisierung des 3D-Plots
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        for n in G.nodes():
            ax.scatter(pos[n][0], pos[n][1], pos[n][2], c='b')

        # Zeichnen der Kanten als Pfeile
        for u, v, d in G.edges(data=True):
            print(pos[v])
            arrowprops = dict(arrowstyle="->", color=d['color'], linewidth=1.5, mutation_scale=10)
            ax.annotate("", pos[v], pos[u], arrowprops=arrowprops)

        # Festlegen der Achsenbeschriftungen
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')

        # Anzeigen des Plots
        plt.show()

        """ pos = nx.spring_layout(G)
        # Erstellen eines leeren Listen-Objekts für die Kantenfarben
        edge_colors = []
        # Schleife über alle Kanten
        for u, v, data in G.edges(data=True):
            # Abrufen der Ausrichtung der Kante
            circulation_direction = data['circulation_direction']
            direction = data['direction']

            # Festlegen der Farbe basierend auf der Kanten-Ausrichtung
            if circulation_direction == 'forward':
                if direction == 'x':
                    edge_colors.append('red')
                else:
                    edge_colors.append('blue')
            else:
                if direction == 'x':
                    edge_colors.append('green')
                else:
                    edge_colors.append('orange')

        # Zeichnen des gerichteten Graphen mit eingefärbten Kanten
        fig, ax = plt.subplots()
        nx.draw_networkx_nodes(G, pos)
        nx.draw_networkx_edges(G, pos, edge_color=edge_colors)
        plt.axis('off')
        plt.show()"""
        return D

class PipeSystem(object):
    def __init__(self,G):
        self.G = G

    def create_empty_network(self):
        pass

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
    calc.visulize_networkx(G=fs)
    calc.visualzation_networkx_3D(G=G, minimum_trees=[fs])
    D = calc.directed_graph(G=fs)


    #calc.visualzation_networkx_3D(G=G, minimum_trees=[D])
    #todo:  Backwars
    """calc = Calc_pipes(diameter=0.5, pressure=1.0, temperature=293.15, color="blue")
    b_start, b_path_points, b_end_points = calc.add_offset(offset=0.1, start_p=start_point, end_p=end_points, path_p=path_points)
    fb = nx.Graph(circulation_direction="forward")
    fb = calc.create_nx_network(G=fb, edge_name="room",  points=b_path_points, circulation_direction="building", type_node="space")
    fb = calc.create_nx_network(G=fb, edge_name="pipe",  points=b_start, circulation_direction="backward", type_node="source", direction_z=False)  # Add Source
    fb = calc.create_nx_network(G=fb, edge_name="pipe", points=b_end_points, circulation_direction="backward", type_node="radiator", direction_z=False)  # Add radiators
    bw_graph_list = []
    for height in floor_list:
        f_b = calc.steiner_tree(fb, circulation_direction="backward", floor_height=height)
        bw_graph_list.append(f_b)
    fb = calc.add_graphs(graph_list=bw_graph_list)
    fb = calc.add_rise_tube(G=fb, circulation_direction="backward")
    fb = calc.add_component_nodes(frozen_graph=fb, circulation_direction="backward")
    print(fb)
    #calc.visualzation_networkx_3D(G=G, minimum_trees=[fb])
    #calc.visualzation_networkx_3D(G=G, minimum_trees=[fb,fs])
    full_graph = calc.add_graphs(graph_list=[fb, fs])
    calc.visualzation_networkx_3D(G=G, minimum_trees=[full_graph])"""
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


