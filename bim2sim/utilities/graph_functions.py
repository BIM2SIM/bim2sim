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
from bim2sim.utilities.visualize_graph_functions import visualzation_networkx_3D, visulize_networkx

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
                        tol_value: float = 0.0) -> dict:
    """

    Args:
        graph (): nx.Graph()
        working_node_dict (): A sorted dictionary where each key is a node and its values are possible nodes that can be connected to the node.
        directions (): Specification of the direction in which edges can be placed: [x,y,z]. Should I lay all directions [True, True, True].
        tol_value (): Tollerized deviations from the position of the node.
    return:
        pos_negativ_neighbors {}: Creates a dictionary where each key is a node. Its values are sorted by x,y or z  in positive and negative direction.
    """
    directions = directions or [True, True, True]
    pos_negativ_neighbors = {}
    for node in working_node_dict:
        pos_negativ_neighbors.setdefault(node, {"positive": {}, "negative": {}})
        for neighbor_node in working_node_dict[node]:
            neighbor_pos = tuple(round(coord, 2) for coord in graph.nodes[neighbor_node]["pos"])
            node_pos = tuple(round(coord, 2) for coord in graph.nodes[node]["pos"])
            for i, direction in enumerate(["x", "y", "z"]):
                if directions[i]:
                    diff = neighbor_pos[i] - node_pos[i]
                    if diff < 0 and all(abs(neighbor_pos[j] - node_pos[j]) <= tol_value for j in range(3) if j != i):
                        pos_negativ_neighbors[node]["positive"].setdefault(direction, []).append(neighbor_node)
                    elif diff > 0 and all(abs(neighbor_pos[j] - node_pos[j]) <= tol_value for j in range(3) if j != i):
                        pos_negativ_neighbors[node]["negative"].setdefault(direction, []).append(neighbor_node)
    return pos_negativ_neighbors


def sort_connect_nodes(graph: nx.Graph() or nx.DiGraph(),
                       connect_nodes: list = None,
                       element_types: list = None,
                       node_with_same_ID_element_flag: bool = False,
                       node_with_same_element_types_flag: bool = False,
                       ) -> dict:
    """
    Searches nodes for a transferred node according to different requirement criteria.
    Args:
        graph (): nx.Graph()
        connect_nodes (): List of existing nodes that are to be connected to other nodes via edges.
        element_types ():
        node_with_same_element_types_flag ():
        connect_node_flag ():
        to_connect_node_list ():
        node_with_same_ID_element_flag (): Searches for all nodes in the graph that have the same "ID_Element" attribute.
    Returns:
        working_connection_nodes (): Outputs a sorted dictionary. Each key is a node and its values are matching nodes that fulfill certain requirement criteria.
    """
    element_types = element_types or ["IfcSpace"]
    working_connection_nodes = {}
    if connect_nodes:
        for working_node in connect_nodes:
            working_connection_nodes.setdefault(working_node, [])
            # Sucht passende Knoten für ein orthogonales Koordinatensystem
            for neighbor, data in graph.nodes(data=True):
                if neighbor != working_node and node_with_same_ID_element_flag and \
                        graph.nodes[working_node]["ID_element"] == data["ID_element"]:
                    working_connection_nodes[working_node].append(neighbor)
                if neighbor != working_node and node_with_same_element_types_flag:# and element_types:
                    if isinstance(element_types, list):
                        if data["element_type"] in element_types:
                            working_connection_nodes[working_node].append(neighbor)
        return working_connection_nodes
    else:
        logger.error(f'No nodes to connect: {connect_nodes}. Please add a list of nodes.')
        exit(1)


def nearest_polygon_in_space(project_node_pos: tuple,
                             direction: str,
                             room_global_points: list,
                             floor_flag: bool = True) -> tuple:
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
    poly_dict = {"floor": Polygon(coords[coords[:, 2].argsort()][4:]),
                 "roof": Polygon(coords[coords[:, 2].argsort()][:4]),
                 "wall_x_pos": Polygon(coords[coords[:, 0].argsort()][:4]),
                 "wall_x_neg": Polygon(coords[coords[:, 0].argsort()][4:]),
                 "wall_y_pos": Polygon(coords[coords[:, 1].argsort()][:4]),
                 "wall_y_neg": Polygon(coords[coords[:, 1].argsort()][4:])}
    poly_list = []
    poly_distance_dict = {}
    for poly in poly_dict:
        polygon_2d = None
        bounds_check = None
        distance_func = None
        # z richtung
        if floor_flag and direction == "z" and poly in ["floor", "roof"]:
            coords_slice = slice(3) if poly == "roof" else slice(3, None)
            polygon_2d = Polygon([(point[0], point[1]) for point in Polygon(coords_z[coords_slice]).exterior.coords])
            bounds_check = lambda bounds: bounds[0] <= point.x <= bounds[2] and bounds[1] <= point.y <= bounds[3]
            distance_func = lambda ext: abs(point.z - poly_dict[poly].exterior.interpolate(ext.project(point)).z)

        if direction == "y" and poly in ["wall_x_pos", "wall_x_neg"]:
            coords_slice = slice(3) if poly == "wall_x_pos" else slice(3, None)
            polygon_2d = Polygon([(point[1], point[2]) for point in Polygon(coords_x[coords_slice]).exterior.coords])
            bounds_check = lambda bounds: bounds[0] <= point.y <= bounds[2] and bounds[1] <= point.z <= bounds[3]
            distance_func = lambda ext: abs(point.x - poly_dict[poly].exterior.interpolate(ext.project(point)).x)

        if direction == "x" and poly in ["wall_y_pos", "wall_y_neg"]:
            coords_slice = slice(4) if poly == "wall_y_pos" else slice(4, None)
            polygon_2d = Polygon([(point[0], point[2]) for point in Polygon(coords_y[coords_slice]).exterior.coords])
            bounds_check = lambda bounds: bounds[0] <= point.x <= bounds[2] and bounds[1] <= point.z <= bounds[3]
            distance_func = lambda ext: abs(point.y - poly_dict[poly].exterior.interpolate(ext.project(point)).y)

        if polygon_2d is not None and bounds_check(polygon_2d.bounds):
            distance = distance_func(poly_dict[poly].exterior)
            poly_list.append(poly_dict[poly])
            poly_distance_dict[poly_dict[poly]] = distance
    projected_point = None
    try:
        nearest_rectangle = min(poly_distance_dict, key=poly_distance_dict.get)
    except ValueError:
        return None
    projected_point_on_boundary = nearest_rectangle.exterior.interpolate(nearest_rectangle.exterior.project(point))
    for poly_key, poly_val in poly_dict.items():
        if nearest_rectangle == poly_val:
            if poly_key in ["wall_x_pos", "wall_x_neg"]:
                projected_point = Point(projected_point_on_boundary.x, point.y, point.z)
            if poly_key in ["wall_y_pos", "wall_y_neg"]:
                projected_point = Point(point.x, projected_point_on_boundary.y, point.z)
            if poly_key in ["floor", "roof"]:
                projected_point = Point(point.x, point.y, projected_point_on_boundary.z)
    return projected_point.coords[0]

def project_nodes_on_building(graph: nx.Graph(),
                              project_node_list: list,
                              element_type: list = None,
                              ) -> tuple[nx.Graph(), list]:
    """
    Projeziert Knoten die außerhalb des Gebäudes sind, auf die Gebäude Ebene und löscht den Ursprünglichen Knoten
    Args:
        graph (): nx.graph()
        project_node_list (): list of nodes, that are projected on a polygon
    Returns:
    """
    element_type = element_type or ["IfcSpace"]
    room_node_list = {}
    for project_node in project_node_list:
        for room_node, data in graph.nodes(data=True):
            # Search for the room/ thermal space in which the element is in.
            if data["ID_element"] in graph.nodes[project_node]["belongs_to_room"] and \
                    data["element_type"] in element_type:
                room_node_list.setdefault(project_node, []).append(data["pos"])
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
                 element_type: list = None ,
                 edge_same_belongs_to_room_flag: bool = False,
                 edge_same_element_type_flag: bool = False,
                 edge_same_belongs_to_storey_flag:bool =False) -> list:
    """
    Args:
        element_type ():
        edge_element_belongs_to_space_flag ():
        edge_snapped_nodes_in_space_flag ():
        all_edges_flag ():
        graph (): Networkx Graph
        node (): Knoten, der mit dem Graphen verbunden werden soll.
    Returns:
    """
    element_type = element_type or ["IfcSpace"]
    edge_list = []

    for edge in graph.edges(data=True):
        # exception requirements
        if node in edge:
            continue

        # search requirements
        # Node Attributes
        if edge_same_belongs_to_room_flag and \
                all(set(graph.nodes[edge[i]]["belongs_to_room"]) &
                   set(graph.nodes[node]["belongs_to_room"]) for i in range(2)):
            edge_list.append((edge[0], edge[1]))
        if edge_same_element_type_flag and \
                 any(graph.nodes[edge[i]]["element_type"] in
                    element_type for i in range(2)):
            edge_list.append((edge[0], edge[1])) #edge_same_belongs_to_storey_flag
        if edge_same_belongs_to_storey_flag and  all(graph.nodes[edge[i]]["belongs_to_storey"] == graph.nodes[node]["belongs_to_storey"] for i in range(2)):
            #if edge_same_element_type_flag and \
            if     any(graph.nodes[edge[i]]["element_type"] in
                    element_type for i in range(2)):
                edge_list.append((edge[0], edge[1]))

    return list(set(edge_list))


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
                type: str):

    if nx.is_connected(graph):
        logger.info(f"{type} Graph is connected.")
        return graph
    else:
        logger.warning(f"{type} Graph is not connected.")
        for node in graph.nodes():
            if nx.is_isolate(graph, node):
                logger.warning(f"node {node} is not connected." \
                                             f'{graph.nodes[node]["pos"]} with type {graph.nodes[node]["node_type"]} '
                                             f'and element type {graph.nodes[node]["element_type"]}')

        graph = kit_grid(graph)
        if nx.is_connected(graph):
            logger.info(f" {type} Graph is connected.")
            return graph
        else:
            visulize_networkx(graph, graph.graph["grid_type"])
            logger.warning(f"{type} Graph is not connected.")
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
        logger.info(f"Read building graph from json-file: {json_file}")
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
    node_pos = graph.nodes[node]["pos"]
    lines_dict = {}
    for edge in edges:
        (x1, y1, z1), (x2, y2, z2) = graph.nodes[edge[0]]["pos"], graph.nodes[edge[1]]["pos"]
        if node in edge:
            continue
        # Prüfe x line
        # y1 = y2, z1 = z2
        if abs(y1 - y2) <= tol_value and abs(z1 - z2) <= tol_value and x1 < node_pos[0] < x2 or x2 < node_pos[0] < x1:
            if abs(z1 - node_pos[2]) <= tol_value and pos_y_flag and node_pos[1] > y1: #
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
            if abs(z1 - node_pos[2]) <= tol_value and neg_y_flag and node_pos[1] < y1:
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
            if abs(y1 - node_pos[1]) <= tol_value and bottom_z_flag and node_pos[2] > z1 :
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
            if abs(y1 - node_pos[1]) <= tol_value and top_z_flag and node_pos[2] < z1:
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
        # Prüfe y line
        if abs(x1 - x2) <= tol_value and abs(z1 - z2) <= tol_value and y1 < node_pos[1] < y2 or y2 < node_pos[1] < y1:
            if abs(z1 - node_pos[2]) <= tol_value and pos_x_flag and node_pos[0] > x1:
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
            if abs(z1 - node_pos[2]) <= tol_value and neg_x_flag and node_pos[0] < x1:
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
            if abs(x1 - node_pos[0]) <= tol_value and bottom_z_flag and node_pos[2] > z1:
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
            if  abs(x1 - node_pos[0]) <= tol_value and top_z_flag and node_pos[2] < z1:
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
        # Prüfe z line
        if abs(x1 - x2) <= tol_value and abs(y1 - y2) <= tol_value and z1 < node_pos[2] < z2 or z2 < node_pos[2] < z1:
            if abs(x1 - node_pos[0]) <= tol_value and pos_y_flag and node_pos[1] > y1 :
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
            if abs(x1 - node_pos[0]) <= tol_value and neg_y_flag and node_pos[1] < y1:
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
            if abs(y1 - node_pos[1]) <= tol_value and pos_x_flag and node_pos[0] > x1:
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
            if abs(y1 - node_pos[1]) <= tol_value and  neg_x_flag and node_pos[0] < x1:
                lines_dict[(edge[0], edge[1])] = LineString([(x1, y1, z1), (x2, y2, z2)])
    point = Point(node_pos)
    nearest_lines = None
    new_node_pos = None

    if pos_x_flag or neg_x_flag:
        nearest_lines = min(lines_dict.items(),
                            key=lambda item: abs(item[1].coords[0][0] - point.x)) if lines_dict else {}
        if nearest_lines:
            new_node_pos = (nearest_lines[1].coords[0][0], node_pos[1], node_pos[2])
    elif pos_y_flag or neg_y_flag:
        nearest_lines = min(lines_dict.items(),
                            key=lambda item: abs(item[1].coords[0][1] - point.y)) if lines_dict else {}
        if nearest_lines:
            new_node_pos = (node_pos[0], nearest_lines[1].coords[0][1], node_pos[2])
    elif top_z_flag or bottom_z_flag:
        nearest_lines = min(lines_dict.items(),
                            key=lambda item: abs(item[1].coords[0][2] - point.z)) if lines_dict else {}
        if nearest_lines:
            new_node_pos = (node_pos[0], node_pos[1], nearest_lines[1].coords[0][2])
    return nearest_lines, new_node_pos


def remove_nodes_by_attribute(graph: nx.Graph() or nx.DiGraph(),
                              element_type: list) -> nx.DiGraph() or nx.DiGraph:
    nodes_to_remove = []
    for node, data in graph.nodes(data=True):
        if isinstance(element_type, list):
            if data["element_type"] in element_type:
                nodes_to_remove.append(node)
    graph.remove_nodes_from(nodes_to_remove)
    return graph

def return_attribute_element_type_nodes(graph: nx.Graph() or nx.DiGraph(),
                           element_type: list) -> list:
    attribute_nodes = []
    for node, data in graph.nodes(data=True):
        if isinstance(element_type, list):
            if data["element_type"] in element_type:
                attribute_nodes.append(node)
    return attribute_nodes

def return_attribute_node_type_nodes(graph: nx.Graph() or nx.DiGraph(),
                                     node_type: str or list) -> list:
    attribute_nodes = []
    for node, data in graph.nodes(data=True):
        if isinstance(node_type, str):
            if node_type == data["node_type"]:
                attribute_nodes.append(node)
        if isinstance(node_type, list):
            if data["node_type"] in node_type:
                attribute_nodes.append(node)
    return attribute_nodes


def snapp_nodes_to_grid(graph: nx.Graph(),
                        node_list: list,
                        bottom_z_flag: bool = False,
                        top_z_flag: bool = False,
                        pos_x_flag: bool = False,
                        neg_x_flag: bool = False,
                        pos_y_flag: bool = False,
                        neg_y_flag: bool = False,
                        filter_edge_node_element_type: list = None,
                        snapped_node_type:str = "snapped_node",
                        color: str = "grey",
                        element_type:str  = None,
                        snapped_edge_type:str = "room_snapped_edge" ,
                        col_tol: float = 0.1,
                        edge_same_belongs_to_room_flag: bool = False,
                        edge_same_element_type_flag:bool = False,
                        collision_space_flag: bool = True,
                        no_neighbour_collision_flag: bool = True,
                        edge_same_belongs_to_storey_flag:bool =False
                        ) -> nx.Graph():
    """
    Args:

        neg_x_flag ():
        top_z_flag (): Falls False: Sucht nur in negativer z richtung
        graph (): Networkx Graph
        node_list (): Liste von Knoten die mit dem Graphen verbunden werden
        Suchen der Kanten, auf die ein neuer Knoten gesnappt werden kann.
    Returns:
    """
    filter_edge_node_element_type = filter_edge_node_element_type or ["IfcSpace"]
    direction_flags = [top_z_flag, bottom_z_flag, pos_x_flag, neg_x_flag, pos_y_flag, neg_y_flag]
    logger.info(f"Number of snapped nodes {len(node_list)}")
    for i, node in enumerate(node_list):
        # Sucht alle Kanten, auf die ein Knoten gesnappt werden kann.
        element_type = element_type or graph.nodes[node]["element_type"]
        for j, direction in enumerate(direction_flags):
            logger.info(f"Number node ({i + 1}/{len(node_list)})")
            direction_flags = [top_z_flag, bottom_z_flag, pos_x_flag, neg_x_flag, pos_y_flag, neg_y_flag]
            for k, flag in enumerate(direction_flags):
                if j == k:
                    direction_flags[k] = flag
                else:
                    direction_flags[k] = False
            if not any(direction_flags):
                continue
            edge_list = filter_edges(graph,
                                     node=node,
                                     edge_same_element_type_flag=edge_same_element_type_flag,
                                     edge_same_belongs_to_room_flag=edge_same_belongs_to_room_flag,
                                     element_type=filter_edge_node_element_type,
                                     edge_same_belongs_to_storey_flag=edge_same_belongs_to_storey_flag)
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
            if new_node_pos:
                if not check_space_collision(graph,
                                             edge_point_A=graph.nodes[node]["pos"],
                                             edge_point_B=new_node_pos,
                                             collision_space_flag=collision_space_flag,
                                             tolerance=col_tol) and \
                        not check_neighbour_nodes_collision(graph,
                                                            edge_point_A=graph.nodes[node]["pos"],
                                                            edge_point_B=new_node_pos,
                                                            no_neighbour_collision_flag=no_neighbour_collision_flag):
                    # todo: node_type=f'{snapped_node_type}_{graph.nodes[node]["element_type"]}',
                    graph, created_nodes = create_graph_nodes(graph,
                                                              points_list=[new_node_pos],
                                                              ID_element=graph.nodes[node]["ID_element"],
                                                              element_type=element_type,
                                                              direction=graph.nodes[node]["direction"],
                                                              node_type=f'{snapped_node_type}_{graph.nodes[node]["element_type"]}',
                                                              belongs_to_room=graph.nodes[node]["belongs_to_room"],
                                                              belongs_to_element=graph.nodes[node]["belongs_to_element"],
                                                              belongs_to_storey=graph.nodes[node]["belongs_to_storey"],
                                                              update_node=True)

                    if created_nodes:
                        graph.remove_edges_from([(nearest_lines[0][0], nearest_lines[0][1]),
                                                 (nearest_lines[0][1], nearest_lines[0][0])])

                        for created_node in created_nodes:
                            for start_node in [nearest_lines[0][0], nearest_lines[0][1], node]:

                                if start_node != created_node: # and not graph.has_edge(start_node, created_node):
                                    if start_node == node:
                                        edge_type = "snapped_edge"
                                    else:
                                        edge_type = snapped_edge_type
                                    if graph.has_edge(start_node, created_node) or graph.has_edge(created_node, start_node):
                                        continue
                                    else:
                                        graph.add_edge(start_node,
                                                       created_node,
                                                       color=color,
                                                       element_type=graph.nodes[start_node]["element_type"],
                                                       edge_type=edge_type,
                                                       grid_type=graph.nodes[node]["grid_type"],
                                                       direction=direction,
                                                       length=abs(distance.euclidean(graph.nodes[start_node]["pos"],
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
    for i, subgraph in enumerate(graph_list):
        prefix = f"{i}_"
        relabeling = {}
        for node in subgraph.nodes:
            relabeling[node] = f'{prefix}_{node}'
        subgraph_renamed = nx.relabel_nodes(subgraph, relabeling)
        combined_graph = nx.union(combined_graph, subgraph_renamed)
    combined_graph.graph["grid_type"] = grid_type
    return combined_graph


def connect_nodes_via_edges(graph: nx.Graph(),
                            node_neighbors: dict,
                            edge_type: str = None,
                            element_type: str or list = None,
                            grid_type: str = None,
                            color: str = "black",
                            no_neighbour_collision_flag: bool = True,
                            collision_space_flag: bool = True,
                            col_tol: float = 0.1) -> nx.Graph():
    """
    Args:
        no_neighbour_collision_flag ():
        graph (): nx.Graph ()
        node_neighbors (): Dictionaries with neighbouring nodes that are sorted in x, y or z direction
        edge_type (): type of the created edges
        grid_type (): type of the grid type of the created edges
        color (): Color of the edges
        collision_space_flag ():
        col_tol (): Tolerance of the polygons. The polygon is reduced by the collision tolerance.
    Returns:
        graph (): nx.Graph ()
    """
    for node in node_neighbors:
        node_pos = graph.nodes[node]["pos"]
        directions = list(node_neighbors[node].keys())
        for direction in directions:  # positive, negative
            coord_directions = list(node_neighbors[node][direction].keys())
            for coord in coord_directions:  # x ,y ,z
                node_neighbors_list = node_neighbors[node][direction][coord]
                nearest_neighbour = \
                    sorted(node_neighbors_list, key=lambda p: distance.euclidean(graph.nodes[p]["pos"], node_pos))[0]

                if nearest_neighbour:
                    if not graph.has_edge(node, nearest_neighbour) and not graph.has_edge(nearest_neighbour, node):
                        if not check_space_collision(graph,
                                                     edge_point_A=graph.nodes[node]["pos"],
                                                     edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                                     collision_space_flag=collision_space_flag,
                                                     tolerance=col_tol) \
                                and not check_neighbour_nodes_collision(graph,
                                                                        edge_point_A=graph.nodes[node]["pos"],
                                                                        edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                                                        no_neighbour_collision_flag=no_neighbour_collision_flag):
                            length = abs(distance.euclidean(graph.nodes[nearest_neighbour]["pos"], node_pos))
                            graph.add_edge(node,
                                           nearest_neighbour,
                                           color=color,
                                           element_type=element_type,
                                           edge_type=edge_type,
                                           direction=direction,
                                           grid_type=grid_type,
                                           length=length)
    return graph

def remove_edges_by_attribute(graph: nx.Graph() or nx.DiGraph(),
                              edge_type: str or list) -> nx.Graph() or nx.DiGraph():
    edges_to_remove = []
    for u, v, data in graph.edges(data=True):
        if isinstance(edge_type, str):
            if edge_type == data["edge_type"]:
                edges_to_remove.append((u,v))
        if isinstance(edge_type, list):
            if data["edge_type"] in edge_type:
                edges_to_remove.append((u, v))
    graph.remove_edges_from(edges_to_remove)
    return graph

def check_neighbour_nodes_collision(graph: nx.Graph(),
                                    edge_point_A: tuple,
                                    edge_point_B: tuple,
                                    no_neighbour_collision_flag: bool = True,
                                    directions: list = None) -> bool:
    """
    Args:

        graph (): Networkx Graph
        edge_point_A (): Knoten der verbunden werden soll
        edge_point_B (): Gesnappter Knoten an nächste Wand
    Returns:
        bool: If True line intersect with another nodes else not.
    """

    directions = directions or [True, True, True]
    if not no_neighbour_collision_flag:
        return False
    for neighbor, data in graph.nodes(data=True):
        if data["pos"] not in (edge_point_A, edge_point_B):
            for i, direction in enumerate(["x", "y", "z"]):
                if directions[i] and edge_point_A[i] == edge_point_B[i] == data["pos"][i]:
                    for j in range(3):
                        if j != i:
                            for t in range(3):
                                if t != i and t != j and t > j:
                                    p = Point(data["pos"][j], data["pos"][t])
                                    line = LineString(
                                        [(edge_point_A[j], edge_point_A[t]),
                                         (edge_point_B[j], edge_point_B[t])])
                                    if p.intersects(line):
                                        return True
    return False


def check_space_collision(graph: nx.Graph(),
                          edge_point_A: tuple,
                          edge_point_B: tuple,
                          collision_space_flag: bool = True,
                          tolerance: float = 0.1,
                          collision_type_node: list = None) -> bool:
    """
    Args:
        edge_point_A ():
        edge_point_B ():
        tolerance ():
        collision_type_node ():
        graph (): nx.Graph ()
   """
    collision_type_node = collision_type_node or ["IfcSpace"]
    if not collision_space_flag:
        return False
    room_point_dict = {}
    for node, data in graph.nodes(data=True):
        if data["element_type"] in collision_type_node:
            room_point_dict.setdefault(data["ID_element"], []).append(data["pos"])
    polygons = [Polygon([(np.max(coords[:, 0]) - tolerance, np.max(coords[:, 1]) - tolerance),
                         (np.min(coords[:, 0]) + tolerance, np.max(coords[:, 1]) - tolerance),
                         (np.max(coords[:, 0]) - tolerance, np.min(coords[:, 1]) + tolerance),
                         (np.min(coords[:, 0]) + tolerance, np.min(coords[:, 1]) + tolerance)]) for coords in
                [np.array(room_point_dict[element])[:, :2] for element in room_point_dict]]
    snapped_line = LineString([(edge_point_A[0], edge_point_A[1]), (edge_point_B[0], edge_point_B[1])])
    return any(snapped_line.crosses(poly) for poly in polygons)

def remove_edges_from_node(G: nx.Graph(),
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

def delete_edge_overlap(graph: nx.Graph() or nx.DiGraph(),
                        color: str = "grey",
                        edge_type: str ="ifc_element"
                        ) -> nx.Graph() or nx.DiGraph():
    """

    Args:
        graph ():
        color (): color of edges
        edge_type ():
        grid_type ():
    Returns:
    """
    edges = list(graph.edges())
    index = 0
    while index < len(list(graph.edges())):
        intersect_flag = False
        edge_1 = list(graph.edges())[index]
        if graph.has_edge(edge_1[0], edge_1[1]):
            edge_list = list(graph.edges())
            j = 0
            """while  j < len(list(graph.edges())):
                edge_2 = list(graph.edges())[j]
                print(index)"""
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
                            index = 0
                            j = 0
                            intersect_flag = True
                            intersection_pos = line_1.intersection(line_2)
                            intersection_pos_node = (
                                intersection_pos.x, intersection_pos.y, graph.nodes[edge_1[0]]["pos"][2])
                            # Create intersection node
                            G, created_node = create_graph_nodes(graph,
                                                         points_list=[intersection_pos_node],
                                                         ID_element=graph.nodes[edge_1[0]]["ID_element"],
                                                         element_type=graph.nodes[edge_1[0]]["element_type"],
                                                         direction=graph.nodes[edge_1[0]]["direction"],
                                                         node_type=graph.nodes[edge_1[0]]["node_type"],
                                                         belongs_to_room=graph.nodes[edge_1[0]]["belongs_to_room"],
                                                         belongs_to_element=graph.nodes[edge_1[0]][
                                                             "belongs_to_element"],
                                                         belongs_to_storey=graph.nodes[edge_1[0]][
                                                             "belongs_to_storey"],
                                                         update_node=True)
                            for start_node in [(edge_1[0], edge_1[1]), (edge_2[0], edge_2[1])]:
                                if graph.has_edge(start_node[0], start_node[1]):
                                    graph.remove_edge(start_node[0], start_node[1])
                                    edge_list.remove((start_node[0], start_node[1]))
                                if graph.has_edge(start_node[1], start_node[0]):
                                    graph.remove_edge(start_node[1], start_node[0])
                                    edge_list.remove((start_node[1], start_node[0]))
                                for node in start_node:
                                    if graph.has_edge(created_node[0], node) or graph.has_edge(node , created_node[0]):
                                        continue
                                    else:
                                        edge_list.append((created_node[0], node))
                                        graph.add_edge(created_node[0],
                                                       node,
                                                       color=color,
                                                       edge_type=edge_type,
                                                       direction=graph.nodes[node]["direction"],
                                                       grid_type=graph.nodes[node]["grid_type"],
                                                       length=abs(distance.euclidean(graph.nodes[created_node[0]]["pos"], \
                                                                                     graph.nodes[node]["pos"])))
                        else:
                            j =  j + 1
                    else:
                        j = j + 1
                else:
                    j = j + 1
        if not intersect_flag:
            index = index +1

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
        if update_node:
            for node, data in graph.nodes(data=True):
                if abs(distance.euclidean(data['pos'], node_pos)) <= tol_value:
                    data.update(
                        {
                            'ID_element': ID_element,
                            'element_type': element_type,
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
                           element_type=element_type,
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
