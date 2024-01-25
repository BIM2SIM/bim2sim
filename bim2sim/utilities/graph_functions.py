import json
import bim2sim
import networkx as nx
from networkx.algorithms.components import is_strongly_connected
from networkx.readwrite import json_graph

from pathlib import Path
from scipy.spatial import distance
from shapely.ops import nearest_points
from shapely.geometry import Polygon, Point, LineString
import numpy as np
from bim2sim.elements.bps_elements import ThermalZone, Door, Wall, Window, OuterWall, Floor
import matplotlib.pyplot as plt
import logging

logger = logging.getLogger(__name__)


def lay_direction(verts: tuple) -> str:
    x_coords = [point[0] for point in verts]
    y_coords = [point[1] for point in verts]
    x_diff = np.max(x_coords) - np.min(x_coords)
    y_diff = np.max(y_coords) - np.min(y_coords)
    if x_diff > y_diff:
        direction = "x"
    else:
        direction = "y"
    return direction


def sort_edge_direction(graph: nx.Graph() or nx.DiGraph(),
                        working_node_dict: dict,
                        directions: list = None,
                        tol_value: float = 0.0) -> tuple[dict, dict]:
    """

    Args:
        graph (): nx.Graph()
        working_node_dict (): A sorted dictionary where each key is a node and its values are possible nodes that can be connected to the node.
        directions (): Specification of the direction in which edges can be placed: [x,y,z]. Should I lay all directions [True, True, True].
        tol_value (): Tollerized deviations from the position of the node.
    return:
        pos_neighbors {}: Creates a dictionary where each key is a node. Its values are sorted by x,y or z  in positive direction.
        neg_neighbors {}: Creates a dictionary where each key is a node. Its values are sorted by x,y or z  in negative direction.
    """
    directions = directions or [True, True, True]
    pos_neighbors, neg_neighbors = {}, {}
    for node in working_node_dict:
        pos_neighbors.setdefault(node, {})
        neg_neighbors.setdefault(node, {})
        for neighbor_node in working_node_dict[node]:
            neighbor_pos = tuple(round(coord, 2) for coord in graph.nodes[neighbor_node]["pos"])
            node_pos = tuple(round(coord, 2) for coord in graph.nodes[node]["pos"])
            for i, direction in enumerate(["x", "y", "z"]):
                if directions[i]:
                    diff = neighbor_pos[i] - node_pos[i]
                    if diff < 0 and all(abs(neighbor_pos[j] - node_pos[j]) <= tol_value for j in range(3) if j != i):
                        pos_neighbors[node].setdefault(direction, []).append(neighbor_node)
                    elif diff > 0 and all(abs(neighbor_pos[j] - node_pos[j]) <= tol_value for j in range(3) if j != i):
                        neg_neighbors[node].setdefault(direction, []).append(neighbor_node)
    return neg_neighbors, pos_neighbors


def sort_connect_nodes(graph: nx.Graph() or nx.DiGraph(),
                       connect_nodes: list = None,
                       element_types: list = None,
                       connect_node_flag: bool = False,
                       to_connect_node_list: list = None,
                       same_ID_element_flag: bool = False,
                       element_types_flag: bool = False,
                       ) -> dict:
    """
    Searches nodes for a transferred node according to different requirement criteria.
    Args:
        graph (): nx.Graph()
        connect_nodes (): List of existing nodes that are to be connected to other nodes via edges.
        element_types ():
        element_types_flag ():
        connect_node_flag ():
        to_connect_node_list ():
        same_ID_element_flag (): Searches for all nodes in the graph that have the same "ID_Element" attribute.
    Returns:
        working_connection_nodes (): Outputs a sorted dictionary. Each key is a node and its values are matching nodes that fulfill certain requirement criteria.
    """
    # todo: Kürzen und doku erweitern
    working_connection_nodes = {}
    if connect_nodes is not None and len(connect_nodes) > 0:
        # Sucht passende Knoten aus
        for working_node in connect_nodes:
            if working_node not in working_connection_nodes:
                working_connection_nodes[working_node] = []
            # Sucht passende Knoten aus der Knotenliste für ein orthogonales Koordinatensystem
            if connect_node_flag and to_connect_node_list is not None:
                for connect_node in to_connect_node_list:
                    if connect_node != working_node:
                        working_connection_nodes[working_node].append(connect_node)
            # Sucht passende Knoten für ein orthogonales Koordinatensystem
            else:
                for neighbor, data in graph.nodes(data=True):
                    if neighbor != working_node:
                        if same_ID_element_flag:
                            if graph.nodes[working_node]["ID_element"] == data["ID_element"]:
                                working_connection_nodes[working_node].append(neighbor)
                        if element_types_flag and element_types is not None:
                            if set(element_types) & set(graph.nodes[working_node]["element_type"]) & set(data["element_type"]):
                                if graph.nodes[working_node]["ID_element"] != data["ID_element"]:
                                    working_connection_nodes[working_node].append(neighbor)

        return working_connection_nodes
    else:
        logger.error(f'No nodes to connect: {connect_nodes}.')
        exit(1)

def nearest_polygon_in_space(project_node_pos: tuple,
                             direction: str,
                             room_global_points: list,
                             floor_flag: bool = True):
    """
    Finde die nächste Raum ebene des Punktes/Knoten.
    Args:
        graph ():
        project_node_pos ():

    Returns:
    """
    point = Point(project_node_pos)
    coords = np.array(room_global_points)


    coords_x = coords[coords[:, 0].argsort()]
    coords_y = coords[coords[:, 1].argsort()]
    coords_z = coords[coords[:, 2].argsort()]
    poly_dict = {}
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
        polygon_2d = None
        if floor_flag is True and direction == "z":
            if poly == "floor":
                polygon_2d = Polygon([(point[0], point[1]) for point in Polygon(coords_z[3:]).exterior.coords])
            if poly == "roof":
                polygon_2d = Polygon([(point[0], point[1]) for point in Polygon(coords_z[:3]).exterior.coords])
            if polygon_2d is not None:
                minx, miny, maxx, maxy = polygon_2d.bounds
                if point.x >= minx and point.x <= maxx and point.y >= miny and point.y <= maxy:
                    distance_z = abs(
                        point.z - poly_dict[poly].exterior.interpolate(
                            poly_dict[poly].exterior.project(point)).z)
                    poly_list.append(poly_dict[poly])
                    poly_distance_dict[poly_dict[poly]] = distance_z
        # y-Richtung
        if direction == "y":
            if poly == "wall_x_pos":
                polygon_2d = Polygon([(point[1], point[2]) for point in Polygon(coords_x[:3]).exterior.coords])
            if poly == "wall_x_neg":
                polygon_2d = Polygon([(point[1], point[2]) for point in Polygon(coords_x[3:]).exterior.coords])
            if polygon_2d is not None:
                miny, minz, maxy, maxz = polygon_2d.bounds
                if point.y >= miny and point.y <= maxy and point.z >= minz and point.z <= maxz:
                    distance_x = abs(
                        point.x - poly_dict[poly].exterior.interpolate(poly_dict[poly].exterior.project(point)).x)
                    poly_list.append(poly_dict[poly])
                    poly_distance_dict[poly_dict[poly]] = distance_x
        # X-Richtung
        if direction == "x":
            if poly == "wall_y_pos":
                polygon_2d = Polygon([(point[0], point[2]) for point in Polygon(coords_y[:4]).exterior.coords])
            if poly == "wall_y_neg":
                polygon_2d = Polygon([(point[0], point[2]) for point in Polygon(coords_y[4:]).exterior.coords])
            if polygon_2d is not None:
                minx, minz, maxx, maxz = polygon_2d.bounds
                if point.x >= minx and point.x <= maxx and point.z >= minz and point.z <= maxz:
                    distance_y = abs(
                        point.y - poly_dict[poly].exterior.interpolate(poly_dict[poly].exterior.project(point)).y)
                    poly_list.append(poly_dict[poly])
                    poly_distance_dict[poly_dict[poly]] = distance_y
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


def project_nodes_on_building(graph: nx.Graph(),
                              project_node_list: list,
                              element_type: list = ["IfcSpace"],
                              )  -> tuple[nx.Graph(), list]:
    """
    Projeziert Knoten die außerhalb des Gebäudes sind, auf die Gebäude Ebene und löscht den Ursprünglichen Knoten
    Args:
        graph ():
        project_node_list ():
    Returns:
    """
    room_node_list = {}
    for project_node in project_node_list:
        belongs_to_element = graph.nodes[project_node]["belongs_to_element"]
        for room_node, data in graph.nodes(data=True):
            if data["ID_element"] in belongs_to_element and set(element_type) & set(data["element_type"]):
                # room / space
                if project_node not in room_node_list:
                    room_node_list[project_node] = []
                room_node_list[project_node].append(data["pos"])

    node_list = []
    for project_node in room_node_list:
        projected_point = nearest_polygon_in_space(project_node_pos=graph.nodes[project_node]["pos"],
                                                   direction=graph.nodes[project_node]["direction"],
                                                   room_global_points=room_node_list[project_node])

        if projected_point is not None:
            graph, created_nodes = create_graph_nodes(graph,
                                   points_list=[projected_point],
                                   ID_element=graph.nodes[project_node]["ID_element"],
                                   element_type=graph.nodes[project_node]["element_type"],
                                   direction=graph.nodes[project_node]["direction"],

                                   node_type=graph.nodes[project_node]["node_type"],
                                   belongs_to_room=graph.nodes[project_node]["belongs_to_room"],
                                   belongs_to_element=graph.nodes[project_node]["belongs_to_element"],
                                   belongs_to_storey=graph.nodes[project_node]["belongs_to_storey"],
                                   update_node=True)
            node_list = list(set(node_list + created_nodes))

            if project_node not in created_nodes:
                graph.remove_node(project_node)
    return graph, node_list



def filter_edges(graph: nx.Graph(),
                 node: nx.Graph().nodes(),
                 element_type: str = "IfcSpace",
                 element_belongs_to_space: bool = False,
                 snapped_nodes_in_space: bool = False,
                 all_edges_flag: bool = False
                 ):
    """
    Args:
        graph (): Networkx Graph
        node (): Knoten, der mit dem Graphen verbunden werden soll.

    Returns:
    """
    edge_list = []
    for edge in graph.edges(data=True):
        if edge[0] != node and edge[1] != node:
            # Beachtet alle Kanten des Graphs.
            if element_belongs_to_space:
                # Kanten des Raums
                if any(obj == element_type for obj in graph.nodes[edge[0]]["element_type"] \
                                                    + graph.nodes[edge[1]]["element_type"]):
                    if all(graph.nodes[edge[i]]["ID_element"] in set(graph.nodes[node]["belongs_to_element"]) for i in
                           range(2)):
                        if (edge[0], edge[1]) not in edge_list:
                            edge_list.append((edge[0], edge[1]))
            if snapped_nodes_in_space:
                if all(set(graph.nodes[edge[i]]["belongs_to_room"]) & set(graph.nodes[node]["belongs_to_room"]) for i in
                           range(2)):
                    if (edge[0], edge[1]) not in edge_list:
                        edge_list.append((edge[0], edge[1]))
            if all_edges_flag:
                edge_list.append((edge[0], edge[1]))
    return edge_list

def kit_grid(graph: nx.Graph()):
    """

    Args:
        graph ():

    Returns:

    """
    G_connected = nx.connected_components(graph)
    G_largest_component = max(G_connected, key=len)
    G = graph.subgraph(G_largest_component)
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


def check_graph(graph: nx.Graph(),
                type:str):
    if nx.is_connected(graph) is True:
        logger.info(f"{type} Graph is connected.")
        return graph
    else:
        logger.warning(f"{type} Graph is not connected.")
        for node in graph.nodes():
            if nx.is_isolate(graph, node) is True:
                logger.warning("node", node, "is not connected." \
                               f'{graph.nodes[node]["pos"]} with type {graph.nodes[node]["node_type"]}')
        # Gib die nicht miteinander verbundenen Komponenten aus
        graph = kit_grid(graph)
        if nx.is_connected(graph) is True:
            logger.info(f" {type} Graph is connected.")
            return graph
        else:
            logger.error(f"{type} Graph is not connected.")
            exit(1)

def save_networkx_json(graph: nx.Graph(), file: Path):
    """

    Args:
        graph ():
        file ():
    """
    # todo: bisher über settings: Datei muss bisher immer vorher erst erstellt werden
    logger.info(f"Save Networkx {graph} in {file}.")
    data = json_graph.node_link_data(graph)
    with open(file, 'w') as f:
        json.dump(data, f)


def read_json_graph(json_file: Path):
    try:
        with open(json_file, "r") as file:
            json_data = json.load(file)
            G = nx.node_link_graph(json_data)
        logger.info(f"Read building graph from json-file: {json_file}" )
        return G
    except json.decoder.JSONDecodeError as e:
        logger.error(f"Error reading the JSON file {json_file}: {e}")
        exit(1)
    except FileNotFoundError as e:
        logger.error(e)
        exit(1)




def nearest_edges(graph: nx.Graph(),
                  node: nx.Graph().nodes(),

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

        z_flag (): Falls True, such auch in Z Richtung nach Kanten
        x_flag (): Falls True, such auch in X Richtung nach Kanten
        y_flag (): Falls True, such auch in Y Richtung nach Kanten
        tol_value ():
        bottom_z_flag (): Falls False, Sucht nur in negativer z richtung
        edges (): Ausgewählte Kanten für den Punkt
    Returns:
    """
    points = graph.nodes[node]["pos"]
    lines_dict = {}
    for edge in edges:
        (x1, y1, z1) = graph.nodes[edge[0]]["pos"]
        (x2, y2, z2) = graph.nodes[edge[1]]["pos"]
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



def connect_nodes_with_grid(graph: nx.Graph(),
                            node_list: list,
                            node_type: list or str = None,
                            collision_flag: bool = True,
                            bottom_z_flag: bool = False,
                            top_z_flag: bool = False,
                            pos_x_flag: bool = False,
                            neg_x_flag: bool = False,
                            pos_y_flag: bool = False,
                            neg_y_flag: bool = False,
                            element_type:str="IfcSpace",
                            color: str = "black",
                            edge_type: str = "aux_line",
                            grid_type:str = "building",
                            col_tol:float = 0.1,
                            element_belongs_to_space:bool = False,
                            all_edges_flag: bool = False,
                            snapped_nodes_in_space: bool = False,
                            neighbor_nodes_collision_type: list = ["IfcSpace", "snapped_nodes"],
                            no_neighbour_collision_flag: bool = True
                            ) -> nx.Graph():
    """
    Args:

        top_z_flag (): Falls False: Sucht nur in negativer z richtung
        graph (): Networkx Graph
        node_list (): Liste von Knoten die mit dem Graphen verbunden werden
        Suchen der Kanten, auf die ein neuer Knoten gesnappt werden kann.
    Returns:
    """
    # todo: snapped Knoten attribute überprüfen, anpassen, kürzen
    # todo: Liste mit allemen node_type, element_types. Unterscheidungen klar machen
    direction_flags = [top_z_flag, bottom_z_flag, pos_x_flag, neg_x_flag, pos_y_flag, neg_y_flag]
    for i, node in enumerate(node_list):
        node_type = node_type or graph.nodes[node]["node_type"]

        # Sucht alle Kanten, auf die ein Knoten gesnappt werden kann.
        for j, direction in enumerate(direction_flags):
            direction_flags = [top_z_flag, bottom_z_flag, pos_x_flag, neg_x_flag, pos_y_flag, neg_y_flag]
            for k, flag in enumerate(direction_flags):
                if j == k:
                    direction_flags[k] = flag
                    # Setze alle anderen Flags auf False (für jeden anderen Index k außer j)
                else:
                    direction_flags[k] = False
            # Sucht passende Kanten
            edge_list = filter_edges(graph,
                                     node=node,
                                     element_belongs_to_space=element_belongs_to_space,
                                     snapped_nodes_in_space=snapped_nodes_in_space,
                                     element_type=element_type,
                                     all_edges_flag=all_edges_flag)
            if not any(direction_flags):
                continue
            # Sucht die nächste Kante und die Position des neu erstellten Knotens
            nearest_lines, new_node_pos = nearest_edges(graph=graph,
                                                        node=node,
                                                        edges=edge_list,
                                                        top_z_flag=direction_flags[0],
                                                        bottom_z_flag=direction_flags[1],
                                                        pos_x_flag=direction_flags[2],
                                                        neg_x_flag=direction_flags[3],
                                                        pos_y_flag=direction_flags[4],
                                                        neg_y_flag=direction_flags[5])

            if new_node_pos is not None:
                if check_space_collision(graph,
                                         edge_point_A=graph.nodes[node]["pos"],
                                         edge_point_B=new_node_pos,
                                         collision_flag=collision_flag,
                                         tolerance=col_tol) is False:
                    if check_neighbour_nodes_collision(graph,
                                                       edge_point_A=graph.nodes[node]["pos"],
                                                       edge_point_B=new_node_pos,
                                                       neighbor_nodes_collision_type=neighbor_nodes_collision_type,
                                                       no_neighbour_collision_flag=no_neighbour_collision_flag) is False:
                        graph, created_nodes = create_graph_nodes(graph,
                                                   points_list=[new_node_pos],
                                                   ID_element=graph.nodes[node]["ID_element"],
                                                   element_type=f'snapped_node',
                                                   direction=graph.nodes[node]["direction"],
                                                   node_type=node_type,
                                                   belongs_to_room=graph.nodes[node]["belongs_to_room"],
                                                   belongs_to_element=graph.nodes[node]["belongs_to_element"],
                                                   belongs_to_storey=graph.nodes[node]["belongs_to_storey"])
                        if created_nodes is not None:
                            # Löscht die nächste Kante
                            if graph.has_edge(nearest_lines[0][0], nearest_lines[0][1]):
                                graph.remove_edge(nearest_lines[0][0], nearest_lines[0][1])
                            if graph.has_edge(nearest_lines[0][1], nearest_lines[0][0]):
                                graph.remove_edge(nearest_lines[0][1], nearest_lines[0][0])
                            # Verbindet gesnappten Knoten mit den Kantenknoten
                            for created_node in created_nodes:
                                if nearest_lines[0][0] != created_node:
                                    graph.add_edge(nearest_lines[0][0],
                                           created_node,
                                           color=color,
                                           edge_type=edge_type,
                                           grid_type=grid_type,
                                           direction=direction,
                                           length=abs(
                                               distance.euclidean(graph.nodes[nearest_lines[0][0]]["pos"],
                                                                  graph.nodes[created_node]["pos"])))
                                if nearest_lines[0][1] != created_node:
                                    graph.add_edge(nearest_lines[0][1],
                                           created_node,
                                           color=color,
                                           edge_type=edge_type,
                                           grid_type=grid_type,
                                           direction=direction,
                                           length=abs(
                                               distance.euclidean(graph.nodes[nearest_lines[0][1]]["pos"],
                                                                  graph.nodes[created_node]["pos"])))
                                graph.add_edge(node,
                                               created_node,
                                               color=color,
                                               edge_type=edge_type,
                                               grid_type=grid_type,
                                               direction=direction,
                                               length=abs(
                                                   distance.euclidean(graph.nodes[node]["pos"],
                                                                      graph.nodes[created_node]["pos"])))


    return graph



def add_graphs(graph_list: list,
               grid_type: str = "building"):
    """

    Args:
        graph_list ():
        grid_type (): Attribute: Type of graph

    Returns:

    """
    # Prove if graph is directed or not
    is_directed = all(G.is_directed() for G in graph_list)
    if is_directed:
        combined_graph = nx.DiGraph()
    else:
        combined_graph = nx.Graph()
    for subgraph in graph_list:
        combined_graph = nx.union(combined_graph, subgraph)
    combined_graph.graph["grid_type"] = grid_type
    return combined_graph



def connect_nodes_via_edges(graph: nx.Graph(),
                           node_neighbors: dict,
                           edge_type: str = None,
                           grid_type: str = None,
                           color: str = "black",
                           neighbor_nodes_collision_type: list = None,
                           no_neighbour_collision_flag: bool = False,
                           collision_flag: bool = False,
                           col_tol: float = 0.1) -> nx.Graph():
    """
    Args:
        graph (): nx.Graph ()
        node_neighbors ():
        edge_type ():
        grid_type ():
        color (): Color of the edges
        collision_flag ():
        col_tol ():
    Returns:
    """
    neighbor_nodes_collision_type = neighbor_nodes_collision_type or ["IfcSpace", "snapped_nodes"]
    for node in node_neighbors:
        node_pos = graph.nodes[node]["pos"]
        directions = list(node_neighbors[node].keys())
        for direction in directions:  # x ,y ,z
            node_neighbors_list = node_neighbors[node][direction]
            nearest_neighbour = \
                sorted(node_neighbors_list, key=lambda p: distance.euclidean(graph.nodes[p]["pos"], node_pos))[0]
            if nearest_neighbour is not None and not graph.has_edge(node, nearest_neighbour) \
                    and not graph.has_edge(node, nearest_neighbour):
                if check_space_collision(graph,
                                         edge_point_A=graph.nodes[node]["pos"],
                                         edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                         collision_flag=collision_flag,
                                         tolerance=col_tol) is False:
                    if check_neighbour_nodes_collision(graph,
                                                       edge_point_A=graph.nodes[node]["pos"],
                                                       edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                                       neighbor_nodes_collision_type=neighbor_nodes_collision_type,
                                                       no_neighbour_collision_flag=no_neighbour_collision_flag) is False:
                        length = abs(distance.euclidean(graph.nodes[nearest_neighbour]["pos"], node_pos))
                        graph.add_edge(node,
                                   nearest_neighbour,
                                   color=color,
                                   edge_type=edge_type,
                                   direction=direction,
                                   grid_type=grid_type,
                                   length=length)
    return graph


def check_neighbour_nodes_collision(graph: nx.Graph(),
                                    edge_point_A: tuple,
                                    edge_point_B: tuple,
                                    neighbor_nodes_collision_type: list = ["IfcSpace", "snapped_nodes"],
                                    no_neighbour_collision_flag: bool = True,
                                    directions: list = None):
    """
    Args:
        neighbor_nodes_collision_type (): Typ des Knotens
        graph (): Networkx Graph
        edge_point_A (): Knoten der verbunden werden soll
        edge_point_B (): Gesnappter Knoten an nächste Wand
    Returns:
    """
    directions = directions or [True, True, True]
    if no_neighbour_collision_flag is False:
        return False
    else:
        # All Nodes
        for neighbor, data in graph.nodes(data=True):
            # Koordinaten eines Knotens
            point = data["pos"]
            if point != edge_point_A and point != edge_point_B:
                if set(neighbor_nodes_collision_type) & set(data["node_type"]):
                    for i, direction in enumerate(["x", "y", "z"]):
                        if directions[i] and edge_point_A[i] == edge_point_B[i] == point[i]:
                            for j in range(3):
                                if j != i:
                                    for t in range(3):
                                        if t != i and t != j and t > j:
                                            p = Point(point[j], point[t])
                                            line = LineString(
                                            [(edge_point_A[j], edge_point_A[t]), (edge_point_B[j], edge_point_B[t])])
                                            if p.intersects(line):
                                                return p.intersects(line)
        return False

def check_space_collision(graph: nx.Graph(),
                          edge_point_A: tuple,
                          edge_point_B: tuple,
                          collision_flag: bool = True,
                          tolerance: float = 0.1,
                          collision_type_node: list = None):
    """
    Args:
        edge_point_A ():
        edge_point_B ():
        tolerance ():
        collision_type_node ():
        graph ():
   """
    collision_type_node = collision_type_node or ["IfcSpace"]
    if collision_flag is False:
        return False
    else:
        room_point_dict = {}
        for node, data in graph.nodes(data=True):
            if set(data["element_type"]) & set(collision_type_node):
                room_point_dict.setdefault(data["ID_element"], []).append(data["pos"])
        print(room_point_dict)
        polygons = []
        for element in room_point_dict:
            points = room_point_dict[element]
            coords = np.array(points)
            coords_z = coords[coords[:, 2].argsort()]
            # Bestimme maximale und minimale Y- und X-Koordinaten
            max_y = np.max(coords_z[:, 1]) - tolerance
            min_y = np.min(coords_z[:, 1]) + tolerance
            max_x = np.max(coords_z[:, 0]) - tolerance
            min_x = np.min(coords_z[:, 0]) + tolerance
            polygon_2d = Polygon([(max_x, max_y), (min_x, max_y), (max_x, min_y), (min_x, min_y)])
            polygons.append(polygon_2d)
        snapped_line = LineString([(edge_point_A[0], edge_point_A[1]), (edge_point_B[0], edge_point_B[1])])
        for poly in polygons:
            if snapped_line.crosses(poly):
                return True
        return False





def delete_edge_overlap(graph: nx.Graph(),
                        grid_type: str = "building",
                        edge_type: str = "wall",
                        color: str = "grey"
                        ) -> nx.Graph():
    """

    Args:
        graph ():
        color ():
        edge_type ():
        grid_type ():
    Returns:
    """
    index = 0
    remove_node_list = []
    intersect_node_list = []
    edges = list(graph.edges())
    num_edges_before = len(edges)
    while index < len(edges):
        edge_1 = edges[index]
        index += 1
        if graph.has_edge(edge_1[0], edge_1[1]):
            # todo: Dicitonary verändert sich:
            # for edge_2 in graph.edges(data=True):
            edge_list = list(graph.edges())
            for edge_2 in edge_list:
                if edge_1 != edge_2:
                    if graph.nodes[edge_1[0]]["pos"][2] == graph.nodes[edge_1[1]]["pos"][2] \
                            == graph.nodes[edge_2[0]]["pos"][2] == graph.nodes[edge_1[1]]["pos"][2]:
                        line_1 = LineString(
                            [graph.nodes[edge_1[0]]['pos'][0:2], graph.nodes[edge_1[1]]['pos'][0:2]])
                        line_2 = LineString(
                            [graph.nodes[edge_2[0]]['pos'][0:2], graph.nodes[edge_2[1]]['pos'][0:2]])
                        # Check if edges crosses
                        if line_1.crosses(line_2):
                            intersection_pos = line_1.intersection(line_2)
                            intersection_pos_node = (
                            intersection_pos.x, intersection_pos.y, graph.nodes[edge_1[0]]["pos"][2])
                            # Create intersection node
                            G, node = create_graph_nodes(graph,
                                                         points_list=[intersection_pos_node],
                                                         ID_element=graph.nodes[edge_1[0]]["ID_element"],
                                                         element_type=graph.nodes[edge_1[0]]["element_type"],
                                                         direction=graph.nodes[edge_1[0]]["direction"],
                                                         node_type=graph.nodes[edge_1[0]]["node_type"],
                                                         belongs_to_room=graph.nodes[edge_1[0]]["belongs_to_room"],
                                                         belongs_to_element=graph.nodes[edge_1[0]][
                                                             "belongs_to_element"],
                                                         belongs_to_storey=graph.nodes[edge_1[0]][
                                                             "belongs_to_storey"]
                                                         )
                            # Delete crosses edges
                            if graph.has_edge(edge_1[0], edge_1[1]):
                                graph.remove_edge(edge_1[0], edge_1[1])
                                edge_list.remove((edge_1[0], edge_1[1]))
                            if graph.has_edge(edge_1[1], edge_1[0]):
                                graph.remove_edge(edge_1[1], edge_1[0])
                                edge_list.remove((edge_1[1], edge_1[0]))
                            if graph.has_edge(edge_2[0], edge_2[1]):
                                graph.remove_edge(edge_2[0], edge_2[1])
                                edge_list.remove((edge_2[0], edge_2[1]))
                            if graph.has_edge(edge_2[1], edge_2[0]):
                                graph.remove_edge(edge_2[1], edge_2[0])
                                edge_list.remove((edge_2[1], edge_2[0]))
                            # Create new edges from intersection
                            # new node - edge_1[0]
                            graph.add_edge(node[0],
                                           edge_1[0],
                                           color=color,
                                           edge_type=edge_type,
                                           direction=graph.nodes[edge_1[0]]["direction"],
                                           grid_type=grid_type,
                                           length=abs(distance.euclidean(graph.nodes[node[0]]["pos"], \
                                                                         graph.nodes[edge_1[0]]["pos"]))
                                           )
                            if (node[0], edge_1[0]) not in edge_list:
                                edge_list.append((node[0], edge_1[0]))
                            # new node - edge_1[1]
                            graph.add_edge(node[0],
                                           edge_1[1],
                                           color=color,
                                           edge_type=edge_type,
                                           direction=graph.nodes[edge_1[0]]["direction"],
                                           grid_type=grid_type,
                                           length=abs(distance.euclidean(graph.nodes[node[0]]["pos"], \
                                                                         graph.nodes[edge_1[1]]["pos"]))
                                           )
                            if (node[0], edge_1[1]) not in edge_list:
                                edge_list.append((node[0], edge_1[1]))
                            # new node - edge_2[0]
                            graph.add_edge(node[0],
                                           edge_2[0],
                                           color=color,
                                           edge_type=edge_type,
                                           direction=graph.nodes[edge_2[0]]["direction"],
                                           grid_type=grid_type,
                                           length=abs(distance.euclidean(graph.nodes[node[0]]["pos"], \
                                                                         graph.nodes[edge_2[0]]["pos"]))
                                           )
                            if (node[0], edge_2[0]) not in edge_list:
                                edge_list.append((node[0], edge_2[0]))
                                # new node - edge_2[1]
                            graph.add_edge(node[0],
                                           edge_2[1],
                                           color=color,
                                           edge_type=edge_type,
                                           direction=graph.nodes[edge_2[1]]["direction"],
                                           grid_type=grid_type,
                                           length=abs(distance.euclidean(graph.nodes[node[0]]["pos"], \
                                                                         graph.nodes[edge_2[1]]["pos"]))
                                           )
                            if (node[0], edge_2[1]) not in edge_list:
                                edge_list.append((node[0], edge_2[1]))
    return graph









def create_graph_nodes(graph: nx.Graph() or nx.DiGraph(),
                       points_list: list,
                       grid_type: str = "building",
                       ID_element: str = None,
                       element_type: str = None,
                       node_type: str = None,
                       belongs_to_element: str or list = None,
                       belongs_to_room: str or list = None,
                       belongs_to_storey: str = None,
                       direction: str = None,
                       color: str = "black",
                       tol_value: float = 0.0,
                       component_type: str = None,
                       update_node: bool = True
                       ) -> tuple[nx.Graph(), list]:
    """
    Creates nodes based on a list of tuples with three-dimensional coordinates.
    Args:
        grid_type (): type of graph created.
        element_type (): type of element: IfcWall, IfcDoor, IfcWindow, IfcSpace.
        belongs_to_room (): Indicates the relationship of the element to which room (Room_ID) the node belongs-
        component_type (): Specifies the component type of the poop (e.g. radiator).
        graph (): Networkx Graphs
        points_list (): List of three-dimensional coordinates in tuples (x,y,z)
        color ():  Color of the nodes.
        node_type (): Type of nodes of the graph.
        ID_element (): Unique ID of the element (guid)
        belongs_to_element (): Indicates the relationship of the element to which room (Room_ID) the node belongs.
        belongs_to_storey (): Specifies the relationship of the element to which storey ("storey_iD") the node belongs..
        direction (): Specifies the direction in which the nodes and their elements are aligned in the coordinate system.
        tol_value (): Tollerized deviations from the position of the node
        update_node (): Check whether the node already exists at the position; if so, it is updated/extended.

    Returns:
        created_nodes(): List of created nodes with their Node_ID-
        graph (): Networkx Graphs
    """
    created_nodes = []
    for points in points_list:
        create_node = True
        node_pos = tuple(round(coord, 2) for coord in points)
        if update_node is True:
            for node, data in graph.nodes(data=True):
                if abs(distance.euclidean(data['pos'], node_pos)) <= tol_value:
                    graph.nodes[node].update(
                        {
                            'ID_element': ID_element,
                            'element_type': attr_node_list(entry=element_type, attr_list=data['element_type']),
                            'node_type': node_type,
                            'color': color,
                            "belongs_to_room": attr_node_list(entry=belongs_to_element,
                                                                 attr_list=data['belongs_to_room']),
                            "belongs_to_element": attr_node_list(entry=belongs_to_element,
                                                                 attr_list=data['belongs_to_element']),
                            'belongs_to_storey': belongs_to_storey,
                            'direction': direction,
                            'grid_type': grid_type,
                            'component_type': component_type
                        })
                    created_nodes.append(node)
                    create_node = False
                    break
        if create_node:
            id_name = generate_unique_node_id(graph, floor_id=belongs_to_storey)
            graph.add_node(id_name,
                           pos=node_pos,
                           color=color,
                           ID_element=ID_element,
                           element_type=check_attribute(attribute=element_type),
                           node_type=node_type,
                           belongs_to_element=check_attribute(attribute=belongs_to_element),
                           belongs_to_room=check_attribute(attribute=belongs_to_room),
                           belongs_to_storey=belongs_to_storey,
                           grid_type=grid_type,
                           direction=direction,
                           component_type=component_type)
            created_nodes.append(id_name)
    return graph, created_nodes


def check_attribute(attribute: str or list):
    return [attribute] if isinstance(attribute, str) else attribute


def attr_node_list(entry: list or str, attr_list: list):
    if not isinstance(attr_list, list):
        attr_list = []
    attr_list.extend(item for item in (entry if isinstance(entry, list) else [entry]) if item not in attr_list)
    return attr_list


def generate_unique_node_id(graph: nx.Graph(), floor_id: str):
    prefix = f"floor{floor_id}_"
    existing_ids = [int(node[len(prefix):]) for node in graph.nodes if
                    isinstance(node, str) and node.startswith(prefix)]
    new_id = max(existing_ids, default=-1) + 1

    return f"{prefix}{new_id}"

