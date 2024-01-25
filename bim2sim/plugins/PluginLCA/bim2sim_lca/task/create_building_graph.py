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
from networkx.readwrite import json_graph

import bim2sim
from bim2sim.tasks.base import ITask
from bim2sim.elements.bps_elements import ThermalZone, Door, Wall, Window, OuterWall, Floor, GroundFloor, Roof, InnerWall
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.graph_functions import create_graph_nodes, \
    connect_nodes_via_edges, lay_direction, sort_connect_nodes, sort_edge_direction, project_nodes_on_building, \
    connect_nodes_with_grid, check_graph, add_graphs, delete_edge_overlap, read_json_graph, save_networkx_json
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

    reads = ('ifc_files', 'elements', 'space_boundaries')
    #reads = ('ifc_files',)
    touches = ('building_graph',)
    final = True

    def __init__(self, playground):
        super().__init__(playground)




    def run(self, ifc_files,  elements: dict, space_boundaries: dict):
        """
        Args:
        Returns:
        """
        building_networkx_file = Path(self.playground.sim_settings.networkx_building_path)
        #self.sort_space_boundary(space_boundaries=space_boundaries)
        building_graph = None
        if self.playground.sim_settings.bldg_graph_from_json:
            building_graph = read_json_graph(building_networkx_file)
        else:
            if self.playground.sim_settings.distribution_layer_options == "Ifc_Wall":
                building_graph = self.create_building_graph_nx(elements)
            if self.playground.sim_settings.distribution_layer_options == "Space_Boundary":
                building_graph = self.sort_space_boundary(space_boundaries)
            save_networkx_json(building_graph, file=building_networkx_file)
        print(building_graph.graph["grid_type"])
        visulize_networkx(building_graph, building_graph.graph["grid_type"])
        return building_graph,






    def create_building_graph_nx(self, elements) -> nx.Graph():
        """
        Args:
            elements ():
        """
        self.logger.info("Create building graph from IFC-model in networkX.")
        floor_graph_list = []
        all_st = sorted(filter_elements(elements, 'Storey'), key=lambda obj: obj.position[2])

        for i, storey in enumerate(all_st):
            # Storey
            self.logger.info(f"Build graph for storey {storey.guid}.")
            #G = nx.Graph(grid_type=f"building_{storey.guid}")
            G = nx.Graph(grid_type=f"building")
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
                                       node_type="element",
                                       belongs_to_room=tz.guid,
                                       belongs_to_element=storey.guid,
                                       belongs_to_storey=storey.guid,
                                       grid_type=G.graph["grid_type"])
                    # Give possible connections nodes and return in a dictionary
                    working_connection_nodes = sort_connect_nodes(G,
                                                                  connect_nodes=created_nodes,
                                                                  same_ID_element_flag=True)
                    # Give the nearest node of the observation node in positive and negative direction
                    neg_neighbors, pos_neighbors = sort_edge_direction(G, working_connection_nodes)
                    # Connect room nodes with same ID
                    G = connect_nodes_via_edges(G,
                                                node_neighbors=neg_neighbors,
                                                edge_type=tz.ifc_type,
                                                collision_flag=True,
                                                grid_type=G.graph["grid_type"])
                    G = connect_nodes_via_edges(G,
                                                node_neighbors=pos_neighbors,
                                                edge_type=tz.ifc_type,
                                                grid_type=G.graph["grid_type"])
                    visulize_networkx(G, G.graph["grid_type"])
                """# Create elements of space
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

                        if element.ifc.is_a('IfcWall') and self.playground.sim_settings.distribution_layer_options == "Ifc_Wall":
                            direction, points_list = self.center_points(global_points=element.verts)
                            G, created_nodes = create_graph_nodes(G,
                                                                  points_list=points_list,
                                                                  ID_element=element.guid,
                                                                  element_type=element.ifc_type,
                                                                  direction=direction,
                                                                  node_type="element",
                                                                  belongs_to_room=tz.guid,
                                                                  belongs_to_element=tz.guid,
                                                                  belongs_to_storey=storey.guid)
                            working_connection_nodes = sort_connect_nodes(G,
                                                                          connect_nodes=created_nodes,
                                                                          same_ID_element_flag=True)
                            # Give the nearest node of the observation node in positive and negative direction
                            #todo: grid_type automatisieren
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
                                                                  node_type="element",
                                                                  belongs_to_room=tz.guid,
                                                                  belongs_to_element=tz.guid,
                                                                  belongs_to_storey=storey.guid)
                            # Projeziert Knoten auf näches Polygon
                            G, project_node_list = project_nodes_on_building(G, project_node_list=created_nodes)

                            # Verbindet die Projezierten Knoten der Elemente miteinander
                            # Sucht Knoten mit der selben Element ID
                            working_connection_nodes = sort_connect_nodes(G,
                                                                          connect_nodes=project_node_list,
                                                                          same_ID_element_flag=True)

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
                                                        bottom_z_flag=True,
                                                        node_list=project_node_list,
                                                        element_belongs_to_space=True,
                                                        snapped_nodes_in_space=True)"""

            # Intersection of edges
            self.logger.info(f"Solve Overlapping edges for floor {storey.guid}.")
            G = delete_edge_overlap(G)
            # Connect nodes of walls with snapping algorithm
            snapped_nodes = []
            for node, data in G.nodes(data=True):
                element_type_list = ["IfcWallStandardCase", "snapped_node"]
                if set(data["element_type"]) & set(element_type_list) and data["belongs_to_storey"] == storey.guid:
                    snapped_nodes.append(node)
            G = connect_nodes_with_grid(G,
                                        node_list=snapped_nodes,
                                        all_edges_flag=True,
                                        color="red",
                                        pos_x_flag=True,
                                        neg_x_flag=True,
                                        pos_y_flag=True,
                                        neg_y_flag=True)

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

            G = connect_nodes_via_edges(G,
                                        #color="red",
                                        node_neighbors=neg_neighbors,
                                        edge_type="space",
                                        grid_type="building",
                                        no_neighbour_collision_flag=True)
            G = connect_nodes_via_edges(G,
                                        #color="red",
                                        node_neighbors=pos_neighbors,
                                        edge_type="space",
                                        grid_type="building",
                                        no_neighbour_collision_flag=True)
            check_graph(G, type=f"Floor_{i}_forward")

            # todo: connect wall nodes via edges

            floor_graph_list.append(G)


        G = add_graphs(graph_list=floor_graph_list, grid_type="building")
        check_graph(G, type=f"Floor_{i}_forward")
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


    def sort_space_boundary(self, space_boundaries):
        # bound_thermalZone: Schlafzimmer
        # bound_thermalZone.bound_elements: [Wall, Door,..]
        G = nx.Graph(grid_type=f"Building")
        for space in space_boundaries:
            thermalzone = space_boundaries[space].bound_thermal_zone
            bound_elements = thermalzone.bound_elements
            for element in bound_elements:
                storey = element.storeys[0]
                if isinstance(element, (OuterWall, InnerWall)):
                    direction, points_list = self.center_points(global_points=element.verts)
                    G, created_nodes = create_graph_nodes(G,
                                                          points_list=points_list,
                                                          ID_element=element.guid,
                                                          element_type=element.ifc_type,
                                                          direction=direction,
                                                          node_type="element",
                                                          belongs_to_room=space,
                                                          belongs_to_element=element.guid,
                                                          belongs_to_storey=storey.guid)
                    working_connection_nodes = sort_connect_nodes(G,
                                                                  connect_nodes=created_nodes,
                                                                  connect_ID_element=True)
                    # Give the nearest node of the observation node in positive and negative direction
                    # todo: grid_type automatisieren
                    neg_neighbors, pos_neighbors = sort_edge_direction(G, working_connection_nodes)
                    G = connect_nodes_via_edges(G,
                                                node_neighbors=neg_neighbors,
                                                edge_type=element.ifc_type,
                                                grid_type="building")
                    G = connect_nodes_via_edges(G,
                                                node_neighbors=pos_neighbors,
                                                edge_type=element.ifc_type,
                                                grid_type="building")
                if isinstance(element, (Door, Window)):
                    direction = lay_direction(element.verts)
                    points_list = element.verts
                    # Erstellt Knoten des Elements

                    G, created_nodes = create_graph_nodes(G,
                                                          points_list=points_list,
                                                          ID_element=element.guid,
                                                          element_type=element.ifc_type,
                                                          direction=direction,
                                                          node_type="element",
                                                          belongs_to_room=space,
                                                          belongs_to_element=element.guid,
                                                          belongs_to_storey=storey.guid)

                    # Projeziert Knoten auf nächste Polygon
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
                                                bottom_z_flag=True,
                                                node_list=project_node_list,
                                                element_belongs_to_space=True,
                                                snapped_nodes_in_space=True)

        visulize_networkx(G, type_grid="test")


        # SpaceBoundary/ BoundThermalzone/Bound_Element
        # bound_thermal_zone
        # bound_elements
    #


































