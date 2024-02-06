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
from bim2sim.elements.bps_elements import ThermalZone, Door, Wall, Window, OuterWall, Floor, GroundFloor, Roof, \
    InnerWall
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.graph_functions import create_graph_nodes, \
    connect_nodes_via_edges, lay_direction, sort_connect_nodes, sort_edge_direction, project_nodes_on_building, \
    snapp_nodes_to_grid, check_graph, add_graphs, delete_edge_overlap, read_json_graph, save_networkx_json, \
    remove_nodes_by_attribute, return_attribute_element_type_nodes, remove_edges_by_attribute, \
    return_attribute_node_type_nodes, remove_edges_from_node, determine_centre_room
from bim2sim.utilities.visualize_graph_functions import visualzation_networkx_3D, visulize_networkx

# todo: Später wieder raus
from  bim2sim.plugins.PluginLCA.bim2sim_lca.task.create_heating_tree_base import CreateHeatingTreeBase
import matplotlib.pyplot as plt

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
    # reads = ('ifc_files',)
    # todo_
    touches = ('building_graph', 'node_type', 'snapped_node_type', 'snapped_edge_type',)
    final = True

    def __init__(self, playground):
        super().__init__(playground)

    def run(self, ifc_files, elements: dict, space_boundaries: dict):
        """
        Args:
        Returns:
        """
        # Node Settings
        node_type = "ifc_element_node"
        grid_type = "building"
        snapped_node_type = "snapped_node"
        snapped_edge_type = "snapped_edge"

        building_networkx_file = Path(self.playground.sim_settings.networkx_building_path)
        # self.sort_space_boundary(space_boundaries=space_boundaries)
        building_graph = None
        if self.playground.sim_settings.bldg_graph_from_json:
            building_graph = read_json_graph(building_networkx_file)
        else:
            # todo: node_type etc. als self. und keine übergabe
            if self.playground.sim_settings.distribution_layer_options == "Ifc_Wall":
                building_graph = self.create_building_graph_nx(elements=elements,
                                                               node_type=node_type,
                                                               grid_type=grid_type,
                                                               snapped_node_type=snapped_node_type)

            if self.playground.sim_settings.distribution_layer_options == "Space_Boundary":
                storey_space_boundaries = self.sort_space_boundary_in_storey(space_boundaries=space_boundaries)
                building_graph = self.create_building_graph_nx_with_space_boundary(storey_space_boundary_dict=storey_space_boundaries,
                                                                                   node_type=node_type,
                                                                                   grid_type=grid_type,
                                                                                   snapped_node_type=snapped_node_type,
                                                                                   snapped_edge_type=snapped_edge_type)




            save_networkx_json(building_graph, file=building_networkx_file)
        return building_graph, node_type, snapped_node_type,  snapped_edge_type,

    def create_building_graph_nx(self,
                                 elements,
                                 node_type:str = "ifc_element_node",
                                 grid_type:str = "building",
                                 snapped_node_type:str =  "snapped_node") -> nx.Graph():
        """
        Args:
            elements ():
        """
        self.logger.info("Create building graph from IFC-model in networkX with elements.")
        storey_graph_list = []
        all_st = sorted(filter_elements(elements, 'Storey'), key=lambda obj: obj.position[2])
        for i, storey in enumerate(all_st):
            self.logger.info(f"Build graph for storey {storey.guid}. "
                             f"storey number of {i}/{len(all_st)}")
            thermal_zones = storey.thermal_zones
            storey_graph = nx.Graph(grid_type=grid_type)


            for tz in thermal_zones:

                # Thermal Zones
                self.logger.info(f"Create graph for thermal zones {tz}.")
                # Create room nodes
                if isinstance(tz, ThermalZone):
                    storey_graph, created_nodes = create_graph_nodes(storey_graph,
                                                          points_list=tz.verts,
                                                          ID_element=tz.guid,
                                                          element_type=tz.ifc_type,
                                                          direction=lay_direction(tz.verts),
                                                          node_type=node_type,
                                                          belongs_to_room=tz.guid,
                                                          belongs_to_element=tz.guid,
                                                          belongs_to_storey=storey.guid,
                                                          room_area=tz.net_area.magnitude,
                                                          grid_type=storey_graph.graph["grid_type"])
                    # Give possible connections nodes and return in a dictionary
                    working_connection_nodes = sort_connect_nodes(storey_graph,
                                                                  connect_nodes=created_nodes,
                                                                  element_types=["IfcSpace"],
                                                                  node_with_same_ID_element_flag=True)
                    # Give the nearest node of the observation node in positive and negative direction
                    pos_negativ_neighbors = sort_edge_direction(storey_graph, working_connection_nodes)
                    # Connect room nodes with same ID
                    storey_graph = connect_nodes_via_edges(storey_graph,
                                                node_neighbors=pos_negativ_neighbors,
                                                element_type=tz.ifc_type,
                                                edge_type=node_type,
                                                grid_type=storey_graph.graph["grid_type"],
                                                collision_space_flag=False,
                                                no_neighbour_collision_flag=False)
                    #midpoint = determine_centre_room(tz.verts)






                bound_elements = tz.bound_elements
                for element in bound_elements:  # Create elements of space, bounded elements
                    if isinstance(element, (Floor, GroundFloor, Roof)):
                        continue
                    elif element and element.verts is not None:
                        # Wall
                        self.logger.info(f"Create graph for element {element} with ifc type {element.ifc_type}.")
                        if element.ifc.is_a('IfcWall'):
                            direction, points_list = self.center_points(global_points=element.verts)
                            storey_graph, created_nodes = create_graph_nodes(storey_graph,
                                                                  points_list=points_list,
                                                                  ID_element=element.guid,
                                                                  element_type=element.ifc_type,
                                                                  direction=direction,
                                                                  node_type=node_type,
                                                                  belongs_to_room=tz.guid,
                                                                  belongs_to_element=tz.guid,
                                                                  room_area=tz.net_area.magnitude,
                                                                  belongs_to_storey=storey.guid)
                            working_connection_nodes = sort_connect_nodes(storey_graph,
                                                                          connect_nodes=created_nodes,
                                                                          node_with_same_ID_element_flag=True)
                            # Give the nearest node of the observation node in positive and negative direction
                            pos_negativ_neighbors = sort_edge_direction(storey_graph, working_connection_nodes)
                            storey_graph = connect_nodes_via_edges(storey_graph,
                                                                node_neighbors=pos_negativ_neighbors,
                                                                edge_type=node_type,
                                                                element_type=element.ifc_type,
                                                                grid_type=storey_graph.graph["grid_type"],
                                                                   collision_space_flag=False,
                                                                   no_neighbour_collision_flag=False
                                                                   )
                        if any(element.ifc.is_a(type_name) for type_name in ['IfcWindow', 'IfcDoor']):
                            direction = lay_direction(element.verts)
                            points_list = element.verts
                            color = "orange"
                            # create nodes of the elements
                            storey_graph, created_nodes = create_graph_nodes(storey_graph,
                                                                              points_list=points_list,
                                                                              ID_element=element.guid,
                                                                              element_type=element.ifc_type,
                                                                              direction=direction,
                                                                              node_type=node_type,
                                                                              room_area=tz.net_area.magnitude,
                                                                              belongs_to_room=tz.guid,
                                                                              belongs_to_element=element.guid,
                                                                              belongs_to_storey=storey.guid)
                            print(tz.net_area.magnitude)
                            # Projeziert Knoten auf nächstes Polygon
                            storey_graph, project_node_list = project_nodes_on_building(storey_graph, project_node_list=created_nodes)
                            # Verbindet die Projezierten Knoten der Elemente miteinander
                            # Sucht Knoten mit der selben Element ID
                            working_connection_nodes = sort_connect_nodes(storey_graph,
                                                                          connect_nodes=project_node_list,
                                                                          node_with_same_ID_element_flag=True)
                            # Give the nearest node of the observation node in positive and negative direction
                            pos_negativ_neighbors = sort_edge_direction(storey_graph, working_connection_nodes)
                            storey_graph = connect_nodes_via_edges(storey_graph,
                                                        node_neighbors=pos_negativ_neighbors,
                                                        edge_type=node_type,
                                                        element_type=element.ifc_type,
                                                        grid_type=storey_graph.graph["grid_type"],
                                                        color=color,
                                                                   )
                            # Snapping - Algorithmus
                            storey_graph = snapp_nodes_to_grid(storey_graph,
                                                    bottom_z_flag=True,
                                                    snapped_node_type=snapped_node_type,
                                                    node_list=project_node_list,
                                                    edge_same_belongs_to_room_flag=True,
                                                   filter_edge_node_element_type=["IfcSpace"],
                                                    snapped_edge_type="room_snapped_edge")
            self.logger.info(f"Solve Overlapping edges for floor {storey.guid}.")
            storey_graph = delete_edge_overlap(storey_graph,
                                               edge_type=node_type)
            self.logger.info(f"Connect nodes with element_type attribute IfcWallStandardCase")
            connect_nodes = return_attribute_element_type_nodes(storey_graph, element_type=["IfcWallStandardCase"])
            working_connection_nodes = sort_connect_nodes(connect_nodes=connect_nodes,
                                                          graph=storey_graph,
                                                          node_with_same_element_types_flag=True,
                                                          element_types=["IfcWallStandardCase"])

            if len(working_connection_nodes) > 0:
                pos_negativ_neighbors = sort_edge_direction(storey_graph, working_connection_nodes)
                storey_graph = connect_nodes_via_edges(storey_graph,
                                                   node_neighbors=pos_negativ_neighbors,
                                                   element_type="IfcWallStandardCase",
                                                   edge_type=node_type,
                                                   grid_type=storey_graph.graph["grid_type"])

            for node in storey_graph.nodes():
                storey_graph, z_list, x_list, y_list = remove_edges_from_node(storey_graph, node=node)
            # Intersection of edges
            # Give the nearest node of the observation node in positive and negative direction
            self.logger.info(f"Snapp nodes with element_type attribute IfcWallStandardCase")
            connect_nodes = return_attribute_element_type_nodes(storey_graph, element_type=["IfcWallStandardCase"])
            storey_graph = snapp_nodes_to_grid(storey_graph,
                                    node_list=connect_nodes,
                                    snapped_node_type=snapped_node_type,
                                    filter_edge_node_element_type=["IfcWallStandardCase",
                                                                   f'{snapped_node_type}_IfcWallStandardCase',
                                                                   f'{snapped_node_type}_IfcWindow',
                                                                   f'{snapped_node_type}_IfcDoor'],
                                    element_type="IfcWallStandardCase",
                                    snapped_edge_type="snapped_edge",
                                    edge_same_element_type_flag=True,

                                    bottom_z_flag=False,
                                    top_z_flag=False,
                                    pos_x_flag=True,
                                    neg_x_flag=True,
                                    pos_y_flag=True,
                                    neg_y_flag=True)
            # Connect nodes (window and doors snapped nodes) of walls with snapping algorithm
            self.logger.info(f"Snapp nodes with element_type attribute snapped_node_type")
            connect_nodes = return_attribute_node_type_nodes(storey_graph,
                                                             node_type=[f'{snapped_node_type}_IfcWindow',
                                                                        f'{snapped_node_type}_IfcDoor'])
            storey_graph = snapp_nodes_to_grid(storey_graph,
                                               node_list=connect_nodes,
                                               snapped_node_type=snapped_node_type,
                                               edge_same_element_type_flag=True,
                                               filter_edge_node_element_type=["IfcWallStandardCase",
                                                                              f'{snapped_node_type}_IfcWallStandardCase',
                                                                              f'{snapped_node_type}_IfcWindow',
                                                                              f'{snapped_node_type}_IfcDoor'
                                                                              ],
                                               snapped_edge_type="snapped_edge",
                                               element_type="IfcWallStandardCase",
                                               bottom_z_flag=False,
                                               top_z_flag=False,
                                               pos_x_flag=True,
                                               neg_x_flag=True,
                                               pos_y_flag=True,
                                               neg_y_flag=True)
            storey_graph = remove_nodes_by_attribute(storey_graph, element_type=["IfcSpace"])
            storey_graph = remove_edges_by_attribute(storey_graph, edge_type="room_snapped_edge")
            """for node in storey_graph.nodes():
                storey_graph, z_list, x_list, y_list = remove_edges_from_node(storey_graph, node=node)"""

            storey_graph = check_graph(storey_graph, type=storey_graph.graph["grid_type"])
            storey_graph_list.append(storey_graph)
            #visulize_networkx(storey_graph, storey_graph.graph["grid_type"])
        building_graph = add_graphs(graph_list=storey_graph_list, grid_type=grid_type)
        #visulize_networkx(building_graph, building_graph.graph["grid_type"])
        #plt.show()
        return building_graph


    def center_points(self,
                      global_points: list,
                      offset: float = 0.5) -> tuple[str, list]:
        """

            Args:
                points ():
                offset (): Shifting the points by a certain offset.
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

    def sort_space_boundary_in_storey(self, space_boundaries):
        """

        Args:
            space_boundaries ():

        Returns:

        """
        space_boundaries_storey_dict = {}
        for space in space_boundaries:
            tz = space_boundaries[space].bound_thermal_zone
            storey = tz.storeys[0]
            if storey not in space_boundaries_storey_dict:
                space_boundaries_storey_dict[storey] = []
            if tz not in space_boundaries_storey_dict[storey]:
                space_boundaries_storey_dict[storey].append(tz)
        return space_boundaries_storey_dict

    def create_building_graph_nx_with_space_boundary(self,
                                                     storey_space_boundary_dict: dict,
                                                     node_type: str = "ifc_element_node",
                                                     snapped_node_type:str = "snapped_node",
                                                     grid_type: str = "building",
                                                     snapped_edge_type:str = "snapped_edge"):
        # bound_thermalZone: Schlafzimmer
        # bound_thermalZone.bound_elements: [Wall, Door,..]
         # list: space_boundaries.bound_neighbors.bound_element
        self.logger.info("Create building graph from IFC-model in networkX with space boundaries.")
        storey_graph_list = []
        for i, storey in enumerate(storey_space_boundary_dict):
            self.logger.info(f"Build graph for storey {storey.guid}. "
                             f"storey number of {i}/{len(storey_space_boundary_dict)}")
            thermal_zones = storey_space_boundary_dict[storey]
            storey_graph = nx.Graph(grid_type=grid_type)
            for tz in thermal_zones:
                self.logger.info(f"Create graph for thermal zones {tz}.")
                if isinstance(tz, ThermalZone):
                    storey_graph, created_nodes = create_graph_nodes(storey_graph,
                                                                 points_list=tz.verts,
                                                                 ID_element=tz.guid,
                                                                 element_type=tz.ifc_type,
                                                                 direction=lay_direction(tz.verts),
                                                                 node_type=node_type,
                                                                 belongs_to_room=tz.guid,
                                                                 belongs_to_element=tz.guid,
                                                                 belongs_to_storey=storey.guid,
                                                                 grid_type=storey_graph.graph["grid_type"])
                    # Give possible connections nodes and return in a dictionary
                    working_connection_nodes = sort_connect_nodes(storey_graph,
                                                                  connect_nodes=created_nodes,
                                                                  element_types=["IfcSpace"],
                                                                  node_with_same_ID_element_flag=True)
                    # Give the nearest node of the observation node in positive and negative direction
                    pos_negativ_neighbors = sort_edge_direction(storey_graph, working_connection_nodes)
                    # Connect room nodes with same ID

                    storey_graph = connect_nodes_via_edges(storey_graph,
                                                       node_neighbors=pos_negativ_neighbors,
                                                       element_type=tz.ifc_type,
                                                       edge_type=node_type,
                                                       grid_type=storey_graph.graph["grid_type"],
                                                       collision_space_flag=False,
                                                       no_neighbour_collision_flag=False
                                                       )
                bound_elements = tz.bound_elements
                for element in bound_elements:  # Create elements of space, bounded elements
                    if isinstance(element, (Floor, GroundFloor, Roof)):
                        continue
                    elif element and element.verts is not None:
                        # Wall
                        self.logger.info(f"Create graph for element {element} with ifc type {element.ifc_type}.")
                        if element.ifc.is_a('IfcWall'):
                            direction, points_list = self.center_points(global_points=element.verts)
                            storey_graph, created_nodes = create_graph_nodes(storey_graph,
                                                                         points_list=points_list,
                                                                         ID_element=element.guid,
                                                                         element_type=element.ifc_type,
                                                                         direction=direction,
                                                                         node_type=node_type,
                                                                         belongs_to_room=tz.guid,
                                                                         belongs_to_element=tz.guid,
                                                                         belongs_to_storey=storey.guid)
                            working_connection_nodes = sort_connect_nodes(storey_graph,
                                                                          connect_nodes=created_nodes,
                                                                          node_with_same_ID_element_flag=True)
                            # Give the nearest node of the observation node in positive and negative direction
                            pos_negativ_neighbors = sort_edge_direction(storey_graph, working_connection_nodes)
                            storey_graph = connect_nodes_via_edges(storey_graph,
                                                               node_neighbors=pos_negativ_neighbors,
                                                               edge_type=node_type,
                                                               element_type=element.ifc_type,
                                                               grid_type=storey_graph.graph["grid_type"],
                                                               collision_space_flag=False,
                                                               no_neighbour_collision_flag=False)

                        if any(element.ifc.is_a(type_name) for type_name in ['IfcWindow', 'IfcDoor']):
                            direction = lay_direction(element.verts)
                            points_list = element.verts
                            color = "orange"
                            # create nodes of the elements
                            storey_graph, created_nodes = create_graph_nodes(storey_graph,
                                                                         points_list=points_list,
                                                                         ID_element=element.guid,
                                                                         element_type=element.ifc_type,
                                                                         direction=direction,
                                                                         node_type=node_type,
                                                                         belongs_to_room=tz.guid,
                                                                         belongs_to_element=element.guid,
                                                                         belongs_to_storey=storey.guid)
                            # Projeziert Knoten auf nächstes Polygon
                            storey_graph, project_node_list = project_nodes_on_building(storey_graph,
                                                                                    project_node_list=created_nodes)

                            # Verbindet die Projezierten Knoten der Elemente miteinander
                            # Sucht Knoten mit der selben Element ID
                            working_connection_nodes = sort_connect_nodes(storey_graph,
                                                                          connect_nodes=project_node_list,
                                                                          node_with_same_ID_element_flag=True)

                            # Give the nearest node of the observation node in positive and negative direction
                            pos_negativ_neighbors = sort_edge_direction(storey_graph, working_connection_nodes)

                            storey_graph = connect_nodes_via_edges(storey_graph,
                                                               node_neighbors=pos_negativ_neighbors,
                                                               edge_type=node_type,
                                                               element_type=element.ifc_type,
                                                               grid_type=storey_graph.graph["grid_type"],
                                                               color=color)
                            # Snapping - Algorithmus
                            storey_graph = snapp_nodes_to_grid(storey_graph,
                                                           bottom_z_flag=True,
                                                           snapped_node_type=snapped_node_type,
                                                           node_list=project_node_list,
                                                           edge_same_belongs_to_room_flag=True,
                                                           filter_edge_node_element_type=["IfcSpace"],
                                                           snapped_edge_type=snapped_edge_type)
            # Intersection of edges
            self.logger.info(f"Solve Overlapping edges for floor {storey.guid}.")
            storey_graph = delete_edge_overlap(storey_graph, edge_type=node_type)
            self.logger.info(f"Connect nodes with element_type attribute IfcWallStandardCase")

            connect_nodes = return_attribute_element_type_nodes(storey_graph, element_type=["IfcWallStandardCase"])
            working_connection_nodes = sort_connect_nodes(connect_nodes=connect_nodes,
                                                          graph=storey_graph,
                                                          node_with_same_element_types_flag=True,
                                                          element_types=["IfcWallStandardCase"])
            pos_negativ_neighbors = sort_edge_direction(storey_graph, working_connection_nodes)
            storey_graph = connect_nodes_via_edges(storey_graph,
                                                   node_neighbors=pos_negativ_neighbors,
                                                   element_type="IfcWallStandardCase",
                                                   edge_type=node_type,
                                                   grid_type=storey_graph.graph["grid_type"])
            for node in storey_graph.nodes():
                storey_graph, z_list, x_list, y_list = remove_edges_from_node(storey_graph, node=node)
            # Give the nearest node of the observation node in positive and negative direction
            self.logger.info(f"Snapp nodes with element_type attribute IfcWallStandardCase")
            connect_nodes = return_attribute_element_type_nodes(storey_graph, element_type=["IfcWallStandardCase"])

            storey_graph = snapp_nodes_to_grid(storey_graph,
                                               node_list=connect_nodes,
                                               snapped_node_type=snapped_node_type,
                                               filter_edge_node_element_type=["IfcWallStandardCase",
                                                                   f'{snapped_node_type}_IfcWallStandardCase',
                                                                   f'{snapped_node_type}_IfcWindow',
                                                                   f'{snapped_node_type}_IfcDoor'],
                                               element_type="IfcWallStandardCase",
                                               snapped_edge_type=snapped_edge_type,
                                               edge_same_element_type_flag=True,
                                               bottom_z_flag=False,
                                               top_z_flag=False,
                                               pos_x_flag=True,
                                               neg_x_flag=True,
                                               pos_y_flag=True,
                                               neg_y_flag=True)
            # Connect nodes (window and doors snapped nodes) of walls with snapping algorithm
            self.logger.info(f"Snapp nodes with element_type attribute snapped_node_type")
            connect_nodes = return_attribute_node_type_nodes(storey_graph,
                                                             node_type=[f'{snapped_node_type}_IfcWindow',
                                                                        f'{snapped_node_type}_IfcDoor'])
            storey_graph = snapp_nodes_to_grid(storey_graph,
                                               node_list=connect_nodes,
                                               snapped_node_type=snapped_node_type,
                                               edge_same_element_type_flag=True,
                                               filter_edge_node_element_type=["IfcWallStandardCase",
                                                                              f'{snapped_node_type}_IfcWallStandardCase',
                                                                              f'{snapped_node_type}_IfcWindow',
                                                                              f'{snapped_node_type}_IfcDoor'
                                                                              ],
                                               snapped_edge_type=snapped_edge_type,
                                               element_type="IfcWallStandardCase",
                                               bottom_z_flag=False,
                                               top_z_flag=False,
                                               pos_x_flag=True,
                                               neg_x_flag=True,
                                               pos_y_flag=True,
                                               neg_y_flag=True)
            storey_graph = remove_nodes_by_attribute(storey_graph, element_type=["IfcSpace"])
            storey_graph = check_graph(storey_graph, type=storey_graph.graph["grid_type"])
            #visulize_networkx(storey_graph, storey_graph.graph["grid_type"])

            """building_graph = remove_edges_by_attribute(building_graph, edge_type=["snapped_edge_IfcSpace",
                                                                                  "snapped_edge_IfcDoor",
                                                                                  "snapped_edge_IfcWindow"])"""
            storey_graph_list.append(storey_graph)
        building_graph = add_graphs(graph_list=storey_graph_list, grid_type=grid_type)
        return building_graph






