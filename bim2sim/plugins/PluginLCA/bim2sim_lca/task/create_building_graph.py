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
from bim2sim.utilities.graph_functions import create_graph_nodes, connect_nodes_via_edges, create_graph_edges, lay_direction, sort_connect_nodes, sort_edge_direction
from bim2sim.utilities.visualize_graph_functions import visualzation_networkx_3D, visulize_networkx


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
    touches = ('building_graph',)
    final = True

    def __init__(self, playground):
        super().__init__(playground)
        self.sorted_elements = {}
        self.graph_storey_list = []
        #self.building_graph


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
        building_graph = nx.Graph()

        return building_graph,


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
                       belongs_to: str,
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
            self.logger.info(f"Build graph for storey {storey.guid}.")
            G = nx.Graph(grid_type=f"Building_{storey.guid}")
            thermal_zones = storey.thermal_zones
            for tz in thermal_zones:
                # Thermal Zones
                self.logger.info(f"Create graph for thermal zones {tz}.")
                # Create nodes
                G, created_nodes = create_graph_nodes(G,
                                   points_list=tz.verts,
                                   ID_element=tz.guid,
                                   element_type=tz.ifc_type,
                                   direction=lay_direction(tz.verts),
                                   node_type="space",
                                   belongs_to_element=storey.guid,
                                   belongs_to_storey=storey.guid)
                # Give possible connections nodes and return in a dicitonary
                working_connection_nodes = sort_connect_nodes(G,
                                   connect_nodes=created_nodes,
                                   connect_ID_element=True)
                # Give the nearest node of the oberservation node in positive and negative direction
                neg_neighbors, pos_neighbors = sort_edge_direction(G, working_connection_nodes)

                G = connect_nodes_via_edges(G,
                                            node_neighbors=neg_neighbors,
                                            edge_type="space",
                                            grid_type="building")
                G = connect_nodes_via_edges(G,
                                            node_neighbors=pos_neighbors,
                                            edge_type="space",
                                            grid_type="building")

                #visulize_networkx(G, type_grid="test")
                #  Create elements of space
                bound_elements = tz.bound_elements
                for element in bound_elements:
                    # bounded elements
                    if element and element.verts is not None:
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
        direction = lay_direction(element_data.verts)
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





























