import networkx as nx
from networkx.algorithms.components import is_strongly_connected
from scipy.spatial import distance
from shapely.ops import nearest_points
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import json
from shapely.geometry import Polygon, Point, LineString
from pathlib import Path

from bim2sim.tasks.base import ITask
from bim2sim.elements.bps_elements import ThermalZone, Door, Wall, Window, OuterWall, Floor, GroundFloor, Roof
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.graph_functions import create_graph_nodes, \
    connect_nodes_via_edges, lay_direction, sort_connect_nodes, sort_edge_direction, project_nodes_on_building, \
    connect_nodes_with_grid, check_graph, add_graphs, delete_edge_overlap
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
        if self.playground.sim_settings.bldg_graph_from_json:
            self.logger.info("Read building graph from json-file.")
            #heating_graph = read_json_graph()
        else:

            self.logger.info("Create building graph from IFC-model in networkX.")
            building_graph = self.create_building_graph_nx(elements)


        return building_graph,


    def read_json_graph(cls, file: Path):
        print(f"Read Building Graph from file {file}")
        with open(file, "r") as file:
            json_data = json.load(file)
            G = nx.node_link_graph(json_data)
        return G

    @staticmethod
    def read_buildings_json(file: Path = Path("buildings_json.json")):
        with open(file, "r") as datei:
            data = json.load(datei)
        return data

    def create_building_graph_nx(self, elements) -> nx.Graph():
        """
        Args:
            elements ():
        """
        floor_graph_list = []
        all_st = sorted(filter_elements(elements, 'Storey'), key=lambda obj: obj.position[2])

        for i, storey in enumerate(all_st):
            # Storey
            self.logger.info(f"Build graph for storey {storey.guid}.")
            G = nx.Graph(grid_type=f"Building_{storey.guid}")
            thermal_zones = storey.thermal_zones
            for tz in thermal_zones:
                # Thermal Zones
                self.logger.info(f"Create graph for thermal zones {tz}.")
                # Create room nodes
                if isinstance(tz, ThermalZone):
                    G, created_nodes = create_graph_nodes(G,
                                       points_list=tz.verts,
                                       ID_element=tz.guid,
                                       element_type=tz.ifc_type,
                                       direction=lay_direction(tz.verts),
                                       node_type=tz.ifc_type,
                                       belongs_to_room=tz.guid,
                                       belongs_to_element=storey.guid,
                                       belongs_to_storey=storey.guid)
                    # Give possible connections nodes and return in a dicitonary
                    working_connection_nodes = sort_connect_nodes(G,
                                       connect_nodes=created_nodes,
                                       connect_ID_element=True)
                    # Give the nearest node of the observation node in positive and negative direction
                    neg_neighbors, pos_neighbors = sort_edge_direction(G, working_connection_nodes)
                    # Connect room nodes with same ID
                    # todo: grid_type automatisieren
                    G = connect_nodes_via_edges(G,
                                                node_neighbors=neg_neighbors,
                                                edge_type=tz.ifc_type,
                                                grid_type="building")
                    G = connect_nodes_via_edges(G,
                                                node_neighbors=pos_neighbors,
                                                edge_type=tz.ifc_type,
                                                grid_type="building")

                # Create elements of space
                bound_elements = tz.bound_elements
                for element in bound_elements:
                    # bounded elements
                    if isinstance(element, (Floor, GroundFloor, Roof)):
                        continue
                    elif element and element.verts is not None:
                        # Wall
                        points_list = None
                        direction = None
                        self.logger.info(f"Create graph for element {element} with ifc type {element.ifc_type}.")
                        if element.ifc.is_a('IfcWall'):
                            direction, points_list = self.center_points(global_points=element.verts)
                            G, created_nodes = create_graph_nodes(G,
                                                                  points_list=points_list,
                                                                  ID_element=element.guid,
                                                                  element_type=element.ifc_type,
                                                                  direction=direction,
                                                                  node_type=element.ifc_type,
                                                                  belongs_to_room=tz.guid,
                                                                  belongs_to_element=tz.guid,
                                                                  belongs_to_storey=storey.guid)
                            working_connection_nodes = sort_connect_nodes(G,
                                                                          connect_nodes=created_nodes,
                                                                          connect_ID_element=True)
                            # Give the nearest node of the observation node in positive and negative direction
                            neg_neighbors, pos_neighbors = sort_edge_direction(G, working_connection_nodes)
                            G = connect_nodes_via_edges(G,
                                                        node_neighbors=neg_neighbors,
                                                        edge_type=element.ifc_type,
                                                        grid_type="building")
                            G = connect_nodes_via_edges(G,
                                                        node_neighbors=pos_neighbors,
                                                        edge_type=element.ifc_type,
                                                        grid_type="building")
                        elif any(element.ifc.is_a(type_name) for type_name in ['IfcWindow', 'IfcDoor']):
                            direction = lay_direction(element.verts)
                            points_list = element.verts
                            # Erstellt Knoten des Elements
                            G, created_nodes = create_graph_nodes(G,
                                                                  points_list=points_list,
                                                                  ID_element=element.guid,
                                                                  element_type=element.ifc_type,
                                                                  direction=direction,
                                                                  node_type=element.ifc_type,
                                                                  belongs_to_room=tz.guid,
                                                                  belongs_to_element=tz.guid,
                                                                  belongs_to_storey=storey.guid)
                            # Projeziert Knoten auf näches Polygon
                            G, project_node_list = project_nodes_on_building(G, project_node_list=created_nodes)

                            # Verbindet die Projezierten Knoten der Elemente miteinander
                            # Sucht Knoten mit der selben Element ID
                            working_connection_nodes = sort_connect_nodes(G,
                                                                          connect_nodes=project_node_list,
                                                                          connect_ID_element=True)

                            # Give the nearest node of the observation node in positive and negative direction
                            neg_neighbors, pos_neighbors = sort_edge_direction(G, working_connection_nodes)
                            G = connect_nodes_via_edges(G,
                                                        node_neighbors=neg_neighbors,
                                                        edge_type=element.ifc_type,
                                                        grid_type="building",
                                                        color="orange")
                            G = connect_nodes_via_edges(G,
                                                        node_neighbors=pos_neighbors,
                                                        edge_type=element.ifc_type,
                                                        grid_type="building",
                                                        color="orange")

                            # Snapping - Algorithmus
                            G = connect_nodes_with_grid(G,
                                                    node_list=project_node_list,
                                                    belongs_to_element=tz.guid,
                                                    element_belongs_to_element_type=tz.ifc_type)

            G= delete_edge_overlap(G)
            # Floor: Connect Spaces
            # Give possible connections nodes and return in a dicitonary
            room_floor_nodes = []
            for node, data in G.nodes(data=True):
                if data["belongs_to_storey"] == storey.guid and \
                        "IfcSpace" in data["element_type"]:
                    room_floor_nodes.append(node)

            working_connection_nodes = sort_connect_nodes(G,
                                                          element_types=["IfcSpace"],
                                                          connect_nodes=room_floor_nodes,
                                                          element_types_flag=True)
            # Give the nearest node of the observation node in positive and negative direction
            neg_neighbors, pos_neighbors = sort_edge_direction(G, working_connection_nodes)
            # todo: no_neighbour_collision_flag funktion anpassen
            G = connect_nodes_via_edges(G,
                                        color="red",
                                        node_neighbors=neg_neighbors,
                                        edge_type="space",
                                        grid_type="building",
                                        no_neighbour_collision_flag=True)
            G = connect_nodes_via_edges(G,
                                        color="red",
                                        node_neighbors=pos_neighbors,
                                        edge_type="space",
                                        grid_type="building",
                                        no_neighbour_collision_flag=True)
            check_graph(G, type=f"Floor_{i}_forward")

            # connect room nodes via edges

            floor_graph_list.append(G)
            #todo: Save json pro Etage
            #save_networkx_json(G, file=)
            visulize_networkx(G, type_grid="test")



            #visulize_networkx(G, type_grid="test")

        G = add_graphs(graph_list=floor_graph_list)
        visulize_networkx(G, type_grid="test")
        return G





    def center_points(self,
                      global_points: list,
                      offset: float = 0.5):
        """

            Args:
                points ():
                offset ():
            Returns:

            """
        x_min, y_min, z_min = np.min(global_points, axis=0)
        x_max, y_max, z_max = np.max(global_points, axis=0)
        x_diff, y_diff = x_max - x_min, y_max - y_min
        if x_diff > y_diff:
            direction = "x"
            y = y_diff * offset + y_min
            point_list = [(x_max, y, z_min), (x_min, y, z_min), (x_max, y, z_max), (x_min, y, z_max)]
        else:
            direction = "y"
            x = x_diff * offset + x_min
            point_list = [(x, y_max, z_min), (x, y_min, z_min), (x, y_max, z_max), (x, y_min, z_max)]

        return direction, point_list





































