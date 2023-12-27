import json
import bim2sim
import networkx as nx
from networkx.algorithms.components import is_strongly_connected
from scipy.spatial import distance
from shapely.ops import nearest_points
from shapely.geometry import Polygon, Point, LineString
import numpy as np





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
                        directions: list,
                        working_node: nx.Graph().nodes(),
                        neighbor_node: nx.Graph().nodes(),
                        pos_neighbors: list,
                        neg_neighbors: list,
                        tol_value: float = 0.0) -> tuple[list, list]:
    """
    Zieht Grade Kanten in eine Richtung X, Y oder Z Richtung.
    Args:
        direction (): Sucht Kanten in X ,Y oder Z Richtung
        node_pos (): Position des Knoten, der verbunden werden soll.
        tol_value (): Toleranz bei kleinen Abweichungen in X,Y oder Z Richtungen
        neighbor_node (): Potentieller benachbarter Knoten
        pos_neighbors (): Liste von benachbarten Knoten in positiver Richtung
        neg_neighbors (): Liste von benachbarten Knoten in negativer Richtung
    Returns:
        pos_neighbors (): Liste von benachbarten Knoten in positiver Richtung
        neg_neighbors (): Liste von benachbarten Knoten in negativer Richtung

    """

    neighbor_pos = tuple(round(coord, 2) for coord in graph.nodes[neighbor_node]["pos"])
    node_pos = tuple(round(coord, 2) for coord in graph.nodes[working_node]["pos"])
    for i, direction in enumerate(["x", "y", "z"]):
        if directions[i]:
            diff = neighbor_pos[i] - node_pos[i]
            if diff < 0 and all(abs(neighbor_pos[j] - node_pos[j]) <= tol_value for j in range(3) if j != i):
                if direction not in pos_neighbors:
                    pos_neighbors[direction] = []
                pos_neighbors[direction].append(neighbor_node)
            elif diff > 0 and all(abs(neighbor_pos[j] - node_pos[j]) <= tol_value for j in range(3) if j != i):
                if direction not in neg_neighbors:
                    neg_neighbors[direction] = []
                neg_neighbors[direction].append(neighbor_node)
    return neg_neighbors, pos_neighbors


def create_graph_edges(graph: nx.Graph(),
                       connect_nodes: list,
                       edge_type: str,
                       color: str = "grey",
                       directions: list = [True, True, True],
                       tol_value: float = 0.0,
                       connect_floor_spaces_together: bool = False,
                       connect_types: bool = False,
                       connect_types_element: bool = False,
                       connect_ID_element: bool = False,
                       node_type: list = None,
                       connect_node_flag: bool = False,
                       to_connect_node_list: list = None,
                       disjoint_flag: bool = False,
                       intersects_flag: bool = True,
                       within_flag: bool = False,
                       all_node_flag: bool = False,
                       col_tol: float = 0.1,
                       collision_type_node: list = ["space"],
                       collision_flag: bool = True,
                       neighbor_nodes_collision_type: list = None,
                       no_neighbour_collision_flag: bool = False
                       ) -> nx.Graph():
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
        graph ():
        node_list ():
        edge_type ():
        graph_type ():
        directions (): Liste von Verlegungsrichtungen [x, y, z] für ein orthogonales Koordinatensystem
        tol_value ():
    Returns:
    """
    working_connection_nodes = []
    if connect_nodes and len(connect_nodes) > 0:
        # Sucht passende Knoten aus
        for working_node in connect_nodes:
            pos_neighbors = {}
            neg_neighbors = {}
            if connect_node_flag is True:
                for connect_node in to_connect_node_list:
                    if connect_node != working_node:
                        working_connection_nodes.append(connect_node)
            else:
                for neighbor, data in graph.nodes(data=True):
                    if neighbor != working_node:
                        if connect_ID_element and set(graph.nodes[working_node]["ID_element"]) & set(data["ID_element"]):
                            working_connection_nodes.append(neighbor)
                        if connect_floor_spaces_together and set(node_type) & set(graph.nodes[working_node]["type"]) and set(node_type) & set(data["type"]):
                            if graph.nodes[working_node]["floor_belongs_to"] == data["floor_belongs_to"] and set(graph.nodes[working_node]["element"]).isdisjoint(set(data["element"])):
                                working_connection_nodes.append(neighbor)
                        if connect_types and set(node_type) & set(data["type"]):
                            working_connection_nodes.append(neighbor)
                        if connect_types_element and set(node_type) & set(data["type"]) and set(graph.nodes[working_node]["element"]) & set(
                                    data["element"]):
                            working_connection_nodes.append(neighbor)
                        if all_node_flag is True:
                            working_connection_nodes.append(neighbor)

            # Gibt den nächsten Knoten zum Arbeitsknoten aus
            for neighbor_node in working_connection_nodes:
                neg_neighbors, pos_neighbors = sort_edge_direction(graph=graph,
                                    directions=directions,
                                    working_node=working_node,
                                    neighbor_node=neighbor_node,
                                    tol_value=tol_value,
                                    pos_neighbors=pos_neighbors,
                                    neg_neighbors=neg_neighbors)
            node_pos = graph.nodes[working_node]["pos"]
            node_list = None
            if pos_neighbors:
                node_list = pos_neighbors
            if neg_neighbors:
                node_list = neg_neighbors

            nearest_neighbour = \
                sorted(pos_neighbors, key=lambda p: distance.euclidean(graph.nodes[p]["pos"], node_pos))[0]
            if nearest_neighbour is not None and not graph.has_edge(working_node, nearest_neighbour) \
                    and not graph.has_edge(working_node, nearest_neighbour):
                if check_collision(graph,
                                    edge_point_A=graph.nodes[working_node]["pos"],
                                    edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                        disjoint_flag=disjoint_flag,
                                        collision_flag=collision_flag,
                                        intersects_flag=intersects_flag,
                                        within_flag=within_flag,
                                        tolerance=col_tol) is False:
                    if check_neighbour_nodes_collision(graph,
                                                            edge_point_A=graph.nodes[working_node]["pos"],
                                                            edge_point_B=graph.nodes[nearest_neighbour]["pos"],
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


            print(neg_neighbors)
            print(pos_neighbors)
            exit(0)

            """# Zieh Kanten zwischen den Knoten
                if pos_neighbors:
                    node_pos = G.nodes[node]["pos"]
                    nearest_neighbour = \
                        sorted(pos_neighbors, key=lambda p: distance.euclidean(graph.nodes[p]["pos"], node_pos))[0]
                    if nearest_neighbour is not None:
                        if not graph.has_edge(working_node, nearest_neighbour) and not graph.has_edge(working_node, nearest_neighbour):
                            if check_collision(G=graph,
                                               edge_point_A=graph.nodes[working_node]["pos"],
                                               edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                               disjoint_flag=disjoint_flag,
                                               collision_flag=collision_flag,
                                               intersects_flag=intersects_flag,
                                               within_flag=within_flag,
                                               tolerance=col_tol) is False:
                                if check_neighbour_nodes_collision(G=graph,
                                                                        edge_point_A=graph.nodes[working_node]["pos"],
                                                                        edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                                                        neighbor_nodes_collision_type=neighbor_nodes_collision_type,
                                                                        no_neighbour_collision_flag=no_neighbour_collision_flag) is False:
                                    length = abs(distance.euclidean(graph.nodes[nearest_neighbour]["pos"], node_pos))
                                    graph.add_edge(working_node,
                                                   nearest_neighbour,
                                                   color=color,
                                                   type=edge_type,
                                                   length=length)



            node_pos = graph.nodes[node]["pos"]
            if pos_neighbors:
                nearest_neighbour = \
                sorted(pos_neighbors, key=lambda p: distance.euclidean(graph.nodes[p]["pos"], node_pos))[0]
                if nearest_neighbour is not None:
                    if not graph.has_edge(node, nearest_neighbour) and not graph.has_edge(node, nearest_neighbour):
                        if check_collision(G=graph,
                                                edge_point_A=graph.nodes[node]["pos"],
                                                edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                                disjoint_flag=disjoint_flag,
                                                collision_flag=collision_flag,
                                                intersects_flag=intersects_flag,
                                                within_flag=within_flag,
                                                tolerance=col_tol) is False:
                            if check_neighbour_nodes_collision(G=graph,
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
                                               length=length)
            if neg_neighbors:
                nearest_neighbour = \
                sorted(neg_neighbors, key=lambda p: distance.euclidean(graph.nodes[p]["pos"], node_pos))[0]
                if nearest_neighbour is not None:
                    if not graph.has_edge(node, nearest_neighbour) and not graph.has_edge(node, nearest_neighbour):
                        if check_collision(G=graph,
                                                edge_point_A=graph.nodes[node]["pos"],
                                                edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                                disjoint_flag=disjoint_flag,
                                                intersects_flag=intersects_flag,
                                                within_flag=within_flag,
                                                tolerance=col_tol,
                                                collision_flag=collision_flag,
                                                collision_type_node=collision_type_node) is False:
                            if check_neighbour_nodes_collision(G=graph,
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
                                               length=length)"""
            return graph






    return graph

def check_neighbour_nodes_collision(G: nx.Graph(),
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


def get_type_node_attr(G: nx.Graph(),
                       type_node,
                       attr: str = "pos"):
    ergebnis_dict = {}
    for space_node, data in G.nodes(data=True):
        if set(type_node) & set(data["type"]):
            for ele in data["element"]:
                if ele in ergebnis_dict:
                    ergebnis_dict[ele].append(data[attr])
                else:
                    ergebnis_dict[ele] = [data[attr]]
    return ergebnis_dict

def check_collision(G: nx.Graph(),
                    edge_point_A,
                    edge_point_B,
                    collision_flag: bool = True,
                    intersects_flag: bool = False,
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
    if collision_flag is False:
        return False
    if intersects_flag is False:
        return False
    ele_dict = get_type_node_attr(G=G,
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
        if intersects_flag:
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
            for  node, data in graph.nodes(data=True):
                if abs(distance.euclidean(data['pos'], node_pos)) <= tol_value:
                    graph.nodes[node].update(
                        {
                            'ID_element': attr_node_list(entry=ID_element, attr_list=data['ID_element']),
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
                           ID_element=check_attribute(attribute=ID_element),
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

