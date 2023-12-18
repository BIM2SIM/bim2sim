import networkx as nx
from networkx.algorithms.components import is_strongly_connected
from scipy.spatial import distance
from shapely.ops import nearest_points
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import json
from shapely.geometry import Polygon, Point, LineString


from bim2sim.tasks.base import ITask
from bim2sim.elements.bps_elements import ThermalZone, Door, Wall, Window, OuterWall
from bim2sim.utilities.common_functions import filter_elements







class CreateBuildingGraph(ITask):
    """
    Reads the global points of the elements of an IFC model and transfers them to a graph network.

    Creates a graphen system based on an IFC model.
    The task reads the global coordinates of each element (room, wall, door, window) and returns 8 points
    in the form of a rectangle. Each room is created individually and its elements are added to the room.
    This is done separately for each floor.
    At the end, all floors are connected to each other via edges, so that an undirected,
    weighted graph is created.

    Args:
        elements
    Returns:
        Graphic G
    """

    reads = ('ifc_files', 'elements',)
    #reads = ('ifc_files',)
    touches = ('...',)
    final = True

    def __init__(self, playground):
        super().__init__(playground)
        self.sorted_elements = {}
        self.graph_storey_list = []


    def run(self, ifc_files,  elements: dict):
        """

        Args:


        Returns:

        """

        self.logger.info("Create building graph from IFC-model in networkX.")
        self.create_building_graph_nx(elements)
        #self.sort_room_to_floor(elements)
        #self.create_building_nx_network(elements)
        # self.sort_rooms_elements(elements)
        # print(self.spaces_dict)

        return elements,


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

                       belongs_to: str,
                       room_ID: str,
                       edge_type: str,
                       grid_type: str,
                       node_type: list,
                       floor_belongs_to: str,
                       offset: float = 0.5,
                       tol_value: float = 0.0,
                       color_nodes: str = "grey",
                       color_edges: str = "grey",
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
            G, center_node = self.create_graph_nodes(G=G,
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
        print(node_list)
        G = self.create_graph_edges(G=G,
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


    def create_building_graph_nx(self, elements):
        """

        Args:
            elements ():
        """
        all_st = filter_elements(elements, 'Storey')
        for i, storey in enumerate(all_st):
            # Storey
            self.logger.info(f"Build graph for storey {storey}.")
            G = nx.Graph(grid_type=f"Building_{storey.guid}")
            thermal_zones = storey.thermal_zones
            for tz in thermal_zones:
                # Thermal Zones
                self.logger.info(f"Create graph for space {tz}.")
                self.create_space_grid(G=G,
                                       element_data=tz,
                                       color="grey",
                                       node_type="thermalzone",
                                       edge_type="space",
                                       grid_type="space",
                                       floor_belongs_to=storey.guid,
                                       connect_element_together=True,
                                       connect_floors=False,
                                       nearest_node_flag=True,
                                       connect_node_flag=False,
                                       intersects_flag=False)
                bound_elements = tz.bound_elements
                for element in bound_elements:
                    # bounded elements
                    if element is not None and element.verts is not None:
                        # Wall
                        if element.ifc.is_a('IfcWall'):
                            G, center_wall = self.center_element(G=G,
                                                                 global_corners=element.verts,
                                                                 belongs_to=tz.guid,
                                                                 room_ID=element,
                                                                 edge_type="wall",
                                                                 grid_type="wall",
                                                                 node_type=["wall"],
                                                                 floor_belongs_to=storey.guid)



                        if any(element.ifc.is_a(type_name) for type_name in ['IfcWall', 'IfcDoor', 'IfcWindow']):
                            pass





    def lay_direction(self, verts):
        x_coords = [point[0] for point in verts]
        y_coords = [point[1] for point in verts]
        x_diff = np.max(x_coords) - np.min(x_coords)
        y_diff = np.max(y_coords) - np.min(y_coords)
        if x_diff > y_diff:
            direction = "x"
        else:
            direction = "y"
        return direction








    def create_graph_nodes(self,
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


    def check_attribute(self, attribute):
        attr = attribute
        if isinstance(attribute, str):
            attr = [attribute]
        if isinstance(attribute, list):
            attr = attribute
        return attr

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








    def room_element_position(self, ifc_files):
        """

        Args:
            ifc_files ():

        Returns:

        """
        model = ifcopenshell.open(ifc_files)
        for space in model.by_type("IfcSpace"):
            global_corners, z_min = self.occ_core_global_points(element=space)
            x_coords = [point[0] for point in global_corners]
            y_coords = [point[1] for point in global_corners]
            x_diff = np.max(x_coords) - np.min(x_coords)
            y_diff = np.max(y_coords) - np.min(y_coords)
            if x_diff > y_diff:
                direction = "x"
            else:
                direction = "y"
            self.spaces_dict[space.GlobalId] = {"type": "space",
                                               "number": space.Name,
                                               "Name": space.LongName,
                                               "id": space.id(),
                                               "height": z_min,
                                               "direction": direction,
                                               "global_corners": global_corners,
                                               "room_elements": []
                                               }
            room_elements = self.related_object_space(room=space)
            self.spaces_dict[space.GlobalId]["room_elements"] = room_elements
        return self.spaces_dict

    def related_object_space(self, room):
        """

        Args:
            room ():

        Returns:

        """
        room_elements = []
        element_dict = {}
        for boundary_element in self.model.by_type("IfcRelSpaceBoundary"):
            if boundary_element.RelatingSpace == room:
                room_elements.append(boundary_element.RelatedBuildingElement)
        for element in room_elements:
            if element is not None:
                if element.is_a("IfcWall"):
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
                                                      "height": z_min,
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







    def create_space_grid(self,
                          G: nx.Graph(),
                          element_data,
                          grid_type,
                          edge_type,
                          node_type,
                          floor_belongs_to,
                          color: str = "grey",
                          tol_value: float = 0.0,
                          update_node: bool = False,
                          direction_x: bool = True,
                          direction_y: bool = True,
                          direction_z: bool = True,
                          connect_element_together: bool = True,
                          connect_floors: bool = False,
                          nearest_node_flag: bool = True,
                          connect_node_flag: bool = False,
                          disjoint_flag: bool = False,
                          intersects_flag: bool = True,
                          within_flag: bool = False,
                          col_tol: float = 0.1,
                          collision_type_node: list = ["space"] ):

        room_global_corners = element_data.verts
        room_belong_to = floor_belongs_to
        direction = self.lay_direction(element_data.verts)
        room_ID = element_data.guid
        type_node = node_type
        space_nodes = []

        # Erstellt Knoten für einen Space/Wand
        if room_global_corners is not None:
            for i, points in enumerate(room_global_corners):
                G, nodes = self.create_graph_nodes(G=G,
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
            G = self.create_graph_edges(G=G,
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


    def create_graph_edges(self,
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

    def sort_rooms_elements(self, elements: dict):
        all_tz = filter_elements(elements, 'ThermalZone')
        for tz in all_tz:
            self.spaces_dict[tz.guid] = {"type": tz.ifc_type,
                                       "name": tz,
                                        "storey": tz.storeys,
                                       "id": tz.zone_name,
                                       "height": tz.height,
                                       "direction": self.lay_direction(tz.verts),
                                       "global_corners": tz.verts,
                                       "room_elements": []
                                           }
            bound_elements = tz.bound_elements
            element_dict = {}
            for element in bound_elements:
                if element is not None:
                    if any(element.ifc.is_a(type_name) for type_name in ['IfcWall', 'IfcDoor', 'IfcWindow']):
                        element_dict[element.guid] = {"type": element.ifc_type,
                                                      "name": element,
                                                      "id": element.name,
                                                      "global_corners": element.verts,
                                                      "belongs_to": tz.guid,
                                                      "direction": self.lay_direction(element.verts)}
            self.spaces_dict[tz.guid]["room_elements"] = element_dict

    def sort_room_to_floor(self, elements):
        all_st = filter_elements(elements, 'Storey')
        for storey in all_st:
            self.floor_dict[storey.guid] = {"type": storey.ifc_type,
                                            "Name": storey.name,
                                            #"height": storey.Elevation,
                                            "rooms": []}
            rooms_on_floor = {}
            thermal_zones = storey.thermal_zones
            for tz in thermal_zones:
                rooms_on_floor[tz.guid] = {"type": tz.ifc_type,
                                       "name": tz,
                                        "storey": tz.storeys,
                                       "id": tz.zone_name,
                                       "height": tz.height,
                                       "direction": self.lay_direction(tz.verts),
                                       "global_corners": tz.verts,
                                       "room_elements": []
                                           }
                bound_elements = tz.bound_elements
                element_dict = {}
                for element in bound_elements:
                    if element is not None:
                        if any(element.ifc.is_a(type_name) for type_name in ['IfcWall', 'IfcDoor', 'IfcWindow']):
                            element_dict[element.guid] = {"type": element.ifc_type,
                                                          "name": element,
                                                          "id": element.name,
                                                          "global_corners": element.verts,
                                                          "belongs_to": tz.guid,
                                                          "direction": self.lay_direction(element.verts)}
                rooms_on_floor[tz.guid]["room_elements"] = element_dict
            self.floor_dict[storey.guid]["rooms"] = rooms_on_floor
        print(self.floor_dict)
        print("test")
        print("hallo")
        exit(0)

    def create_building_nx_network(self, elements):
        """
        Args:
            elements ():
        """
        print("Creates nodes for each room independently")
        print(self.spaces_dict)
        exit(0)
        # Zuerst Sortieren Räume und deren Element
        for i, floor_id in enumerate(elements):
            G = nx.Graph(grid_type="building")
            element = elements.get(floor_id)

            if isinstance(element, ThermalZone):
                #print(element[floor_id])

                pass
                #print(floor_id)
                #print((elements[floor_id]))




            """for room in self.floor_dict_data[floor_id]["rooms"]:
                room_data = self.floor_dict_data[floor_id]["rooms"][room]
                room_elements = room_data["room_elements"]
                G, space_nodes = self.create_space_grid(G=G,
                                                        room_data=room_data,
                                                        room_ID=room,
                                                        color="grey",
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
                                                        intersects_flag=False)"""



