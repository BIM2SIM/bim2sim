import json
import bim2sim
import networkx as nx
from networkx.algorithms.components import is_strongly_connected
from scipy.spatial import distance
from shapely.ops import nearest_points
from shapely.geometry import Polygon, Point, LineString
import numpy as np
from bim2sim.elements.bps_elements import ThermalZone, Door, Wall, Window, OuterWall, Floor




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


def sort_edge_direction(graph: nx.Graph(),
                        working_node_dict: dict,
                        directions: list = [True, True, True],
                        tol_value: float = 0.0) -> tuple[dict, dict]:
    """
    Zieht Grade Kanten in eine Richtung X, Y oder Z Richtung.
    Args:
        direction (): Sucht Kanten in X ,Y oder Z Richtung
        node_pos (): Position des Knoten, der verbunden werden soll.
        tol_value (): Toleranz bei kleinen Abweichungen in X,Y oder Z Richtungen
        neighbor_node (): Potentieller benachbarter Knoten

    Returns:
        pos_neighbors (): Dictionary von benachbarten Knoten in positiver Richtung
        neg_neighbors (): Dictionary von benachbarten Knoten in negativer Richtung

    """
    pos_neighbors = {}
    neg_neighbors = {}
    for node in working_node_dict:
        if node not in pos_neighbors:
            pos_neighbors[node] = {}
        if node not in neg_neighbors:
            neg_neighbors[node] = {}

        for neighbor_node in working_node_dict[node]:
            neighbor_pos = tuple(round(coord, 2) for coord in graph.nodes[neighbor_node]["pos"])
            node_pos = tuple(round(coord, 2) for coord in graph.nodes[node]["pos"])
            for i, direction in enumerate(["x", "y", "z"]):
                if directions[i]:
                    diff = neighbor_pos[i] - node_pos[i]
                    if diff < 0 and all(abs(neighbor_pos[j] - node_pos[j]) <= tol_value for j in range(3) if j != i):
                        if direction not in pos_neighbors[node]:
                            pos_neighbors[node][direction] = []
                        pos_neighbors[node][direction].append(neighbor_node)
                    elif diff > 0 and all(abs(neighbor_pos[j] - node_pos[j]) <= tol_value for j in range(3) if j != i):
                        if direction not in neg_neighbors[node]:
                            neg_neighbors[node][direction] = []
                        neg_neighbors[node][direction].append(neighbor_node)
    return neg_neighbors, pos_neighbors


def sort_connect_nodes(graph: nx.Graph(),
                       connect_nodes: list,
                       connect_node_flag: bool = False,
                       to_connect_node_list: list = None,
                       connect_ID_element: bool = False,
                       connect_floor_spaces_together: bool = False,
                       connect_types_element: bool = False,
                       all_node_flag: bool = False,
                       node_type: list = None
                       ) -> dict:
    """

    Args:
        graph ():
        connect_nodes ():
        connect_node_flag ():
        to_connect_node_list ():
        connect_ID_element ():
        connect_floor_spaces_together ():
        connect_types_element ():
        all_node_flag ():
        node_type ():

    Returns:

    """
    working_connection_nodes = {}
    if connect_nodes and len(connect_nodes) > 0:
        # Sucht passende Knoten aus
        for working_node in connect_nodes:
            if working_node not in working_connection_nodes:
                working_connection_nodes[working_node] = []
            pos_neighbors = {}
            neg_neighbors = {}
            # Sucht passende Knoten aus der Knotenliste für ein orthogonales Koordinatensystem
            if connect_node_flag:
                if to_connect_node_list is not None:
                    for connect_node in to_connect_node_list:
                        if connect_node != working_node:
                            working_connection_nodes[working_node].append(connect_node)
            # Sucht passende Knoten für ein orthogonales Koordinatensystem
            else:
                for neighbor, data in graph.nodes(data=True):
                    if neighbor != working_node:
                        if connect_ID_element:
                            if set(graph.nodes[working_node]["ID_element"]) & set(data["ID_element"]):
                                working_connection_nodes[working_node].append(neighbor)
                        if connect_floor_spaces_together and node_type is not None:
                            if set(node_type) & set(graph.nodes[working_node]["type"]) & set(data["type"]):
                                working_connection_nodes[working_node].append(neighbor)
                            # if graph.nodes[working_node]["belongs_to_storey"] == data["belongs_to_storey"] and set(graph.nodes[working_node]["element"]).isdisjoint(set(data["element"])):
                        if connect_types_element:
                            if set(node_type) & set(data["type"]) and set(graph.nodes[working_node]["element"]) & set(
                                    data["element"]):
                                working_connection_nodes[working_node].append(neighbor)
                        if all_node_flag is True:
                            working_connection_nodes[working_node].append(neighbor)
        return working_connection_nodes

def nearest_polygon_in_space(G: nx.Graph(),
                             node,
                             room_global_points,
                             floor_flag: bool = True):
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


def project_nodes_on_building(graph: nx.Graph(),
                              project_node_list: list,
                              element_type: list = ["IfcSpace"],
                              grid_type: str ="building",
                              color: str = "grey") \
                                -> tuple[nx.Graph(), list]:
    """
    Projeziert Knoten die außerhalb des Gebäudes sind, auf die Gebäude Ebene und löscht den Ursprünglichen Knoten
    Args:
        graph ():
        project_node_list ():
        color ():
        grid_type ():
    Returns:
    """
    # isinstance(data["element_type"], ThermalZone)
    for node in project_node_list:
        room_node_list = []
        belongs_to_element = (graph.nodes[node]["belongs_to_element"])
        for node, data in graph.nodes(data=True):
            if data["ID_element"] in belongs_to_element and set(element_type) &  set(data["element_type"]):
                room_node_list.append(node)

    """
    
   


    poly_nodes = get_space_nodes(graph=graph,
                                 element=graph.nodes[project_node_list[0]]["belongs_to_element"],
                                 type=["space"])

    projected_nodes = []
    room_global_points = []
    for poly in poly_nodes:
        room_global_points.append(graph.nodes[poly]["pos"])
    if len(project_node_list) > 0 and project_node_list is not None:
        for i, node in enumerate(project_node_list):
            projected_window_point = nearest_polygon_in_space(G=graph,
                                                                   node=node,
                                                                   room_global_points=room_global_points)

            if projected_window_point is not None:
                type_node = graph.nodes[node]["type"]
                element = graph.nodes[node]["element"]
                belongs_to = graph.nodes[node]["belongs_to"]
                floor_id = graph.nodes[node]["floor_belongs_to"]
                direction = graph.nodes[node]["direction"]
                graph, project_node = self.create_nodes(G=graph,
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
            if node in graph.nodes():
                graph.remove_node(node)"""
    return graph, projected_nodes




def connect_nodes_via_edges(graph: nx.Graph(),
                       node_neighbors: dict,
                       edge_type: str,
                       grid_type:str,
                       color: str = "black",
                       neighbor_nodes_collision_type: list = ["space", "snapped_nodes"],
                       no_neighbour_collision_flag: bool = False,
                       collision_flag: bool = False,
                       col_tol: float = 0.1) -> nx.Graph():
    """

    Args:
        graph ():
        node_neighbors ():
        edge_type ():
        grid_type ():
        color ():
        collision_flag ():
        col_tol ():

    Returns:

    """
    for node in node_neighbors:
        node_pos = graph.nodes[node]["pos"]
        directions = list(node_neighbors[node].keys())
        for direction in directions:
            node_neighbors_list = node_neighbors[node][direction]
            nearest_neighbour = \
                sorted(node_neighbors_list, key=lambda p: distance.euclidean(graph.nodes[p]["pos"], node_pos))[0]
            if nearest_neighbour is not None and not graph.has_edge(node, nearest_neighbour) \
                    and not graph.has_edge(node, nearest_neighbour):
                if check_collision(graph,
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
                                   type=edge_type,
                                   direction=direction,
                                   grid_type=grid_type,
                                   length=length)
    return graph


def check_neighbour_nodes_collision(graph: nx.Graph(),
                                    edge_point_A: tuple,
                                    edge_point_B: tuple,
                                    neighbor_nodes_collision_type: list = ["space", "snapped_nodes"],
                                    no_neighbour_collision_flag: bool = True,
                                    directions: list = [True, True, True]):
    """
    Args:
        neighbor_nodes_collision_type (): Typ des Knotens
        graph (): Networkx Graph
        edge_point_A (): Knoten der verbunden werden soll
        edge_point_B (): Gesnappter Knoten an nächste Wand
    Returns:
    """
    if no_neighbour_collision_flag is False:
        return False
    else:
        for neighbor, data in graph.nodes(data=True):
            # Koordinaten eines Knotens
            point = data["pos"]
            if point != edge_point_A and set(neighbor_nodes_collision_type) & set(data["node_type"]):
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

def check_collision(graph: nx.Graph(),
                    edge_point_A,
                    edge_point_B,
                    collision_flag: bool = True,
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
        graph ():
        node ():
    """
    if collision_flag is False:
        return False
    else:
        room_point_dict = {}
        for node, data in graph.nodes(data=True):
            if set(data["node_type"]) & set(collision_type_node):
                if data["ID_element"] not in room_point_dict:
                    room_point_dict[data["ID_element"]] = []
                room_point_dict[data["ID_element"]].append(data["pos"])
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
        snapped_line_with_tolerance = snapped_line
        for poly in polygons:
            if snapped_line_with_tolerance.crosses(poly):
                return True
        return False





def create_graph_nodes(graph: nx.Graph(),
                       points_list: list,
                       ID_element: str or list = None,
                       element_type: str = None,
                       node_type: str or list = None,
                       belongs_to_element: str or list = None,
                       belongs_to_storey: str = None,
                       direction: str = None,
                       color: str = "black",
                       tol_value: float = 0.0,
                       update_node: bool = True,
                       ):
    """
    Check ob der Knoten auf der Position schon existiert, wenn ja, wird dieser aktualisiert.
    room_points = [room_dict[room]["global_corners"] for room in room_dict]
    room_tup_list = [tuple(p) for points in room_points for p in points]
    building_points = tuple(room_tup_list)
    Args:
        graph (): Networkx Graphen
        points_list (): Punkte des Knotens in (x,y,z)
        color ():  Farbe des Knotens
        node_type (): Typ des Knotens
        ID_element (): ID des Elements
        belongs_to_element (): Element des Knotens gehört zu (Space)
        belongs_to_storey (): Element des Knotens gehört zur Etage ID
        direction (): Richtung des Knotens bzw. des Elements
        tol_value (): Abweichungen von der Position des Knoten
        update_node (): Wenn ein Knoten auf der Position bereits existiert, wird dieser aktualisiert/erweitert.

    Returns:
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
                            #'ID_element': attr_node_list(entry=ID_element, attr_list=data['ID_element']),
                            'ID_element': ID_element,
                            'element_type': attr_node_list(entry=element_type, attr_list=data['element_type']),
                            'node_type': attr_node_list(entry=node_type, attr_list=data['node_type']),
                            'color': color,
                            "belongs_to_element": attr_node_list(entry=belongs_to_element,
                                                                 attr_list=data['belongs_to_element']),
                            'belongs_to_storey': belongs_to_storey,
                            'direction': direction
                        })
                    created_nodes.append(node)
                    create_node = False
                    break
        if create_node:
            id_name = generate_unique_node_id(graph, floor_id=belongs_to_storey)
            graph.add_node(id_name,
                           pos=node_pos,
                           color=color,
                           #ID_element=check_attribute(attribute=ID_element),
                           ID_element=ID_element,
                           element_type=check_attribute(attribute=element_type),
                           node_type=check_attribute(node_type),
                           belongs_to_element=check_attribute(attribute=belongs_to_element),
                           belongs_to_storey=belongs_to_storey,
                           direction=direction)
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

