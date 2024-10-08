from pathlib import Path
import json
import numpy as np
import networkx as nx
from networkx.readwrite import json_graph
from networkx.utils import pairwise
from networkx.algorithms.components import is_strongly_connected
import matplotlib
#matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, Point, LineString
from scipy.spatial import distance
from colorama import *
from pint import Quantity
import itertools
from itertools import chain
import math
import pandas as pd
import ifcopenshell.geom
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.gp import gp_Pnt
from OCC.Core.TopAbs import TopAbs_IN, TopAbs_ON

from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements



class CreateBuildingAndHeatingGraph(ITask):
    """Creates a heating circle out of an ifc model"""

    reads = ('floor_dict', 'elements', 'heat_demand_dict')
    touches = ('building_graph', 'heating_graph')


    def run(self, floor_dict, elements, heat_demand_dict):

        self.hydraulic_system_directory = Path(self.paths.export / 'hydraulic system')

        self.floor_dict = floor_dict
        self.elements = elements
        self.heat_demand_dict = heat_demand_dict

        self.heating_graph_start_point = (self.playground.sim_settings.startpoint_heating_graph_x_axis,
                                          self.playground.sim_settings.startpoint_heating_graph_y_axis,
                                          self.playground.sim_settings.startpoint_heating_graph_z_axis)

        self.temperature_forward = self.playground.sim_settings.t_forward * ureg.kelvin
        self.temperature_backward = self.playground.sim_settings.t_backward * ureg.kelvin
        self.temperature_room = self.playground.sim_settings.t_room * ureg.kelvin

        self.one_pump_flag = self.playground.sim_settings.one_pump_flag

        if self.playground.sim_settings.generate_new_building_graph:
            self.logger.info("Create building network graph")
            building_graph = self.create_building_graph(grid_type="building",
                                                            color="black",
                                                            tol_value=0.0)
            self.logger.info("Finished creating building network graph")

        else:
            self.logger.info("Load building network graph")
            building_graph = self.load_json_graph(filename="network_building.json")
            self.logger.info("Finished loading building network graph")


        if self.playground.sim_settings.generate_new_heating_graph:
            self.logger.info("Create heating network graph")
            if self.playground.sim_settings.heat_delivery_type == "UFH":
                type_delivery = ["door"]
            elif self.playground.sim_settings.heat_delivery_type == "Radiator":
                type_delivery = ["window"]

            heating_graph = self.create_heating_graph(graph=building_graph,
                                                      type_delivery=type_delivery,
                                                      grid_type="forward",
                                                      one_pump_flag=self.one_pump_flag)
            self.logger.info("Finished creating heating network graph")
        else:
            self.logger.info("Load heating network graph")
            heating_graph = self.load_json_graph(filename="heating_circle.json")
            self.logger.info("Finished loading heating network graph")
            
        return building_graph, heating_graph



    def load_json_graph(self, filename: str):
        filepath = self.hydraulic_system_directory / filename
        self.logger.info(f"Read {filename} Graph from file {filepath}")
        with open(filepath, "r") as file:
            json_data = json.load(file)
            graph = nx.node_link_graph(json_data)
        return graph

    def write_json_graph(self, graph, filename):
        filepath = self.hydraulic_system_directory / filename
        self.logger.info(f"Read {filename} Graph from file {filepath}")
        data = json_graph.node_link_data(graph)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)


    def reduce_path_nodes(self, graph, color, start_nodes: list, end_nodes: list):
        graph = graph.copy()
        deleted_nodes = True  # Flag, um die Iteration neu zu starten

        while deleted_nodes:
            deleted_nodes = False
            for start in start_nodes:
                for end in end_nodes:
                    path = nx.shortest_path(G=graph, source=start, target=end)  # Annahme: Pfad ist bereits gegeben
                    restart_inner_loop = False
                    for i in range(1, len(path) - 1):
                        node1 = path[i - 1]
                        node2 = path[i]
                        node3 = path[i + 1]
                        if graph.degree(node2) > 2:
                            continue
                        elif self.is_linear_path(graph, node1, node2, node3) and node2 not in start_nodes and node2 \
                                not in end_nodes:
                            # Entferne den Knoten node2
                            # Erstelle eine neue Kante zwischen node1 und node3
                            length = abs(distance.euclidean(graph.nodes[node1]["pos"], graph.nodes[node3]["pos"]))
                            graph.add_edge(node1,
                                       node3,
                                       color=color,
                                       type=graph.nodes[node1]["direction"],
                                       grid_type=graph.nodes[node1]["direction"],
                                       direction=graph.nodes[node1]["direction"],
                                       length=length)
                            graph.remove_node(node2)
                            deleted_nodes = True  # Setze das Flag auf True, um die Iteration neu zu starten
                            restart_inner_loop = True  # Setze das Flag auf True, um die innere Schleife neu zu starten
                            break  # Beende die innere Schleife

                    if restart_inner_loop:
                        break  # Starte die innere Schleife neu

        return graph

    def is_linear_path(self, graph, node1, node2, node3):
        # Überprüfe, ob die Kanten gradlinig verlaufen
        x1, y1, z1 = graph.nodes[node1]["pos"]
        x2, y2, z2 = graph.nodes[node2]["pos"]
        x3, y3, z3 = graph.nodes[node3]["pos"]
        # Z - Achse
        if x2 == x1 == x3 and y1 == y2 == y3:
            return True
        # X - Achse
        if z2 == z1 == z3 and y1 == y2 == y3:
            return True
        # Y - Achse
        if z2 == z1 == z3 and x1 == x2 == x3:
            return True
        else:
            return False

    def get_UFH_nodes(self, graph, doors, heat_delivery_dict):

        door_dict = {}
        door_dict_lower_z_value = {}
        for door_id, door in doors.items():
            door_dict[door_id] = {}
            for i in range(len(door)):
                door_dict[door_id][door[i]] = graph.nodes[door[i]]

        # Get only bottom door nodes
        for door_id, door_nodes in door_dict.items():
            door_dict_lower_z_value[door_id] = {}
            z_values = []
            for node_id, node in door_nodes.items():
                z_values.append(node['pos'][2])
            z_value = min(z_values)
            for node_id, node in door_nodes.items():
                if node['pos'][2] == z_value:
                    door_dict_lower_z_value[door_id][node_id] = node

        door_dict_new = {}
        to_be_checked = {}

        for door_id, door_nodes in door_dict_lower_z_value.items():
            neighbouring_rooms = {}
            # Sort door nodes by room assignment
            for node_id, node in door_nodes.items():
                room_id = node['belongs_to'][0]
                if room_id not in neighbouring_rooms:
                    neighbouring_rooms[room_id] = {}
                    neighbouring_rooms[room_id]["usage"] = self.elements[room_id].usage
                    neighbouring_rooms[room_id]["door nodes"] = []
                neighbouring_rooms[room_id]["door nodes"].append(node_id)

            # Check if door borders to 2 zones
            if len(neighbouring_rooms) != 2:
                assert KeyError(f"Door {door_id} belongs to more or less than 2 rooms!")

            # Pass on door nodes if nodes belong to heated room (All rooms but traffic zones are heated)
            traffic_area_count = sum(1 for room in neighbouring_rooms.values() if room['usage'] == 'Traffic area')
            if traffic_area_count == 0:
                for room_id, room in neighbouring_rooms.items():
                    to_be_checked[room_id] = room["door nodes"]
            elif traffic_area_count == 1:
                for room_id, room in neighbouring_rooms.items():
                    if room['usage'] != 'Traffic area' and room_id not in door_dict_new.keys():
                        door_dict_new[room_id] = room["door nodes"]

        for room_id, door_nodes in to_be_checked.items():
            if room_id not in door_dict_new.keys():
                door_dict_new[room_id] = door_nodes

        # Check if max heat flow per room area is reached in rooms -> extra radiator in respective rooms
        heat_delivery_extra_radiators = {}
        for room_id, door_nodes in door_dict_new.items():
            heat_flow_per_area = (heat_delivery_dict[room_id]['Q_flow_operation'] * 1000 /
                                  heat_delivery_dict[room_id]['room_area'])
            if heat_flow_per_area > self.playground.sim_settings.ufh_max_heat_flow_per_area:
                heat_delivery_extra_radiators[room_id] = {}
                heat_delivery_extra_radiators[room_id]['Q_flow_operation'] = heat_flow_per_area - self.playground.sim_settings.ufh_max_heat_flow_per_area
                heat_delivery_extra_radiators[room_id]['norm_indoor_temperature'] = heat_delivery_dict[room_id]['norm_indoor_temperature']
                heat_delivery_extra_radiators[room_id]['z_value'] = min([node[2] for node in door_nodes])

        return door_dict_new, heat_delivery_extra_radiators

    def get_radiator_nodes(self, graph, windows, heat_delivery_dict):
        # Get maximal possible radiator power
        radiator_dict = self.read_radiator_material_excel(
                filename=self.playground.sim_settings.hydraulic_components_data_file_path,
                sheet_name=self.playground.sim_settings.hydraulic_components_data_file_radiator_sheet)
        max_radiator_length = 3 #Meter
        Q_radiator_max = max_radiator_length * max(values['Normwärmeleistung'].magnitude for key, values in
                                                 radiator_dict.items()
                                                                        if values)/1000


        room_dict = {}
        needed_windows_dict = {}

        for floor in self.floor_dict.values():
            for room_id, room in floor['rooms'].items():
                if room_id in heat_delivery_dict.keys():

                    log_mean_temperature_operation = round(
                        self.logarithmic_mean_temperature(forward_temperature=self.temperature_forward,
                                                          backward_temperature=self.temperature_backward,
                                                          room_temperature=heat_delivery_dict[room_id][
                                                              "norm_indoor_temperature"]), 2)

                    log_mean_temperature_norm = round(self.logarithmic_mean_temperature(forward_temperature=75,
                                                                                        backward_temperature=65,
                                                                                        room_temperature=20), 2)
                    Q_flow_design = self.heat_flow_design_radiator(
                        log_mean_temperature_operation=log_mean_temperature_operation,
                        heating_exponent=1.3,
                        log_mean_temperature_norm=log_mean_temperature_norm,
                        Q_heat_operation=heat_delivery_dict[room_id]["Q_flow_operation"])

                    needed_windows_dict[room_id] = math.ceil(Q_flow_design / Q_radiator_max)

                    room_dict[room_id] = {}

                    # Get wall elements per room
                    x_room = [x[0] for x in room['global_corners']]
                    y_room = [y[1] for y in room['global_corners']]
                    for wall_id, wall in room["room_elements"].items():
                        if wall['type'] == 'wall':
                            room_dict[room_id][wall_id] = {}
                            x_wall = [x[0] for x in wall['global_corners']]
                            y_wall = [y[1] for y in wall['global_corners']]
                            if max(x_wall)-min(x_wall) > max(y_wall)-min(y_wall):
                                wall_centre = (max(x_room)+min(x_room))/2
                                direction = 0
                            else:
                                wall_centre = (max(y_room) + min(y_room)) / 2
                                direction = 1
                            room_dict[room_id][wall_id]['x_wall'] = (min(x_wall), max(x_wall))
                            room_dict[room_id][wall_id]['y_wall'] = (min(y_wall), max(y_wall))
                            room_dict[room_id][wall_id]['direction'] = direction
                            room_dict[room_id][wall_id]['wall_centre'] = wall_centre
                            room_dict[room_id][wall_id]['windows'] = {}
                            room_dict[room_id][wall_id]['window_centres'] = []

        for window_id, window_nodes in windows.items():
            # Get centre coordinates of window
            room_id = graph.nodes(data=True)[window_nodes[0]]["belongs_to"][0]

            if room_id in heat_delivery_dict.keys():
                x_windows = [x[0] for x in window_nodes]
                y_windows = [y[1] for y in window_nodes]
                window_centre_x = (max(x_windows) + min(x_windows)) / 2
                window_centre_y = (max(y_windows) + min(y_windows)) / 2

                if max(x_windows) - min(x_windows) > max(y_windows) - min(y_windows):
                    window_centre = window_centre_x
                else:
                    window_centre = window_centre_y

                for wall_id, wall in room_dict[room_id].items():
                    if wall['x_wall'][0] <= window_centre_x <= wall['x_wall'][1] and \
                     wall['y_wall'][0] <= window_centre_y <= wall['y_wall'][1] and \
                     self.elements[room_id].usage != "Traffic area":
                        room_dict[room_id][wall_id]['windows'][window_id] = window_nodes
                        room_dict[room_id][wall_id]['window_centres'].append(window_centre)

        window_dict = {}
        for room_id, room in room_dict.items():
            # Add one radiator under one window per wall, if the wall has windows
            # Radiator is placed under the window, which is closest to the wall centre
            room_radiators = []
            for wall in room.values():
                if wall['window_centres']:
                    middle_window = min(wall['window_centres'], key=lambda x: abs(x - wall['wall_centre']))

                    for window_id, window_nodes in wall['windows'].items():
                        x_windows = [x[0] for x in window_nodes]
                        y_windows = [y[1] for y in window_nodes]
                        if wall['direction'] == 0 and (min(x_windows) <= middle_window <= max(x_windows)):
                            window_dict[window_id] = window_nodes
                            room_radiators.append(window_id)
                        elif wall['direction'] == 1 and (min(y_windows) <= middle_window <= max(y_windows)):
                            window_dict[window_id] = window_nodes
                            room_radiators.append(window_id)

            # Add further radiators, if needed to reach the necessary heating power per room
            if needed_windows_dict[room_id] > len(room_radiators):
                further_needed_windows = needed_windows_dict[room_id] - len(room_radiators)
                i = 0
                for wall in room.values():
                    for window_id, window_nodes in wall['windows'].items():
                        if window_id not in room_radiators:
                            window_dict[window_id] = window_nodes
                            room_radiators.append(window_id)
                            i += 1
                        if i == further_needed_windows:
                            break
                    if i == further_needed_windows:
                        break
            if needed_windows_dict[room_id] < len(room_radiators):
                assert KeyError(f"Not enough windows for radiators in room {room_id}")
        return window_dict

    @staticmethod
    def read_radiator_material_excel(filename,
                                     sheet_name,
                                     ):
        """

		Args:
			filename ():
			sheet_name ():

		Returns:

		"""
        data = pd.read_excel(filename, sheet_name=sheet_name)
        # Daten aus der Tabelle auslesen und verarbeiten
        model_dict = {}
        for index, row in data.iterrows():
            data_dict = {}
            if not pd.isnull(row['Typ']):
                data_dict["typ"] = row['Typ']
            if not pd.isnull(row['Normwärmeleistung ((75/65/20 °C) in W/m']):
                data_dict["Normwärmeleistung"] = row['Normwärmeleistung ((75/65/20 °C) in W/m'] * (
                        ureg.watt / ureg.meter)
            if not pd.isnull(row['Wasserinhalt in l/m']):
                data_dict["Wasserinhalt"] = row['Wasserinhalt in l/m'] * (ureg.liter / ureg.meter)
            if not pd.isnull(row['Masse in kg/m']):
                data_dict["Masse"] = row['Masse in kg/m'] * (ureg.kilogram / ureg.meter)
            if not pd.isnull(row['Material']):
                data_dict["Material"] = row['Material']
            # Weiterverarbeitung der Daten (hier nur Ausgabe als Beispiel)
            model_dict[index] = data_dict
        return model_dict

    def read_bim2sim_data(self, space_id):
        for d in self.heat_demand_dict:

            space_guids = self.heat_demand_dict[d]["space_guids"]
            if set(space_id) & set(space_guids):
                standard_indoor_temperature = self.define_standard_indoor_temperature(usage=self.heat_demand_dict[d]["usage"])
                PHeater = self.heat_demand_dict[d]["PHeater"]
                PHeater_max = np.max(PHeater)
                return PHeater_max, standard_indoor_temperature

    def define_standard_indoor_temperature(self, usage):
        UseConditions_Path = Path(__file__).parent.parent / 'assets/UseConditions.json'
        with open(UseConditions_Path, 'r') as file:
            UseConditions = json.load(file)

        standard_indoor_temperature = 0
        for key, values in UseConditions.items():
            if usage == key:
                standard_indoor_temperature = (values["heating_profile"][12] - 273.15) * ureg.kelvin

        if standard_indoor_temperature == 0:
            standard_indoor_temperature = self.temperature_room
        return standard_indoor_temperature

    def logarithmic_mean_temperature(self, forward_temperature: float = 75,
                                     backward_temperature: float = 65,
                                     room_temperature: float = 20):
        """

        Args:
            forward_temperature ():
            backward_temperature ():
            room_temperature ():

        Returns:

        """
        log_mean_temperature = (forward_temperature - backward_temperature) / (math.log(
            (forward_temperature - room_temperature) / (backward_temperature - room_temperature)))
        if isinstance(log_mean_temperature, Quantity):
            return log_mean_temperature.magnitude
        else:
            return log_mean_temperature

    def heat_flow_design_radiator(self,
                                  log_mean_temperature_operation: float,
                                  heating_exponent: float,
                                  log_mean_temperature_norm: float,
                                  Q_heat_operation: float
                                  ):
        """

        Args:
            log_mean_temperature_operation ():
            heating_exponent ():
            log_mean_temperature_norm ():
            Q_heat_operation ():
            Q = 1,15 Q_N
        """
        Q_heat_norm = (Q_heat_operation / (
                    (log_mean_temperature_operation / log_mean_temperature_norm) ** heating_exponent))
        return Q_heat_norm

    def check_if_graph_in_building_boundaries(self, graph):

        def is_point_inside_shape(shape, point):
            classifier = BRepClass3d_SolidClassifier(shape)
            classifier.Perform(gp_Pnt(*point), 1e-6)
            return classifier.State() in (TopAbs_IN, TopAbs_ON)

        def is_edge_inside_shape(shape, point1, point2, iteration=0.1):
            edge_length = euclidean_distance(point1, point2)
            num_points = int(edge_length / iteration)
            x1, y1, z1 = point1
            x2, y2, z2 = point2
            for i in range(num_points):
                t = i / (num_points - 1)
                x = x1 * (1 - t) + x2 * t
                y = y1 * (1 - t) + y2 * t
                z = z1 * (1 - t) + z2 * t
                classifier = BRepClass3d_SolidClassifier(shape)
                classifier.Perform(gp_Pnt(x, y, z), 1e-6)
                if classifier.State() not in (TopAbs_IN, TopAbs_ON):
                    return False
            return True

        def euclidean_distance(point1, point2):
            return round(
                math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2),
                2)

        # Check if nodes and edges are inside the building geometry and not running through staircases, etc.

        settings_products = ifcopenshell.geom.main.settings()
        settings_products.set(settings_products.USE_PYTHON_OPENCASCADE, True)
        stories = filter_elements(self.elements, 'Storey')

        for storey in stories:
            slabs = filter_elements(storey.elements, 'InnerFloor')
            groundfloors = filter_elements(storey.elements, 'GroundFloor')
            slabs_and_baseslabs = slabs + groundfloors
            storey_floor_shapes = []
            for bottom_ele in slabs_and_baseslabs:
                if hasattr(bottom_ele.ifc, 'Representation'):
                    shape = ifcopenshell.geom.create_shape(
                        settings_products, bottom_ele.ifc).geometry
                    storey_floor_shapes.append(shape)

            for floor in self.floor_dict.keys():
                if floor == storey.guid:
                    nodes_floor = [node for node, data in graph.nodes(data=True)
                                   if data["floor_belongs_to"] == floor]
                    for node in nodes_floor:
                        if not any(is_point_inside_shape(shape, node) for shape in storey_floor_shapes):
                            print(f"Node {node} is not inside the building boundaries")
                            if any(type in graph.nodes[node]["type"] for type in ["radiator_forward",
                                                                                  "radiator_backward"]):
                                assert KeyError(f"Delivery node {node} not in building boundaries")
                            graph.remove_node(node)

                    edges_floor = [edge for edge in graph.edges()
                                   if graph.nodes[edge[0]]["floor_belongs_to"] == floor
                                   and graph.nodes[edge[1]]["floor_belongs_to"] == floor]
                    for edge in edges_floor:
                        if not any(is_edge_inside_shape(shape, edge[0], edge[1]) for shape in storey_floor_shapes):
                            print(f"Edge {edge} not inside building boundaries")
                            graph.remove_edge(edge[0], edge[1])
        return graph

    def get_delivery_nodes(self,
                           graph,
                           type_delivery: list = ["window"]):
        delivery_forward_points = []
        delivery_backward_points = []
        possible_delivery_nodes_dict = self.get_type_node(graph=graph,
                                           type_node=type_delivery)

        heat_delivery_dict = {}
        tzs = filter_elements(self.elements, "ThermalZone")
        for tz in tzs:
            heat_delivery_dict[tz.guid] = {}
            Q_flow_operation, norm_indoor_temperature = self.read_bim2sim_data([tz.guid])

            heat_delivery_dict[tz.guid]["Q_flow_operation"] = Q_flow_operation
            heat_delivery_dict[tz.guid]["norm_indoor_temperature"] = norm_indoor_temperature
            heat_delivery_dict[tz.guid]["room_area"] = tz.net_area.magnitude


        if type_delivery == ["door"]:
            delivery_dict, heat_delivery_extra_radiators = self.get_UFH_nodes(graph, possible_delivery_nodes_dict, heat_delivery_dict)
            heat_delivery_extra_radiators['0UiHARbFzF1RT4g_GKem_B'] = heat_delivery_dict[
                '0UiHARbFzF1RT4g_GKem_B'].copy()
            if heat_delivery_extra_radiators:
                possible_delivery_nodes_dict = self.get_type_node(graph=graph,
                                                                  type_node=["window"])
                delivery_dict_extra_radiators = self.get_radiator_nodes(graph, possible_delivery_nodes_dict, heat_delivery_extra_radiators)
        if type_delivery == ["window"]:
            delivery_dict = self.get_radiator_nodes(graph, possible_delivery_nodes_dict, heat_delivery_dict)




        edge_list = []
        # Erstelle eine Liste mit den IDs, die den Element-IDs zugeordnet sind
        for element in delivery_dict:
            forward_node, backward_node = self.get_bottom_left_node(graph=graph, nodes=delivery_dict[element])
            delivery_forward_points.append(forward_node)
            delivery_backward_points.append(backward_node)
            edge_list.append((forward_node, backward_node))
            nx.set_node_attributes(graph, {forward_node: {'type': ['radiator_forward']}})
            nx.set_node_attributes(graph, {forward_node: {'color': 'orange'}})
            nx.set_node_attributes(graph, {backward_node: {'type': ['radiator_backward']}})
            nx.set_node_attributes(graph, {backward_node: {'color': 'orange'}})

        if delivery_dict_extra_radiators:
            for element in delivery_dict_extra_radiators:
                forward_node, backward_node = self.get_bottom_left_node(graph=graph, nodes=delivery_dict_extra_radiators[element])
                delivery_forward_points.append(forward_node)
                delivery_backward_points.append(backward_node)
                edge_list.append((forward_node, backward_node))
                nx.set_node_attributes(graph, {forward_node: {'type': ['radiator_forward_extra']}})
                nx.set_node_attributes(graph, {forward_node: {'color': 'orange'}})
                nx.set_node_attributes(graph, {backward_node: {'type': ['radiator_backward_extra']}})
                nx.set_node_attributes(graph, {backward_node: {'color': 'orange'}})

        return delivery_forward_points, delivery_backward_points, edge_list

    def check_neighbour_nodes_collision(self,
                                        graph: nx.Graph(),
                                        edge_point_A: tuple,
                                        edge_point_B: tuple,
                                        neighbor_nodes_collision_type: list,
                                        no_neighbour_collision_flag: bool = True,
                                        same_type_flag: bool = True):
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
        for neighbor, attr in graph.nodes(data=True):
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

    def point_on_edge(self, graph, node, edges):
        """ Beispiel 3D-Punkt und 3D-Linie
                    point = Point(1, 2, 3)
                    line = LineString([(0, 0, 0), (2, 2, 2)])
                    # Überprüfung, ob der Punkt die Linie schneidet
                    if point.intersects(line):
                """
        point = graph.nodes[node]['pos']
        edge_point_A = graph.nodes[edges[0]]['pos']
        edge_point_B = graph.nodes[edges[1]]['pos']
        # z - Richtung
        if graph.has_edge(node, edges[0]) or graph.has_edge(node, edges[1]) or graph.has_edge(edges[0], node) or graph.has_edge(
                edges[1], node):
            return False
        # z-Richtung
        if edge_point_A[2] == edge_point_B[2] == point[2]:
            p = Point(point[0], point[1])
            line = LineString([(edge_point_A[0], edge_point_A[1]), (edge_point_B[0], edge_point_B[1])])
            return p.intersects(line)
        # y - Richtung
        if edge_point_A[1] == edge_point_B[1] == point[1]:
            p = Point(point[0], point[2])
            line = LineString([(edge_point_A[0], edge_point_A[2]), (edge_point_B[0], edge_point_B[2])])
            return p.intersects(line)
        # X - Richtung
        if edge_point_A[0] == edge_point_B[0] == point[0]:
            p = Point(point[1], point[2])
            line = LineString([(edge_point_A[1], edge_point_A[2]), (edge_point_B[1], edge_point_B[2])])
            return p.intersects(line)

    def define_source_node_per_floor(self,
                                     color: str,
                                     type_node: str,
                                     start_source_point: tuple):
        source_dict = {}
        # print(self.heating_graph_start_point)
        # print(self.floor_dict)
        for i, floor in enumerate(self.floor_dict):
            _dict = {}
            pos = (start_source_point[0], start_source_point[1], self.floor_dict[floor]["height"])
            _dict["pos"] = pos
            _dict["type_node"] = [type_node]
            _dict["element"] = f"source_{floor}"
            _dict["color"] = color
            _dict["belongs_to"] = floor
            source_dict[floor] = _dict

            if self.heating_graph_start_point == pos:
                _dict["type_node"] = [type_node, "start_node"]

        return source_dict

    def get_source_nodes(self,
                         graph: nx.Graph(),
                         points,
                         type,
                         grid_type: str
                         ):
        """
                # Source Points
                # start_point = ((4.040, 5.990, 0), (4.040, 5.990, 2.7))
                Args:
                    graph ():
                    points ():
                    delivery_forward_points ():
                Returns:
                """
        # Pro Etage Source Knoten definieren
        print("Add Source Nodes")
        source_list = []
        source_dict = self.define_source_node_per_floor(color="green",
                                                        type_node=type,
                                                        start_source_point=points)
        graph = graph.copy()
        # Erstellen der Source Knoten

        for floor in source_dict:
            pos = source_dict[floor]["pos"]
            color = source_dict[floor]["color"]
            type = source_dict[floor]["type_node"]
            element = source_dict[floor]["type_node"]
            graph, source_node = self.create_nodes(graph=graph,
                                               points=pos,
                                               color="red",
                                               grid_type=grid_type,
                                               type_node=type,
                                               element=element,
                                               belongs_to=floor,
                                               direction="y",
                                               update_node=True,
                                               floor_belongs_to=floor)
            source_list.append(pos)

        return graph, source_list

    def remove_attributes(self, graph: nx.Graph(), attributes: list):
        print("Delete unnecessary attributes.")
        for node, data in graph.nodes(data=True):
            if set(attributes) & set(data["type"]):
                for attr in attributes:
                    if attr in data["type"]:
                        data["type"].remove(attr)
        return graph

    @staticmethod
    def connect_sources(graph: nx.Graph(),
                        type_edge: str,
                        grid_type: str,
                        color: str,
                        type_units: bool = False):
        """

                Args:
                    graph ():

                Returns:

                """
        element_nodes = {}
        for node, data in graph.nodes(data=True):
            node_list = ["start_node", "end_node"]
            """if "Verteiler" in set(data["type"]):
                        print(data["type"])"""
            if set(node_list) & set(data["type"]):
                element = data["floor_belongs_to"]
                if element not in element_nodes:
                    element_nodes[element] = []
                element_nodes[element].append(node)
        for element, nodes in element_nodes.items():
            source_backward = nodes[0]
            source_forward = nodes[1]
            for node in nodes:
                if "backward" == graph.nodes[node]["grid_type"]:
                    source_backward = node
                else:
                    source_forward = node
            if type_units is True:
                length = abs(
                    distance.euclidean(graph.nodes[nodes[0]]["pos"], graph.nodes[nodes[1]]["pos"])) * ureg.meter
            else:
                length = abs(
                    distance.euclidean(graph.nodes[nodes[0]]["pos"], graph.nodes[nodes[1]]["pos"]))

            graph.add_edge(source_backward,
                       source_forward,
                       color=color,
                       type=type_edge,
                       grid_type=grid_type,
                       length=length,
                       flow_rate=0.0,
                       resistance=2.0)

        return graph

    def create_heating_graph(self,
                             graph: nx.Graph(),
                             grid_type: str,
                             type_delivery: list = ["window"],
                             one_pump_flag: bool = False):

        """
                Erstelle Endpunkte

                """
        # Relabel nodes
        node_mapping = {node: tuple(data["pos"]) for node, data in graph.nodes(data=True)}
        graph = nx.relabel_nodes(graph, node_mapping)

        # Get delivery nodes
        delivery_forward_nodes, delivery_backward_nodes, forward_backward_edge = self.get_delivery_nodes(graph=graph,
                                                                                                         type_delivery=type_delivery)

        forward_graph = graph.subgraph(delivery_forward_nodes)

        # Get source/shaft nodes
        forward_graph, source_forward_list = self.get_source_nodes(graph=forward_graph,
                                                                   points=self.heating_graph_start_point,
                                                                   type="Verteiler",
                                                                   grid_type="forward")

        self.check_graph(graph=forward_graph, type="forward_graph")


        window_node_mapping = {}
        ff_graph_list = []
        forward_nodes_floor = {}
        # pro Etage
        for i, floor in enumerate(self.floor_dict):
            z_value = self.floor_dict[floor]["height"]

            # Add ground nodes for windows
            if type_delivery == ["window"]:
                delivery_forward_nodes = []
                mapping = {}
                for node in forward_graph.nodes(data=True):
                    if node[1]['type'] in [['radiator_forward'], ['radiator_backward']] \
                            and node[1]['floor_belongs_to'] == floor:
                        mapping[node[0]] = (node[0][0], node[0][1], z_value)
                        node[1]['pos'][2] = z_value
                        delivery_forward_nodes.append(mapping[node[0]])
                        window_node_mapping[node[0]] = ((node[0][0], node[0][1], z_value), node[1].copy())

                forward_graph = nx.relabel_nodes(forward_graph, mapping)

            if type_delivery == ["door"]:
                mapping = {}
                for node in forward_graph.nodes(data=True):
                    if node[1]['type'] in [['radiator_forward_extra'], ['radiator_backward_extra']] \
                            and node[1]['floor_belongs_to'] == floor:
                        mapping[node[0]] = (node[0][0], node[0][1], z_value)
                        node[1]['pos'][2] = z_value
                        delivery_forward_nodes.remove(node[0])
                        delivery_forward_nodes.append(mapping[node[0]])
                        window_node_mapping[node[0]] = ((node[0][0], node[0][1], z_value), node[1].copy())

                if mapping:
                    forward_graph = nx.relabel_nodes(forward_graph, mapping)


            # Create list of delivery and source nodes
            element_nodes_forward = []
            for delivery_node in delivery_forward_nodes:
                if forward_graph.nodes[delivery_node]["floor_belongs_to"] == floor:
                    element_nodes_forward.append(delivery_node)
            for source_node in source_forward_list:
                if forward_graph.nodes[source_node]["floor_belongs_to"] == floor:
                    element_nodes_forward.append(source_node)

            forward_nodes_floor[floor] = element_nodes_forward.copy()

            # Add intersection points
            positions = nx.get_node_attributes(forward_graph, 'pos')
            for node1, node2 in itertools.combinations(element_nodes_forward, 2):
                # Project their positions onto the x and y axes
                x_positions = [positions[node1][0], positions[node2][0]]
                y_positions = [positions[node1][1], positions[node2][1]]
                # Find the intersections of these projections
                x_intersection = list(set(x_positions))
                y_intersection = list(set(y_positions))
                z = positions[node1][2]

                # Add the intersection points to the graph
                for x in x_intersection:
                    for y in y_intersection:
                        node_exists = False
                        for node, data in forward_graph.nodes(data=True):
                            if 'pos' in data and (data['pos'] == [x, y, z] or data['pos'] == (x, y, z)):
                                node_exists = True
                                break
                        if not node_exists:
                            forward_graph.add_node((x, y, z),
                                                   type=["intersection_point"],
                                                   pos=[x, y, z],
                                                   color="blue",
                                                   grid_type="forward",
                                                   belongs_to="None",
                                                   floor_belongs_to=floor,
                                                   direction="x")
                            element_nodes_forward.append((x, y, z))

            # Create rectangular grid between all points
            positions = nx.get_node_attributes(forward_graph, 'pos')
            for node, pos in positions.items():
                positions[node] = tuple(pos)

            # Sort the nodes based on their x and y coordinates
            # sorted_nodes = sorted(element_nodes_forward, key=lambda node: (positions[node][0], positions[node][1]))
            sorted_nodes = sorted(element_nodes_forward, key=lambda node: (positions[node][0], positions[node][1]))
            # Connect the nodes sequentially along the x-axis
            for i in range(len(sorted_nodes) - 1):
                if positions[sorted_nodes[i]][0] == positions[sorted_nodes[i + 1]][0]:
                    forward_graph.add_edge(sorted_nodes[i], sorted_nodes[i + 1], color='grey', direction='y',
                                           length=abs(
                                               positions[sorted_nodes[i]][1] - positions[sorted_nodes[i + 1]][1]))

            sorted_nodes = sorted(element_nodes_forward, key=lambda node: (positions[node][1], positions[node][0]))
            # Connect the nodes sequentially along the y-axis
            for i in range(len(sorted_nodes) - 1):
                if positions[sorted_nodes[i]][1] == positions[sorted_nodes[i + 1]][1]:
                    forward_graph.add_edge(sorted_nodes[i], sorted_nodes[i + 1], color='grey', direction='x',
                                           length=abs(
                                               positions[sorted_nodes[i]][0] - positions[sorted_nodes[i + 1]][0]))

        # Add vertical edges between shaft/source nodes
        for i in range(len(source_forward_list) - 1):
            forward_graph.add_edge(source_forward_list[i], source_forward_list[i + 1], color='red', direction='z',
                                   length=abs(
                                       positions[source_forward_list[i]][2] - positions[source_forward_list[i + 1]][
                                           2]))

        print("Check if nodes and edges of forward graph are inside the boundaries of the building")
        forward_graph = self.check_if_graph_in_building_boundaries(forward_graph)
        print("Check done")

        for i, floor in enumerate(self.floor_dict):
            # Save graph for each floor
            nodes_floor = [tuple(data["pos"]) for node, data in forward_graph.nodes(data=True)
                           if data["pos"][2] == self.floor_dict[floor]["height"]]
            floor_graph = forward_graph.subgraph(nodes_floor)

            z_value_floor = floor_graph.nodes[source_forward_list[i]]["pos"][2]
            delivery_nodes_floor = ([tuple(data["pos"]) for node, data in floor_graph.nodes(data=True)
                                    if data["type"] in [['radiator_forward'], ['radiator_backward'],
                                                        ['radiator_forward_extra'], ['radiator_backward_extra']]])
            intersection_nodes_floor = [tuple(data["pos"]) for node, data in floor_graph.nodes(data=True)
                                        if "intersection_point" in data["type"]]
            shaft_node_floor = source_forward_list[i]
            terminal_nodes_floor = forward_nodes_floor[floor].copy()

            self.visualize_graph(graph=floor_graph,
                                 graph_steiner_tree=floor_graph,
                                 z_value=z_value_floor,
                                 node_coordinates=nodes_floor,
                                 delivery_nodes_coordinates=delivery_nodes_floor,
                                 intersection_nodes_coordinates=intersection_nodes_floor,
                                 name=f"Vorlauf 0. Optimierung",
                                 unit_edge="m",
                                 building_shaft=shaft_node_floor
                                 )

            # Optimize heating graph using steiner method
            print(f"Calculate steiner tree {floor}_{i}")
            f_st, forward_total_length = self.steiner_graph(graph=floor_graph,
                                                            nodes_floor=nodes_floor,
                                                            delivery_nodes_floor=delivery_nodes_floor,
                                                            intersection_nodes_floor=intersection_nodes_floor,
                                                            shaft_node_floor=shaft_node_floor,
                                                            terminal_nodes_floor=terminal_nodes_floor,
                                                            z_value=z_value_floor,
                                                            grid_type="forward")

            if forward_total_length != 0 and forward_total_length is not None:
                f_st = self.reduce_path_nodes(graph=f_st,
                                              color="red",
                                              start_nodes=[shaft_node_floor],
                                              end_nodes=delivery_nodes_floor)

                self.visualize_graph(graph=f_st,
                                     graph_steiner_tree=f_st,
                                     z_value=z_value_floor,
                                     node_coordinates=[tuple(data["pos"]) for node, data in floor_graph.nodes(data=True)],
                                     delivery_nodes_coordinates=[tuple(data["pos"]) for node, data in f_st.nodes(data=True)
                                                                    if data["type"] in [['radiator_forward'],
                                                                                        ['radiator_forward_extra']]],
                                     intersection_nodes_coordinates=[tuple(data["pos"]) for node, data in f_st.nodes(data=True)
                                                                    if "intersection_point" in data["type"]],
                                     name=f"Vorlauf nach Optimierung und Reduzierung",
                                     unit_edge="m",
                                     building_shaft=shaft_node_floor
                                     )

                # Add back window nodes
                if type_delivery == ["window"]:
                    for node, data in f_st.nodes(data=True):
                        if data['type'] in [['radiator_forward'], ['radiator_backward']]:
                            data['type'] = [f"{data['type'][0]}_ground"]

                    for window_node, ground_node in window_node_mapping.items():
                        if ground_node[1]['floor_belongs_to'] == floor:
                            f_st.add_node(window_node,
                                          pos=list(window_node),
                                          color=ground_node[1]['color'],
                                          type=ground_node[1]['type'],
                                          grid_type=ground_node[1]['grid_type'],
                                          element=ground_node[1]['element'],
                                          belongs_to=ground_node[1]['belongs_to'],
                                          direction=ground_node[1]['direction'],
                                          floor_belongs_to=ground_node[1]['floor_belongs_to'],
                                          strang=ground_node[1]['strang'])

                            f_st.add_edge(ground_node[0], window_node, color="grey", direction="z",
                                          length=window_node[2] - ground_node[0][2])

                if type_delivery == ["door"]:
                    for node, data in f_st.nodes(data=True):
                        if data['type'] in [['radiator_forward_extra'], ['radiator_backward_extra']]:
                            data['type'] = [f"{data['type'][0]}_ground"]

                    for window_node, ground_node in window_node_mapping.items():
                        if ground_node[1]['floor_belongs_to'] == floor:
                            f_st.add_node(window_node,
                                          pos=list(window_node),
                                          color=ground_node[1]['color'],
                                          type=ground_node[1]['type'],
                                          grid_type=ground_node[1]['grid_type'],
                                          element=ground_node[1]['element'],
                                          belongs_to=ground_node[1]['belongs_to'],
                                          direction=ground_node[1]['direction'],
                                          floor_belongs_to=ground_node[1]['floor_belongs_to'],
                                          strang=ground_node[1]['strang'])

                            f_st.add_edge(ground_node[0], window_node, color="grey", direction="z",
                                          length=window_node[2] - ground_node[0][2])


                self.write_json_graph(graph=f_st,
                                      filename=f"heating_circle_floor_Z_{shaft_node_floor[2]}.json")

                self.check_graph(graph=f_st, type=grid_type)
                ff_graph_list.append(f_st)

        f_st = self.add_graphs(graph_list=ff_graph_list)

        # Delete unnecessary node attribute
        f_st = self.remove_attributes(graph=f_st, attributes=["center_wall_forward", "snapped_nodes"])
        # Add rise tube
        f_st = self.add_rise_tube(graph=f_st)
        self.check_graph(graph=f_st, type="forward")
        # Direct forward graph
        f_st = self.directed_graph(graph=f_st, source_nodes=source_forward_list[0], grid_type=grid_type)
        f_st = self.update_graph(graph=f_st, grid_type="forward", color="red")
        f_st = self.index_strang(graph=f_st)
        # create backward graph
        b_st = self.create_backward(graph=f_st, grid_type="backward", offset=0.1, color="blue")
        # add components
        composed_graph = nx.disjoint_union(f_st, b_st)
        composed_graph = self.connect_sources(graph=composed_graph,
                                              type_edge="source",
                                              grid_type="connection",
                                              color="orange")
        composed_graph = self.connect_forward_backward(graph=composed_graph,
                                                       color="orange",
                                                       edge_type="radiator",
                                                       grid_type="connection",
                                                       type_delivery=["radiator_forward", "radiator_backward"])
        composed_graph = self.add_component_nodes(graph=composed_graph, one_pump_flag=one_pump_flag, type_delivery=type_delivery)
        self.write_json_graph(graph=composed_graph, filename="heating_circle.json")

        return composed_graph


    def visualize_graph(self,
                            graph,
                            graph_steiner_tree,
                            z_value,
                            node_coordinates,
                            delivery_nodes_coordinates,
                            intersection_nodes_coordinates,
                            name,
                            unit_edge,
                            building_shaft
                            ):
        """
        :param graph: Graph
        :param graph_steiner_tree: Steinerbaum
        :param z_value: Z-Achse
        :param node_coordinates: Schnittpunkte
        :param delivery_nodes_coordinates: Koordinaten ohne Volume_flow
        :param intersection_nodes_coordinates: Schnittpunkte ohne Volume_flow
        :param name: Diagrammbezeichnung
        :param unit_edge: Einheit der Kante für Legende Diagramm
        """
        # visualization
        plt.figure(figsize=(8.3, 5.8), dpi=300)
        plt.xlabel('X-Achse in m',
                   fontsize=12
                   )
        plt.ylabel('Y-Achse in m',
                   fontsize=12
                   )
        plt.title(name + f", Z: {z_value}",
                  fontsize=12
                  )
        plt.grid(False)
        plt.subplots_adjust(left=0.03, bottom=0.04, right=0.99,
                            top=0.96)  # Removes the border around the diagram, diagram quasi full screen
        # plt.axis('equal') # Ensures that the plot is true to scale

        # Define node positions
        pos = {node: (node[0], node[1]) for node in node_coordinates}

        # Entry to be deleted
        entry_to_remove = (building_shaft[0], building_shaft[1], z_value)

        # Filter the list to remove all entries that match entry_to_remove
        delivery_nodes_coordinates = [entry for entry in delivery_nodes_coordinates if
                                                   entry != entry_to_remove]

        # draw nodes
        nx.draw_networkx_nodes(graph,
                               pos,
                               nodelist=delivery_nodes_coordinates,
                               node_shape='s',
                               node_color='blue',
                               node_size=10)
        nx.draw_networkx_nodes(graph,
                               pos,
                               nodelist=[(building_shaft[0], building_shaft[1], z_value)],
                               node_shape="s",
                               node_color="green",
                               node_size=10)
        nx.draw_networkx_nodes(graph,
                               pos,
                               nodelist=intersection_nodes_coordinates,
                               node_shape='o',
                               node_color='red',
                               node_size=10)

        # draw edges
        nx.draw_networkx_edges(graph, pos, width=1)
        nx.draw_networkx_edges(graph_steiner_tree, pos, width=1, style="-", edge_color="blue")

        # edge weight
        edge_labels = nx.get_edge_attributes(graph_steiner_tree, 'length')
        for key, value in edge_labels.items():
            edge_labels[key] = round(value,2)

        nx.draw_networkx_edge_labels(graph_steiner_tree,
                                     pos,
                                     edge_labels=edge_labels,
                                     # label_pos=0.5,  # Positioniere die Beschriftung in der Mitte der Kante
                                     verticalalignment='bottom',  # Ausrichtung der Beschriftung unterhalb der Kante
                                     # horizontalalignment='center',
                                     font_size=8,
                                     font_weight=10,
                                     rotate=90,
                                     clip_on=False
                                     )

        # show node weight
        node_labels = nx.get_node_attributes(graph, 'heat flow')
        node_labels_without_unit = dict()
        for key, value in node_labels.items():
            try:
                node_labels_without_unit[key] = f"{value.magnitude}"
            except AttributeError:
                node_labels_without_unit[key] = ""
        nx.draw_networkx_labels(graph, pos, labels=node_labels_without_unit, font_size=8, font_color="white")

        # Create legend
        legend_delivery = plt.Line2D([0], [0], marker='s', color='w', label='Delivery node',
                                    markerfacecolor='blue',
                                    markersize=10)
        legend_intersection = plt.Line2D([0], [0], marker='o', color='w', label='Intersection point',
                                         markerfacecolor='red', markersize=6)
        legend_shaft = plt.Line2D([0], [0], marker='s', color='w', label='Building Shaft',
                                  markerfacecolor='green', markersize=10)
        legend_steiner_edge = plt.Line2D([0], [0], color='blue', lw=1, linestyle='-',
                                         label=f'Steiner-Edge in {unit_edge}')

        # # Check whether the lateral surface is available
        # if total_coat_area is not False:
        #     legend_coat_area = plt.Line2D([0], [0], lw=0, label=f'Mantelfläche: {total_coat_area} m²')
        #
        #     # Add legend to the diagram, including the lateral surface
        #     plt.legend(
        #         handles=[legend_ceiling, legend_intersection, legend_shaft, legend_steiner_edge, legend_coat_area],
        #         loc='best')
        # else:
        # Add legend to the diagram without the lateral surface
        plt.legend(handles=[legend_delivery, legend_intersection, legend_shaft, legend_steiner_edge],
                   loc='best')  # , bbox_to_anchor=(1.1, 0.5)

        # Set the path for the new folder
        folder_path = Path(self.hydraulic_system_directory / 'plots' / f"Z_{z_value}")

        # create folder
        folder_path.mkdir(parents=True, exist_ok=True)

        # save graph
        total_name = name + "_Vorlauf_Z" + f"{z_value}" + ".png"
        path_and_name = folder_path / total_name

        plt.axis('equal')

        plt.savefig(path_and_name, format='png')

        # how graph
        # plt.show()

        # close graph
        plt.close()





    def index_strang(self, graph):
        """

                Args:
                    graph ():
                """
        k = 0
        for node in list(nx.topological_sort(graph)):
            if "Verteiler" in graph.nodes[node]["type"] and graph.nodes[node]["grid_type"] == "forward":
                successors = list(graph.successors(node))
                for i, succ in enumerate(successors):
                    # strang = f'{i}_{node}'
                    strang = f'{k}_strang'
                    graph.nodes[succ]["strang"] = strang
                    k = k + 1
            elif "Verteiler" in graph.nodes[node]["type"] and graph.nodes[node]["grid_type"] == "backward":
                continue
            else:
                strang = graph.nodes[node]["strang"]
                successors = list(graph.successors(node))
                for i, succ in enumerate(successors):
                    graph.nodes[succ]["strang"] = strang
        return graph

    @staticmethod
    def connect_forward_backward(graph,
                                 type_delivery: list,
                                 color: str,
                                 grid_type: str,
                                 edge_type: str,
                                 type_units: float = False):
        element_nodes = {}
        for node, data in graph.nodes(data=True):
            if set(type_delivery) & set(data["type"]):
                element = data["element"]
                for ele in element:
                    if ele not in element_nodes:
                        element_nodes[ele] = []
                    element_nodes[ele].append(node)
        for element, nodes in element_nodes.items():
            source_backward = nodes[0]
            source_forward = nodes[1]
            for node in nodes:
                if "backward" == graph.nodes[node]["grid_type"]:
                    source_backward = node
                else:
                    source_forward = node
            length = abs(
                distance.euclidean(graph.nodes[nodes[0]]["pos"], graph.nodes[nodes[1]]["pos"]))  # * ureg.meter
            if type_units is True:
                length = length * ureg.meter

            graph.add_edge(source_forward,
                       source_backward,
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       length=length,
                       flow_rate=0.0,
                       resistance=2.0)

        return graph

    def visualize_node_order(self, graph, type_grid):
        """

                Args:
                    graph ():
                """
        # Knotenpositionen
        plt.figure(figsize=(10, 8))
        # Anfangs- und Endknoten farblich markieren
        node_color = [
            'red' if "radiator_forward" in set(graph.nodes[node]['type']) else 'graph' if 'Verteiler' in graph.nodes[node][
                'type'] else 'b'
            for node in graph.nodes()]
        # Graph zeichnen
        t = nx.get_node_attributes(graph, "pos")
        new_dict = {key: (x, y) for key, (x, y, z) in t.items()}
        nx.draw_networkx(graph=graph,
                         pos=new_dict,
                         node_color=node_color,
                         node_shape='o',
                         node_size=10,
                         font_size=12,
                         with_labels=False)
        plt.title(f'Graphennetzwerk vom Typ {type_grid}')
        plt.tight_layout()

    def get_bottom_left_node(self, graph, nodes):
        positions = nx.get_node_attributes(graph, 'pos')
        # find nodes with lowest z coordinate
        z_values = {node: positions[node][2] for node in nodes}
        min_z_values = sorted(z_values.items(), key=lambda x: x[1])[:2]
        node1, z1 = min_z_values[0]
        node2, z2 = min_z_values[1]
        # Überprüfe, ob sich die Knoten in x- oder y-Richtung unterscheiden
        diff_x = positions[node1][0] - positions[node2][0]
        diff_y = positions[node1][1] - positions[node2][1]
        if diff_x > 0:
            forward_node = node2
            backward_node = node1
        elif diff_y > 0:
            forward_node = node2
            backward_node = node1
        else:
            # forward_node = node2
            # backward_node = node1
            forward_node = node1
            backward_node = node2
        return forward_node, backward_node

    def nearest_polygon_in_space(self, graph, node, room_global_points, floor_flag: bool = True):
        """
                Finde die nächste Raum ebene des Punktes/Knoten.
                Args:
                    graph ():
                    node ():

                Returns:
                """
        point = Point(graph.nodes[node]["pos"])
        direction = graph.nodes[node]["direction"]
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

    def sort_edge_direction(self,
                            graph: nx.Graph(),
                            direction: str,
                            node: nx.Graph().nodes(),
                            tol_value: float,
                            neighbor: nx.Graph().nodes(),
                            pos_neighbors: list,
                            neg_neighbors: list):
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

        neighbor_pos = graph.nodes[neighbor]["pos"]
        neighbor_pos = tuple(round(coord, 2) for coord in neighbor_pos)
        node_pos = graph.nodes[node]["pos"]
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

    def check_graph(self, graph, type):
        if nx.is_connected(graph) is True:
            print(f"{Fore.BLACK + Back.GREEN} {type} Graph is connected.")
            return graph
        else:
            print(f"{Fore.BLACK + Back.RED} {type} Graph is not connected.")
            # self.visulize_networkx(graph=graph)
            for node in graph.nodes():
                if nx.is_isolate(graph, node) is True:
                    print("node", node, "is not connected.")
                    print(f'{graph.nodes[node]["pos"]} with type {graph.nodes[node]["type"]}')
            # Bestimme die verbundenen Komponenten
            components = list(nx.connected_components(graph))
            # Gib die nicht miteinander verbundenen Komponenten aus
            print("Not Conntected Components")
            graph = self.kit_grid(graph=graph)
            if nx.is_connected(graph) is True:
                print(f"{Fore.BLACK + Back.GREEN} {type} Graph is connected.")
                # self.visulize_networkx(graph=graph)
                # plt.show()
                return graph
            else:
                print(f"{Fore.BLACK + Back.RED} {type} Graph is not connected.")
                # self.visulize_networkx(graph=graph)
                plt.show()
                exit(1)
            """for component in disconnected_components:
                        for c in component:
                            print("node", c, "is not connected.")
                            print(f'{graph.nodes[c]["pos"]} with type {graph.nodes[c]["type"]}')"""

            """# Erhalte die Teilgraphen
                    subgraphs = list(nx.connected_component_subgraphs(graph))

                    # Sortiere die Teilgraphen basierend auf ihrer Größe
                    sorted_subgraphs = sorted(subgraphs, key=lambda x: x.number_of_nodes() + x.number_of_edges())

                    # Lösche den kleinsten Teilgraphen, wenn es mehr als einen Teilgraphen gibt
                    if len(sorted_subgraphs) > 1:
                        smallest_subgraph = sorted_subgraphs[0]
                        graph.remove_nodes_from(smallest_subgraph)

                    # Überprüfe, ob der Graph komplett verbunden ist
                    is_connected = nx.is_connected(graph)

                    # Gib das Ergebnis aus
                    print("Ist der Graph komplett verbunden?", is_connected)"""

    def nearest_neighbour_edge(self,
                               graph: nx.Graph(),
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
                    graph ():
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
                    neg_neighbors, pos_neighbors = self.sort_edge_direction(graph=graph,
                                                                            direction=direction,
                                                                            node=node,
                                                                            tol_value=tol_value,
                                                                            neighbor=connect_node,
                                                                            pos_neighbors=pos_neighbors,
                                                                            neg_neighbors=neg_neighbors)
        elif nearest_node_flag is True:
            for neighbor, data in graph.nodes(data=True):
                if neighbor != node:
                    neighbor_pos = data["pos"]
                    if connect_element_together is True:
                        if set(graph.nodes[node]["element"]) & set(data["element"]):
                            neg_neighbors, pos_neighbors = self.sort_edge_direction(graph=graph,
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
                        if set(node_type) & set(graph.nodes[node]["type"]) and set(node_type) & set(data["type"]):
                            if graph.nodes[node]["floor_belongs_to"] == data["floor_belongs_to"]:
                                if set(graph.nodes[node]["element"]).isdisjoint(set(data["element"])):
                                    neg_neighbors, pos_neighbors = self.sort_edge_direction(graph=graph,
                                                                                            direction=direction,
                                                                                            node=node,
                                                                                            tol_value=tol_value,
                                                                                            neighbor=neighbor,
                                                                                            pos_neighbors=pos_neighbors,
                                                                                            neg_neighbors=neg_neighbors)
                    if connect_types is True:
                        if set(node_type) & set(data["type"]):
                            neg_neighbors, pos_neighbors = self.sort_edge_direction(graph=graph,
                                                                                    direction=direction,
                                                                                    node=node,
                                                                                    tol_value=tol_value,
                                                                                    neighbor=neighbor,
                                                                                    pos_neighbors=pos_neighbors,
                                                                                    neg_neighbors=neg_neighbors)
                    if connect_types_element is True:
                        if set(node_type) & set(data["type"]) and set(graph.nodes[node]["element"]) & set(data["element"]):
                            neg_neighbors, pos_neighbors = self.sort_edge_direction(graph=graph,
                                                                                    direction=direction,
                                                                                    node=node,
                                                                                    tol_value=tol_value,
                                                                                    neighbor=neighbor,
                                                                                    pos_neighbors=pos_neighbors,
                                                                                    neg_neighbors=neg_neighbors)

                    if all_node_flag is True:
                        neg_neighbors, pos_neighbors = self.sort_edge_direction(graph=graph,
                                                                                direction=direction,
                                                                                node=node,
                                                                                tol_value=tol_value,
                                                                                neighbor=neighbor,
                                                                                pos_neighbors=pos_neighbors,
                                                                                neg_neighbors=neg_neighbors)

        node_pos = graph.nodes[node]["pos"]
        if pos_neighbors:
            nearest_neighbour = sorted(pos_neighbors, key=lambda p: distance.euclidean(graph.nodes[p]["pos"], node_pos))[0]
            if nearest_neighbour is not None:
                if not graph.has_edge(node, nearest_neighbour) and not graph.has_edge(node, nearest_neighbour):
                    if self.check_collision(graph=graph,
                                            edge_point_A=graph.nodes[node]["pos"],
                                            edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                            disjoint_flag=disjoint_flag,
                                            collision_flag=collision_flag,
                                            intersects_flag=intersects_flag,
                                            within_flag=within_flag,
                                            tolerance=col_tol) is False:
                        if self.check_neighbour_nodes_collision(graph=graph,
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
        if neg_neighbors:
            nearest_neighbour = sorted(neg_neighbors, key=lambda p: distance.euclidean(graph.nodes[p]["pos"], node_pos))[0]
            if nearest_neighbour is not None:
                if not graph.has_edge(node, nearest_neighbour) and not graph.has_edge(node, nearest_neighbour):
                    if self.check_collision(graph=graph,
                                            edge_point_A=graph.nodes[node]["pos"],
                                            edge_point_B=graph.nodes[nearest_neighbour]["pos"],
                                            disjoint_flag=disjoint_flag,
                                            intersects_flag=intersects_flag,
                                            within_flag=within_flag,
                                            tolerance=col_tol,
                                            collision_flag=collision_flag,
                                            collision_type_node=collision_type_node) is False:
                        if self.check_neighbour_nodes_collision(graph=graph,
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

    def snapped_point_on_edges(self,
                               points,
                               x_neg_lines,
                               x_pos_lines,
                               y_neg_lines,
                               y_pos_lines,
                               z_pos_lines,
                               z_neg_lines):
        """
                Args:
                    points ():
                    x_neg_lines ():
                    x_pos_lines ():
                    y_neg_lines ():
                    y_pos_lines ():
                    z_pos_lines ():
                    z_neg_lines ():
                Returns:
                """
        point = Point(points)

        nearest_pos_x_lines = min(x_pos_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][0] - point.x)) if x_pos_lines else {}

        nearest_neg_x_lines = min(x_neg_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][0] - point.x)) if x_neg_lines else {}

        nearest_pos_y_lines = min(y_pos_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][1] - point.y)) if y_pos_lines else {}
        nearest_neg_y_lines = min(y_neg_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][1] - point.y)) if y_neg_lines else {}
        nearest_pos_z_lines = min(z_pos_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][2] - point.z)) if z_pos_lines else {}

        nearest_neg_z_lines = min(z_neg_lines.items(),
                                  key=lambda item: abs(item[1].coords[0][2] - point.z)) if z_neg_lines else {}

        new_node_neg_x = new_node_pos_x = new_node_neg_y = new_node_pos_y = new_node_neg_z = new_node_pos_z = None

        # x line: y1 = y2 , z1 = z2
        if nearest_pos_x_lines:
            # x line: y1 = y2 , z1 = z2
            new_node_pos_x = (nearest_pos_x_lines[1].coords[0][0], points[1], points[2])
        if nearest_neg_x_lines:
            new_node_neg_x = (nearest_neg_x_lines[1].coords[0][0], points[1], points[2])
        # y line: x1=x2 und z1 = z2
        if nearest_pos_y_lines:
            new_node_pos_y = (points[0], nearest_pos_y_lines[1].coords[0][1], points[2])
        if nearest_neg_y_lines:
            new_node_neg_y = (points[0], nearest_neg_y_lines[1].coords[0][1], points[2])
        # z line: x1 = x2 und y1 = y2
        if nearest_pos_z_lines:
            new_node_pos_z = (points[0], points[1], nearest_pos_z_lines[1].coords[0][2])
        if nearest_neg_z_lines:
            new_node_neg_z = (points[0], points[1], nearest_neg_z_lines[1].coords[0][2])
        return new_node_neg_x, new_node_pos_x, new_node_neg_y, new_node_pos_y, new_node_neg_z, new_node_pos_z, \
            nearest_pos_x_lines, nearest_neg_x_lines, nearest_pos_y_lines, nearest_neg_y_lines, nearest_pos_z_lines, \
            nearest_neg_z_lines

    def get_type_node(self, graph, type_node, ):
        _dict = {}
        for node, data in graph.nodes(data=True):
            if set(type_node) & set(data["type"]):
                for ele in data["element"]:
                    if ele in _dict:
                        _dict[ele].append(node)
                    else:
                        _dict[ele] = [node]
        return _dict

    def get_type_node_attr(self, graph, type_node, attr: str = "pos"):
        ergebnis_dict = {}
        for space_node, data in graph.nodes(data=True):
            if set(type_node) & set(data["type"]):
                for ele in data["element"]:
                    if ele in ergebnis_dict:
                        ergebnis_dict[ele].append(data[attr])
                    else:
                        ergebnis_dict[ele] = [data[attr]]
        return ergebnis_dict

    def check_collision(self,
                        graph,
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
                    graph ():
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
        ele_dict = self.get_type_node_attr(graph=graph,
                                           type_node=collision_type_node,
                                           attr="pos")
        room_point_dict = {}
        for i, floor_id in enumerate(self.floor_dict):
            for room in self.floor_dict[floor_id]["rooms"]:
                room_data = self.floor_dict[floor_id]["rooms"][room]
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

    def center_space(self, graph, tolerance: float = 0.0):
        """

                """
        room_point_dict = {}
        for i, floor_id in enumerate(self.floor_dict):
            for room in self.floor_dict[floor_id]["rooms"]:
                room_data = self.floor_dict[floor_id]["rooms"][room]
                room_global_corners = room_data["global_corners"]
                room_point_dict[room] = room_global_corners
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
                y = (max_y - min_y)
                x = (max_x - min_x)

    def nearest_edges(self,
                      graph: nx.Graph(),
                      node: nx.Graph().nodes(),
                      points: tuple,
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
                    points (): Punktkoordinaten
                    z_flag (): Falls True, such auch in Z Richtung nach Kanten
                    x_flag (): Falls True, such auch in X Richtung nach Kanten
                    y_flag (): Falls True, such auch in Y Richtung nach Kanten
                    tol_value ():
                    bottom_z_flag (): Falls False, Sucht nur in negativer z richtung
                    edges (): Ausgewählte Kanten für den Punkt
                Returns:
                """

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

    def add_rise_tube(self,
                      graph: nx.Graph(),
                      color: str = "red"):
        """
                Args:
                    graph ():
                    circulation_direction ():
                Returns:
                """
        source_dict = {}
        for node, data in graph.nodes(data=True):
            if "Verteiler" in set(graph.nodes[node]["type"]):
                source_dict[node] = data["pos"][2]
        sorted_dict = dict(sorted(source_dict.items(), key=lambda x: x[1]))
        keys = list(sorted_dict.keys())
        for source, target in zip(keys, keys[1:]):
            length = abs(distance.euclidean(graph.nodes[source]["pos"], graph.nodes[target]["pos"]))
            graph.add_edge(source,
                       target,
                       color=color,
                       type="rise_tube",
                       grid_type="forward",
                       direction="z",
                       length=length)
        return graph

    def delete_duplicate_nodes(self,
                               graph: nx.Graph(),
                               duplicated_nodes: list):
        """
                Set der Knoten, die entfernt werden sollen, Dict zur Speicherung des Knotens mit der jeweiligen Position
                Entfernt Knoten aus einem networkx-Graphen, die dieselbe Position haben, außer einem.
                Durchlaufen Sie alle Knoten und suchen Sie nach Duplikaten
                Args:
                    graph ():
                    duplicated_nodes ():
                """
        nodes_to_remove = set()
        pos_to_node = {}

        for node in duplicated_nodes:
            pos = graph.nodes[node]["pos"]
            if pos in pos_to_node:
                nodes_to_remove.add(node)
            else:
                pos_to_node[pos] = node

        graph.remove_nodes_from(nodes_to_remove)
        remaining_nodes = [node for node in duplicated_nodes if node in graph]
        return graph, remaining_nodes

    def check_point_between_edge_and_point(self, point, edge_start, edge_end):
        edge = LineString([edge_start, edge_end])
        point_distance = edge.distance(point)
        edge_length = edge.length
        if point_distance < edge_length:
            return True
        return False

    def add_new_component_nodes(self,
                                graph: nx.Graph(),
                                frozen_graph,
                                node,
                                str_chain):
        """

                Args:
                    graph ():
                    frozen_graph ():
                    node ():
                    str_chain ():

                Returns:

                """
        direction_flow = None
        node_dictionary = {}
        neighbors = list(graph.neighbors(node))
        edges_with_node = list(graph.edges(node))
        for edge in edges_with_node:
            v = graph.nodes[edge[0]]['pos']
            u = graph.nodes[edge[1]]['pos']
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
                node_dictionary[f"{edge[0]}_{str_chain[i]}_{i}"] = {"direction_flow": direction_flow},
                i = i + 1

        return node_dictionary

    def add_components_on_graph(self,
                                graph,
                                node,
                                str_chain,
                                neighbors,
                                color: str,
                                grid_type: str,
                                edge_type: str,
                                strang: str,
                                lay_from_node: bool = True,
                                source_flag: bool = False,
                                tol_value: float = 0.0,
                                z_direction: bool = True,
                                x_direction: bool = True,
                                y_direction: bool = True):
        """
                Fügt Komponenten auf den Graphen hinzu.
                Args:
                    graph ():
                    str_chain ():
                """
        graph = graph.copy()
        # Pro Strang des Knotens
        for k, neighbor in enumerate(neighbors):
            node_list = []
            if set(str_chain) & set(graph.nodes[node]["type"]) or set(str_chain) & set(graph.nodes[neighbor]["type"]):
                continue
            strang = graph.nodes[neighbor]["strang"]
            if lay_from_node is True:
                x2, y2, z2 = graph.nodes[neighbor]["pos"]
                x1, y1, z1 = graph.nodes[node]["pos"]
            else:
                x1, y1, z1 = graph.nodes[neighbor]["pos"]
                x2, y2, z2 = graph.nodes[node]["pos"]
            # Z Achse
            if source_flag is True:
                # if 'start_node' in set(graph.nodes[neighbor]["type"]):
                diff_x = (x1 - x2)
                comp_diff_x = diff_x / (len(str_chain) + 1)
                diff_y = (y1 - y2)
                comp_diff_y = diff_y / (len(str_chain) + 1)
                for i in range(0, len(str_chain)):
                    x = x1 - (i + 1) * comp_diff_x
                    y = y1 - (i + 1) * comp_diff_y
                    pos = (x, y, z1)
                    graph, node_name = self.create_nodes(graph=graph,
                                                     points=pos,
                                                     grid_type=graph.nodes[node]["grid_type"],
                                                     color=graph.nodes[node]["color"],
                                                     type_node=str_chain[i],
                                                     direction=graph.nodes[node]["direction"],
                                                     update_node=True,
                                                     element=graph.nodes[node]["element"],
                                                     belongs_to=graph.nodes[node]["belongs_to"],
                                                     strang=strang,
                                                     floor_belongs_to=graph.nodes[node]["floor_belongs_to"])

                    node_list.append(node_name)
                if graph.has_edge(neighbor, node):
                    graph.remove_edge(neighbor, node)
                    node_list.insert(0, neighbor)
                    node_list.append(node)
                if graph.has_edge(node, neighbor):
                    graph.remove_edge(node, neighbor)
                    node_list.insert(0, node)
                    node_list.append(neighbor)
                graph = self.create_directed_edges(graph=graph,
                                               node_list=node_list,
                                               color=color,
                                               edge_type=edge_type,
                                               grid_type=grid_type)
            if z_direction is True:
                if abs(x1 - x2) <= tol_value and abs(y1 - y2) <= tol_value:
                    diff_z = (z1 - z2)
                    comp_diff = diff_z / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        z = z1 - (i + 1) * comp_diff
                        pos = (x1, y1, z)
                        graph, node_name = self.create_nodes(graph=graph,
                                                         points=pos,
                                                         grid_type=graph.nodes[node]["grid_type"],
                                                         color=graph.nodes[node]["color"],
                                                         type_node=str_chain[i],
                                                         direction=graph.nodes[node]["direction"],
                                                         update_node=True,
                                                         element=graph.nodes[node]["element"],
                                                         belongs_to=graph.nodes[node]["belongs_to"],
                                                         strang=strang,
                                                         floor_belongs_to=graph.nodes[node]["floor_belongs_to"])
                        node_list.append(node_name)
                    if graph.has_edge(neighbor, node):
                        graph.remove_edge(neighbor, node)
                        node_list.insert(0, neighbor)
                        node_list.append(node)
                    if graph.has_edge(node, neighbor):
                        graph.remove_edge(node, neighbor)
                        node_list.insert(0, node)
                        node_list.append(neighbor)
                    graph = self.create_directed_edges(graph=graph,
                                                   node_list=node_list,
                                                   color=color,
                                                   edge_type=edge_type,
                                                   grid_type=grid_type)

            # X Achse
            if x_direction is True:
                if abs(z1 - z2) <= tol_value and abs(y1 - y2) <= tol_value:
                    diff_x = (x1 - x2)
                    comp_diff = diff_x / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        x = x1 - (i + 1) * comp_diff
                        pos = (x, y1, z1)
                        graph, node_name = self.create_nodes(graph=graph,
                                                         points=pos,
                                                         grid_type=graph.nodes[node]["grid_type"],
                                                         color=graph.nodes[node]["color"],
                                                         type_node=str_chain[i],
                                                         direction=graph.nodes[node]["direction"],
                                                         update_node=True,
                                                         element=graph.nodes[node]["element"],
                                                         strang=strang,
                                                         belongs_to=graph.nodes[node]["belongs_to"],
                                                         floor_belongs_to=graph.nodes[node]["floor_belongs_to"])
                        node_list.append(node_name)

                    if graph.has_edge(neighbor, node):
                        graph.remove_edge(neighbor, node)
                        node_list.insert(0, neighbor)
                        node_list.append(node)
                    if graph.has_edge(node, neighbor):
                        graph.remove_edge(node, neighbor)
                        node_list.insert(0, node)
                        node_list.append(neighbor)
                    graph = self.create_directed_edges(graph=graph,
                                                   node_list=node_list,
                                                   color=color,
                                                   edge_type=edge_type,
                                                   grid_type=grid_type)

            # Y Achse
            if y_direction is True:
                if abs(z1 - z2) <= tol_value and abs(x1 - x2) <= tol_value:
                    diff_y = (y1 - y2)
                    comp_diff = diff_y / (len(str_chain) + 1)
                    for i in range(0, len(str_chain)):
                        y = y1 - (i + 1) * comp_diff
                        pos = (x1, y, z1)
                        graph, node_name = self.create_nodes(graph=graph,
                                                         grid_type=graph.nodes[node]["grid_type"],
                                                         points=pos,
                                                         color=graph.nodes[node]["color"],
                                                         type_node=str_chain[i],
                                                         direction=graph.nodes[node]["direction"],
                                                         update_node=True,
                                                         strang=strang,
                                                         element=graph.nodes[node]["element"],
                                                         belongs_to=graph.nodes[node]["belongs_to"],
                                                         floor_belongs_to=graph.nodes[node]["floor_belongs_to"])
                        node_list.append(node_name)
                    if graph.has_edge(neighbor, node):
                        graph.remove_edge(neighbor, node)
                        node_list.insert(0, neighbor)
                        node_list.append(node)
                    if graph.has_edge(node, neighbor):
                        graph.remove_edge(node, neighbor)
                        node_list.insert(0, node)
                        node_list.append(neighbor)
                    graph = self.create_directed_edges(graph=graph, node_list=node_list,
                                                   color=color,
                                                   edge_type=edge_type,
                                                   grid_type=grid_type)
        return graph

    def update_graph(self, graph, grid_type: str, color: str):
        for node in graph.nodes():
            graph.nodes[node]["color"] = color
            graph.nodes[node]["grid_type"] = grid_type
        for edge in graph.edges():
            graph.edges[edge]["color"] = color
        return graph

    def add_component_nodes(self,
                            graph: nx.Graph(),
                            one_pump_flag: bool = True,
                            type_delivery: list = ["window"]):
        """
                Args:
                    graph ():
                    color ():
                    edge_type ():
                    start_node ():
                    grid_type ():

                Returns:

                """
        grid_type = "heating_circle"
        radiator_dict = {}
        source_dict = {}
        source_nodes = None
        radiator_nodes = None
        # todo: Mischventil mit anschließend verbinden
        for node, data in graph.nodes(data=True):
            if data["grid_type"] == "forward":
                color = "red"
                edge_type = "forward"
                grid_type = "forward"
            elif data["grid_type"] == "backward":
                color = "blue"
                edge_type = "backward"
                grid_type = "backward"
            else:
                color = "orange"
                edge_type = "connection"
                grid_type = "connection"
            # Update Knoten
            if graph.degree[node] == 2:
                if len(list(graph.successors(node))) == 1 and len(list(graph.predecessors(node))) == 1:
                    radiator_list = ["radiator_backward", "radiator_forward"]
                    if not set(radiator_list) & set(graph.nodes[node]["type"]):
                        in_edge = list(graph.successors(node))[0]
                        out_edges = list(graph.predecessors(node))[0]
                        if self.is_linear_path(graph=graph,
                                               node1=in_edge,
                                               node2=node,
                                               node3=out_edges) is False:
                            if "Krümmer" not in graph.nodes[node]["type"]:
                                if len(graph.nodes[node]["type"]) == 0:
                                    graph.nodes[node]["type"] = ["Krümmer"]
                                else:
                                    graph.nodes[node]["type"].append("Krümmer")

            if graph.degree[node] == 3 and "Verteiler" not in graph.nodes[node]["type"]:
                in_edge = list(graph.successors(node))
                out_edge = list(graph.predecessors(node))
                if len(in_edge) == 2 and len(out_edge) == 1:
                    if "Trennung" not in graph.nodes[node]["type"]:
                        if len(graph.nodes[node]["type"]) == 0:
                            graph.nodes[node]["type"] = ["Trennung"]
                        else:
                            graph.nodes[node]["type"].append("Trennung")
            if graph.degree[node] == 3 and "Verteiler" not in graph.nodes[node]["type"]:
                in_edge = list(graph.successors(node))
                out_edge = list(graph.predecessors(node))
                if len(in_edge) == 1 and len(out_edge) == 2:
                    if "Vereinigung" not in graph.nodes[node]["type"]:
                        if len(graph.nodes[node]["type"]) == 0:
                            graph.nodes[node]["type"] = ["Vereinigung"]
                        else:
                            graph.nodes[node]["type"].append("Vereinigung")
            if "radiator_backward" in data['type']:
                if "Entlüfter" not in graph.nodes[node]["type"]:
                    graph.nodes[node]["type"].append("Entlüfter")
            # Erweitere Knoten L-System
            # Forward
            strang = data["strang"]
            if one_pump_flag is False:
                type_list = ["Verteiler"]
                if set(type_list).issubset(set(data['type'])):
                    l_rules = "Pumpe"
                    str_chain = l_rules.split("-")

                    in_edge = list(graph.successors(node))
                    out_edge = list(graph.predecessors(node))
                    graph = self.add_components_on_graph(graph=graph,
                                                     node=node,
                                                     str_chain=str_chain,
                                                     z_direction=False,
                                                     color=color,
                                                     edge_type=edge_type,
                                                     neighbors=in_edge,
                                                     grid_type=grid_type,
                                                     strang=strang)
            node_list = ["Verteiler", "start_node"]
            if set(node_list).issubset(set(data['type'])):
                l_rules = "Schwerkraftbremse"
                str_chain = l_rules.split("-")
                in_edge = list(graph.successors(node))
                out_edge = list(graph.predecessors(node))
                graph = self.add_components_on_graph(graph=graph,
                                                 node=node,
                                                 str_chain=str_chain,
                                                 z_direction=True,
                                                 x_direction=False,
                                                 y_direction=False,
                                                 color=color,
                                                 edge_type=edge_type,
                                                 neighbors=in_edge,
                                                 grid_type=grid_type,
                                                 strang=strang)
            if "radiator_forward" in data['type'] and type_delivery == ["window"]:
                l_rules = "Thermostatventil"
                str_chain = l_rules.split("-")
                in_edge = list(graph.successors(node))
                out_edge = list(graph.predecessors(node))
                graph = self.add_components_on_graph(graph=graph,
                                                 node=node,
                                                 edge_type=edge_type,
                                                 str_chain=str_chain,
                                                 color=color,
                                                 z_direction=True,
                                                 x_direction=False,
                                                 y_direction=False,
                                                 neighbors=out_edge,
                                                 grid_type=grid_type,
                                                 strang=strang)
            if "radiator_forward" in data['type'] and type_delivery == ["door"]:
                l_rules = "Magnetventil"
                str_chain = l_rules.split("-")
                in_edge = list(graph.successors(node))
                out_edge = list(graph.predecessors(node))
                graph = self.add_components_on_graph(graph=graph,
                                                 node=node,
                                                 edge_type=edge_type,
                                                 str_chain=str_chain,
                                                 color=color,
                                                 z_direction=False,
                                                 x_direction=True,
                                                 y_direction=True,
                                                 neighbors=out_edge,
                                                 grid_type=grid_type,
                                                 strang=strang)
            # Backward
            node_list = ["end_node"]
            if set(node_list) & set(data['type']):
                l_rules = "Membranausdehnunggefäß" + "-Absperrschieber" + "-Schmutzfänger" + "-Absperrschieber"
                str_chain = l_rules.split("-")
                in_edge = list(graph.successors(node))
                out_edge = list(graph.predecessors(node))
                graph = self.add_components_on_graph(graph=graph,
                                                 node=node,
                                                 str_chain=str_chain,
                                                 z_direction=True,
                                                 x_direction=False,
                                                 y_direction=False,
                                                 color=color,
                                                 lay_from_node=False,
                                                 edge_type=edge_type,
                                                 neighbors=out_edge,
                                                 grid_type=grid_type,
                                                 strang=strang)
            if "radiator_backward" in data['type']:
                l_rules = "Rücklaufabsperrung"
                str_chain = l_rules.split("-")
                in_edge = list(graph.successors(node))
                out_edge = list(graph.predecessors(node))
                graph = self.add_components_on_graph(graph=graph,
                                                 node=node,
                                                 str_chain=str_chain,
                                                 color=color,
                                                 edge_type=edge_type,
                                                 z_direction=True,
                                                 x_direction=True,
                                                 y_direction=True,
                                                 neighbors=in_edge,
                                                 grid_type=grid_type,
                                                 strang=strang)
            # Connection
            # type_list = ["end_node"]
            type_list = ["start_node"]
            if set(type_list).issubset(set(data['type'])):
                color = "orange"
                edge_type = "connection"
                grid_type = "connection"
                # Fall eine Pumpe
                if one_pump_flag is True:
                    l_rules = "heat_source" + "-Pumpe-" + "Sicherheitsventil"
                else:
                    l_rules = "heat_source"
                str_chain = l_rules.split("-")
                in_edge = list(graph.successors(node))
                out_edge = list(graph.predecessors(node))
                graph = self.add_components_on_graph(graph=graph,
                                                 node=node,
                                                 str_chain=str_chain,
                                                 z_direction=False,
                                                 color=color,
                                                 lay_from_node=False,
                                                 edge_type=edge_type,
                                                 neighbors=out_edge,
                                                 grid_type=grid_type,
                                                 source_flag=True,
                                                 strang=strang)

        return graph

    def add_node_if_not_exists(self,
                               graph: nx.Graph(),
                               point):
        """
                Args:
                    graph ():
                    point ():
                Returns:
                """

        for n in graph.nodes():
            if graph.nodes[n]['pos'] == point:
                return n
        else:
            return False

    def is_node_element_on_space_path(self,
                                      graph: nx.Graph(),
                                      node,
                                      node_type_on_path):
        """
                Args:
                    graph ():
                    # Überprüfen, ob ein Fensterknoten eine Verbindung zu einem Spaceknoten hat
                    circulation_direction ():
                Returns:
                """
        for neighbor in graph.neighbors(node):
            if graph.nodes[neighbor]['type'] == node_type_on_path:
                return True
        return False

    def project_nodes_on_building(self, graph: nx.Graph(), grid_type: str, node_list: list, color: str):
        """
                Projeziert Knoten die außerhalb des Gebäudes sind, auf die Gebäude Ebene und löscht den Ursprünglichen Knoten
                Args:
                    graph ():
                    node_list ():
                    color ():
                    grid_type ():
                Returns:
                """
        projected_nodes = []
        room_global_points = []
        poly_nodes = self.get_space_nodes(graph=graph,
                                          element=graph.nodes[node_list[0]]["belongs_to"],
                                          type=["space"])
        for poly in poly_nodes:
            room_global_points.append(graph.nodes[poly]["pos"])
        if len(node_list) > 0 and node_list is not None:
            for i, node in enumerate(node_list):
                projected_window_point = self.nearest_polygon_in_space(graph=graph,
                                                                       node=node,
                                                                       room_global_points=room_global_points)

                if projected_window_point is not None:
                    type_node = graph.nodes[node]["type"]
                    element = graph.nodes[node]["element"]
                    belongs_to = graph.nodes[node]["belongs_to"]
                    floor_id = graph.nodes[node]["floor_belongs_to"]
                    direction = graph.nodes[node]["direction"]
                    graph, project_node = self.create_nodes(graph=graph,
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
                    graph.remove_node(node)
        return graph, projected_nodes

    def create_edges(self,
                     graph: nx.Graph(),
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
                    connect_elements ():  if graph.nodes[node]["element"] == data["element"]:
                    connect_element_together ():
                    nearest_node_flag ():
                    connect_all ():
                    graph ():
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

                        graph = self.nearest_neighbour_edge(graph=graph,
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

        return graph

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

    def check_attribute(self, attribute):
        attr = attribute
        if isinstance(attribute, str):
            attr = [attribute]
        if isinstance(attribute, list):
            attr = attribute
        return attr

    def generate_unique_node_id(self, graph, floor_id):
        highest_id = -1
        prefix = f"floor{floor_id}_"
        for node in graph.nodes:
            try:
                # if node.startswith(prefix):
                if isinstance(node, str) and node.startswith(prefix):
                    node_id = int(node[len(prefix):])
                    highest_id = max(highest_id, node_id)
            except ValueError:
                pass
        new_id = highest_id + 1
        return f"{prefix}{new_id}"

    def create_nodes(self,
                     graph: nx.Graph(),
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
                    graph (): Networkx Graphen
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
            for node in graph.nodes():
                if abs(distance.euclidean(graph.nodes[node]['pos'], node_pos)) <= tol_value:
                    belongs_to_list = self.attr_node_list(entry=belongs_to,
                                                          attr_list=graph.nodes[node]['belongs_to'])
                    element_list = self.attr_node_list(entry=element,
                                                       attr_list=graph.nodes[node]['element'])
                    type_list = self.attr_node_list(entry=type_node,
                                                    attr_list=graph.nodes[node]['type'])
                    graph.nodes[node].update({
                        'element': element_list,
                        'color': color,
                        'type': type_list,
                        'direction': direction,
                        "belongs_to": belongs_to_list,
                        'strang': strang
                        # 'floor_belongs_to': floor_belongs_to
                    })
                    return graph, node
        belongs = self.check_attribute(attribute=belongs_to)
        ele = self.check_attribute(attribute=element)
        type = self.check_attribute(attribute=type_node)
        # id_name = self.generate_unique_node_id(graph=graph, floor_id=floor_belongs_to)
        graph.add_node(node_pos,
                   pos=node_pos,
                   color=color,
                   type=type,
                   grid_type=grid_type,
                   element=ele,
                   belongs_to=belongs,
                   direction=direction,
                   floor_belongs_to=floor_belongs_to,
                   strang=strang)
        return graph, node_pos

    def filter_edges(self,
                     graph: nx.Graph(),
                     node: nx.Graph().nodes(),
                     connect_type_edges: list = None,
                     all_edges_flag: bool = False,
                     all_edges_floor_flag: bool = False,
                     same_type_flag: bool = False,
                     element_belongs_to_flag: bool =False,
                     belongs_to_floor=None):
        """
                Args:
                    exception_type_node (): Beachtet explizit diese Knoten und Kanten nicht.
                    graph (): Networkx Graph
                    connect_type_edges ():
                    node (): Knoten, der mit dem Graphen verbunden werden soll.
                    all_edges_flag (): Sucht alle Kanten eines Graphen
                    all_edges_floor_flag (): Sucht alle Kanten einer Etage eines Graphen
                    same_type_flag (): Sucht alle Kanten, die den gleichen Knoten Type haben (bspw. Space)
                    element_belongs_to_flag ():
                    belongs_to_floor (): ID einer Etage

                Returns:
                """
        edge_list = []
        for edge in graph.edges(data=True):
            type_edge = nx.get_edge_attributes(graph, 'type')[(edge[0], edge[1])]
            if edge[0] != node and edge[1] != node:
                # Beachtet alle Kanten des Graphens.
                if all_edges_flag is True:
                    if (edge[0], edge[1]) not in edge_list:
                        edge_list.append((edge[0], edge[1]))
                # Beachtet alle Kanten der Etage des Graphens.
                elif all_edges_floor_flag is True:
                    if belongs_to_floor == graph.nodes[edge[0]]["floor_belongs_to"] == graph.nodes[edge[1]]["floor_belongs_to"]:
                        if (edge[0], edge[1]) not in edge_list:
                            edge_list.append((edge[0], edge[1]))
                # Beachtet alle Kanten mit dem gleichen Typknoten des Graphens.
                elif same_type_flag is True:
                    if type_edge in set(connect_type_edges):
                        if (edge[0], edge[1]) not in edge_list:
                            edge_list.append((edge[0], edge[1]))
                elif element_belongs_to_flag is True:
                    if type_edge in set(connect_type_edges):
                        if set(graph.nodes[edge[0]]["element"]) & set(graph.nodes[edge[1]]["element"]) & set(
                                graph.nodes[node]["belongs_to"]):
                            if (edge[0], edge[1]) not in edge_list:
                                edge_list.append((edge[0], edge[1]))
                        if set(graph.nodes[edge[0]]["element"]) & set(graph.nodes[node]["belongs_to"]) & set(
                                graph.nodes[edge[1]]["belongs_to"]):
                            if (edge[0], edge[1]) not in edge_list:
                                edge_list.append((edge[0], edge[1]))
                        if set(graph.nodes[edge[1]]["element"]) & set(graph.nodes[edge[0]]["belongs_to"]) & set(
                                graph.nodes[node]["belongs_to"]):
                            if (edge[0], edge[1]) not in edge_list:
                                edge_list.append((edge[0], edge[1]))
                        if set(graph.nodes[edge[0]]["belongs_to"]) & set(graph.nodes[node]["belongs_to"]) & set(
                                graph.nodes[edge[1]]["belongs_to"]):
                            if (edge[0], edge[1]) not in edge_list:
                                edge_list.append((edge[0], edge[1]))
                        if set(graph.nodes[edge[0]]["element"]) & set(graph.nodes[node]["element"]) & set(
                                graph.nodes[edge[1]]["element"]):
                            if (edge[0], edge[1]) not in edge_list:
                                edge_list.append((edge[0], edge[1]))

        return edge_list

    def filter_nodes(self,
                     graph: nx.Graph(),
                     connect_node_flag: bool = False,
                     nearest_node_flag: bool = True,
                     connect_element_together: bool = False,
                     connect_floor_spaces_together: bool = False,
                     connect_types_flag: bool = False,
                     all_node_flag: bool = False):
        pass

    def create_space_grid(self,
                          graph: nx.Graph(),
                          room_data,
                          room_ID,
                          color,
                          grid_type,
                          edge_type,
                          floor_belongs_to,
                          tol_value: float,
                          update_node: bool = False,
                          direction_x: bool = True,
                          direction_y: bool = True,
                          direction_z: bool = True,
                          connect_element_together: bool = True,
                          connect_floors: bool = False,
                          nearest_node_flag: bool = True,
                          node_type=None,
                          connect_node_flag: bool = False,
                          disjoint_flag: bool = False,
                          intersects_flag: bool = True,
                          within_flag: bool = False,
                          col_tol: float = 0.1,
                          collision_type_node: list = ["space"]
                          ):
        """

                Args:
                    graph ():
                    room_data ():
                    room_ID ():
                    color ():
                    grid_type ():
                    edge_type ():
                    floor_belongs_to ():
                    tol_value ():
                    update_node ():
                    direction_x ():
                    direction_y ():
                    direction_z ():
                    connect_element_together ():
                    connect_floors ():
                    connect_grid ():
                    connect_elements ():
                    nearest_node_flag ():
                    connect_all ():
                    node_type ():
                    connect_node_flag ():

                Returns:

                """

        room_global_corners = room_data["global_corners"]
        room_belong_to = room_data["belongs_to"]
        direction = room_data["direction"]
        type_node = room_data["type"]
        space_nodes = []
        # Erstellt Knoten für einen Space/Wand
        if room_global_corners is not None:
            for i, points in enumerate(room_global_corners):
                graph, nodes = self.create_nodes(graph=graph,
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
            graph = self.create_edges(graph=graph,
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
        return graph, space_nodes

    def get_space_nodes(self, graph, element, type):
        room_nodes = []
        for node, data in graph.nodes(data=True):
            if set(element) & set(data["element"]) and set(type) & set(data["type"]):
                room_nodes.append(node)
        return room_nodes

    def create_element_grid(self,
                            graph: nx.Graph(),
                            element_data,
                            element_ID,
                            color_nodes: str,
                            color_edges: str,
                            edge_type: str,
                            grid_type: str,
                            tol_value: float,
                            floor_belongs_to,
                            connect_create_flag: bool = True):
        """

                Args:
                    graph ():
                    element_data ():
                    element_ID ():
                    color ():
                    grid_type ():
                    tol_value ():
                    floor_belongs_to ():
                    connect_create_flag ():

                Returns:

                """
        element_global_corner = element_data["global_corners"]
        element_belongs_to = element_data["belongs_to"]
        type_node = element_data["type"]
        element_nodes = []
        # Punkte erstellen oder aktualisieren
        for i, points in enumerate(element_global_corner):
            graph, nodes = self.create_nodes(graph=graph,
                                         grid_type=grid_type,
                                         points=points,
                                         color=color_nodes,
                                         type_node=type_node,
                                         element=element_ID,
                                         belongs_to=element_belongs_to,
                                         direction=element_data["direction"],
                                         floor_belongs_to=floor_belongs_to,
                                         update_node=True)
            if nodes not in element_nodes:
                element_nodes.append(nodes)
        # Projiziert Elemente Knoten (Fenster, ) auf Raum Ebene (Erstellt diese auf der Gebäude Ebene)
        graph, projected_nodes = self.project_nodes_on_building(graph=graph,
                                                            grid_type=grid_type,
                                                            node_list=element_nodes,
                                                            color=color_nodes)
        # Löscht Knoten die aufeinander liegen
        if projected_nodes is not None and len(projected_nodes) > 0:
            graph, projected_nodes = self.delete_duplicate_nodes(graph=graph,
                                                             duplicated_nodes=projected_nodes)
            # Erstellt Kanten für Elemente (Fenster nur untereinander)
            if connect_create_flag is True:
                graph = self.create_edges(graph=graph,
                                      node_list=projected_nodes,
                                      edge_type=edge_type,
                                      grid_type=grid_type,
                                      tol_value=tol_value,
                                      color=color_edges,
                                      direction_x=True,
                                      direction_y=True,
                                      direction_z=True,
                                      connect_element_together=True,
                                      intersects_flag=False)
        return graph, projected_nodes

    def connect_nodes_with_grid(self,
                                graph: nx.Graph(),
                                node_list: list,
                                color: str,
                                type_node: list,
                                grid_type: str,
                                new_edge_type: str,
                                remove_type_node: list,
                                edge_snapped_node_type: str,
                                neighbor_nodes_collision_type: list = None,
                                belongs_to_floor=None,

                                # filter_edges
                                all_edges_flag: bool = False,
                                all_edges_floor_flag: bool = False,
                                same_type_flag: bool = False,
                                element_belongs_to_flag: bool = False,
                                connect_type_edges: list = None,
                                # snapping
                                update_node: bool = True,
                                bottom_z_flag: bool = True,
                                top_z_flag: bool = True,
                                pos_x_flag: bool = True,
                                neg_x_flag: bool = True,
                                pos_y_flag: bool = True,
                                neg_y_flag: bool = True,
                                no_neighbour_collision_flag: bool = True,
                                tol_value: float = 0.0,
                                snapped_not_same_type_flag: bool = False,
                                # collision
                                collision_type_node: list = ["space"],

                                disjoint_flag: bool = False,
                                intersects_flag: bool = False,
                                within_flag: bool = False,
                                collision_flag: bool = True,
                                col_tolerance: float = 0.1,
                                create_snapped_edge_flag: bool = True):
        """
                Args:
                    connect_type_edges (): Typ von Kanten, die betrachtet oder explizit nicht betrachtet werden sollen
                    update_node (): True: Aktualisiert Knoten, erstellt keinen Neuen Knoten, wenn auf der Position schon ein Knoten ist
                    collision_type_node (): Bspw. ["space"]
                    top_z_flag (): Falls False: Sucht nur in negativer z richtung
                    z_flag (): Betrachtet Kanten in Z-Richtung
                    x_flag (): Betrachtet Kanten in X-Richtung
                    y_flag (): Betrachtet Kanten in Y-Richtung
                    graph (): Networkx Graph
                    node_list (): Liste von Knoten die mit dem Graphen verbunden werden
                    color (): Farbe der Knoten, die neu erstellt werden
                    type_node (): Typ Art der neu erstellten Knoten

                    Suchen der Kanten, auf die ein neuer Knoten gesnappt werden kann.
                    all_edges_flag (): Betrachtet alle Kanten eines Graphen graph
                    all_edges_floor_flag (): Betrachtet alle Kanten der Etage eines Graphen graph
                    same_type_flag (): Sucht alle Kanten, die den gleichen Knoten Type haben (bspw. Space)
                    belongs_to_floor ():

                    type_node ():

                    direction_x (): Legt Kanten Richtung X
                    direction_y (): Legt Kanten Richtung Y
                    direction_z (): Legt Kanten Richtung Z
                    disjoint_flag (): bool: Schnittstelle und auf der Kante
                    intersects_flag ():
                    within_flag (): bool. schnittstelle drinnen
                    element_belongs_to_flag ():
                    belongs_to_floor ():
                Returns:
                """

        direction_flags = [top_z_flag, bottom_z_flag, pos_x_flag, neg_x_flag, pos_y_flag, neg_y_flag]
        nodes = []
        print(f"Number of snapped nodes {len(node_list)}")
        for i, node in enumerate(node_list):
            print(f"Number node ({i + 1}/{len(node_list)})")
            # Sucht alle Kanten, auf die ein Knoten gesnappt werden kann.
            for j, direction in enumerate(direction_flags):
                direction_flags = [top_z_flag, bottom_z_flag, pos_x_flag, neg_x_flag, pos_y_flag, neg_y_flag]
                for k, flag in enumerate(direction_flags):
                    if j == k:
                        direction_flags[k] = flag
                        # Setze alle anderen Flags auf False (für jeden anderen Index k außer j)
                    else:
                        direction_flags[k] = False

                if not any(direction_flags):
                    continue
                edge_space_list = self.filter_edges(graph=graph,
                                                    node=node,
                                                    all_edges_flag=all_edges_flag,
                                                    all_edges_floor_flag=all_edges_floor_flag,
                                                    same_type_flag=same_type_flag,
                                                    belongs_to_floor=belongs_to_floor,
                                                    element_belongs_to_flag=element_belongs_to_flag,
                                                    connect_type_edges=connect_type_edges)
                nearest_lines, new_node_pos = self.nearest_edges(graph=graph,
                                                                 node=node,
                                                                 points=graph.nodes[node]["pos"],
                                                                 edges=edge_space_list,
                                                                 top_z_flag=direction_flags[0],
                                                                 bottom_z_flag=direction_flags[1],
                                                                 pos_x_flag=direction_flags[2],
                                                                 neg_x_flag=direction_flags[3],
                                                                 pos_y_flag=direction_flags[4],
                                                                 neg_y_flag=direction_flags[5],
                                                                 tol_value=tol_value)
                if new_node_pos is not None:
                    direction = graph.get_edge_data(nearest_lines[0][0], nearest_lines[0][1])["direction"]
                    graph, snapped_node = self.create_snapped_nodes(graph=graph,
                                                           node=node,
                                                           new_snapped_node=new_node_pos,
                                                           color=color,
                                                           grid_type=grid_type,
                                                           type_node=type_node,
                                                           element=graph.nodes[node]["element"],
                                                           belongs_to=graph.nodes[node]["belongs_to"],
                                                           floor_belongs_to=graph.nodes[node]["floor_belongs_to"],
                                                           update_node=update_node,
                                                           disjoint_flag=disjoint_flag,
                                                           intersects_flag=intersects_flag,
                                                           within_flag=within_flag,
                                                           collision_type_node=collision_type_node,
                                                           direction=direction,
                                                           col_tolerance=col_tolerance,
                                                           no_neighbour_collision_flag=no_neighbour_collision_flag,
                                                           collision_flag=collision_flag,
                                                           neighbor_nodes_collision_type=neighbor_nodes_collision_type)
                    if create_snapped_edge_flag is True and snapped_node is not None:
                        nodes.append(snapped_node)
                        graph = self.create_edge_snapped_nodes(graph=graph,
                                                           node=node,
                                                           edge_type_node=connect_type_edges,
                                                           remove_type_node=remove_type_node,
                                                           snapped_node=snapped_node,
                                                           color=color,
                                                           edge_snapped_node_type=edge_snapped_node_type,
                                                           new_edge_type=new_edge_type,
                                                           grid_type=grid_type,
                                                           direction=direction,
                                                           snapped_edge=nearest_lines,
                                                           no_neighbour_collision_flag=no_neighbour_collision_flag,
                                                           neighbor_nodes_collision_type=neighbor_nodes_collision_type,
                                                           snapped_not_same_type_flag=snapped_not_same_type_flag)

        return graph, nodes

    def create_overlapped_edge(self,
                               graph: nx.Graph(),
                               connected_node: nx.Graph().nodes(),
                               edge_type: str,
                               color: str,
                               edge_1: nx.Graph().edges(),
                               edge_2: nx.Graph().edges(),
                               edge_3: nx.Graph().edges(),
                               edge_4: nx.Graph().edges(),
                               grid_type: str
                               ):
        pos = graph.nodes[connected_node]["pos"]
        # edge_1
        if graph.has_edge(connected_node, edge_1) is False:  # and graph.has_edge(edge_1, connected_node) is False:
            length = abs(distance.euclidean(graph.nodes[edge_1]["pos"], pos))
            graph.add_edge(connected_node,
                       edge_1,
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       direction=graph.nodes[edge_1]["direction"],
                       length=length)
        # edge_2
        if graph.has_edge(edge_2, connected_node) is False:  # and graph.has_edge(connected_node, edge_2) is False:
            length = abs(distance.euclidean(graph.nodes[edge_2]["pos"], pos))
            graph.add_edge(edge_2,
                       connected_node,
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       direction=graph.nodes[edge_2]["direction"],
                       length=length)
        # edge_3
        if graph.has_edge(connected_node, edge_3) is False:  # and graph.has_edge(edge_3, connected_node) is False:
            length = abs(distance.euclidean(graph.nodes[edge_3]["pos"], pos))
            graph.add_edge(connected_node,
                       edge_3,
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       direction=graph.nodes[edge_3]["direction"],
                       length=length)
        # edge_4
        if graph.has_edge(connected_node, edge_4) is False:  # and graph.has_edge(edge_4, connected_node) is False:
            length = abs(distance.euclidean(graph.nodes[edge_4]["pos"], pos))
            graph.add_edge(connected_node,
                       edge_4,
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       direction=graph.nodes[edge_4]["direction"],
                       length=length)
        return graph

    def delte_overlapped_edge(self,
                              graph: nx.Graph(),
                              edge_1: nx.Graph().edges(),
                              edge_2: nx.Graph().edges(),
                              edge_3: nx.Graph().edges(),
                              edge_4: nx.Graph().edges()):
        """
                Args:
                    graph ():
                    edge_1 ():
                    edge_2 ():
                    edge_3 ():
                    edge_4 ():
                Returns:
                """
        # Lösche alte Kanten
        if graph.has_edge(edge_1, edge_2):
            graph.remove_edge(edge_1, edge_2)
        if graph.has_edge(edge_2, edge_1):
            graph.remove_edge(edge_2, edge_1)
        if graph.has_edge(edge_3, edge_4):
            graph.remove_edge(edge_3, edge_4)
        if graph.has_edge(edge_4, edge_3):
            graph.remove_edge(edge_4, edge_3)

        return graph

    def edge_overlap(self,
                     graph: nx.Graph(),
                     color: str,
                     type_node: list,
                     edge_type: str,
                     delete_degree: int,
                     grid_type: str):
        """

                Args:
                    graph ():
                    color ():
                    type_node ():
                    edge_type ():
                    delete_degree ():
                    grid_type ():

                Returns:

                """
        edges = list(graph.edges())
        index = 0
        num_edges_before = len(edges)
        remove_node_list = []
        intersect_node_list = []
        while index < len(edges):
            edge = edges[index]
            graph, node_list, intersect_node = self.create_node_on_edge_overlap(graph=graph,
                                                                            color=color,
                                                                            e1=edge,
                                                                            grid_type=grid_type,
                                                                            type_node=type_node,
                                                                            type_flag=True,
                                                                            edge_type=edge_type)
            if intersect_node is not None and intersect_node not in intersect_node_list:
                intersect_node_list.append(intersect_node)
            for n in node_list:
                if n not in remove_node_list:
                    remove_node_list.append(n)
            index += 1
            num_edges_after = len(graph.edges())
            if num_edges_after > num_edges_before:
                # Neue Kanten wurden hinzugefügt
                new_edges = list(set(graph.edges()) - set(edges))
                for new in new_edges:
                    edges.append(new)
                # Kanten wurden gelöscht
                """deleted_edges = list(set(edges) - set(graph.edges()))
                        for del_edge in deleted_edges:
                            edges.remove(del_edge)"""
            num_edges_before = num_edges_after
        node_list = []
        for node in remove_node_list:
            if graph.degree(node) <= delete_degree:
                edge = graph.edges(node)
                for e in edge:
                    if graph.nodes[e[0]]["pos"][2] == graph.nodes[e[1]]["pos"][2]:
                        if graph.edges[(e[0], e[1])]["length"] <= 0.3:
                            if node not in node_list:
                                node_list.append(node)
        graph.remove_nodes_from(node_list)
        graph = self.create_edges(graph=graph,
                              node_list=intersect_node_list,
                              color=color,
                              edge_type=edge_type,
                              grid_type=grid_type,
                              direction_x=False,
                              direction_y=False,
                              direction_z=True,
                              tol_value=0.0,
                              connect_types_element=False,
                              connect_element_together=False,
                              connect_types=True,
                              nearest_node_flag=True,
                              node_type=type_node,
                              connect_node_flag=False,
                              disjoint_flag=False,
                              intersects_flag=False,
                              within_flag=False
                              )

        return graph

    def create_intersect_node(self,
                              graph: nx.Graph(),
                              node: nx.Graph().nodes(),
                              color: str,
                              grid_type: str,
                              pos: tuple,
                              type_node: list):

        graph, intersect_node = self.create_nodes(graph=graph,
                                              points=pos,
                                              color=color,
                                              grid_type=grid_type,
                                              type_node=type_node,
                                              element=graph.nodes[node]["element"],
                                              belongs_to=graph.nodes[node]["belongs_to"],
                                              direction=graph.nodes[node]["direction"],
                                              update_node=True,
                                              floor_belongs_to=graph.nodes[node][
                                                  "floor_belongs_to"])
        return graph, intersect_node

    # def create_building_floor_nx_networkx(self):

    def create_building_graph(self,
                                   grid_type: str,
                                   # edge_type: str,
                                   color: str = "red",
                                   laying_guide: str = "center_wall",
                                   tol_value: float = 0.0):
        """
                Args:

                    points ():
                    circulation_direction ():
                    type_node ():
                    **args ():
                Returns:
                """
        print("Creates nodes for each room independently")
        floor_graph_list = []
        for i, floor_id in enumerate(self.floor_dict):
            graph = nx.Graph(grid_type="building")
            for room in self.floor_dict[floor_id]["rooms"]:
                room_data = self.floor_dict[floor_id]["rooms"][room]
                room_elements = room_data["room_elements"]
                graph, space_nodes = self.create_space_grid(graph=graph,
                                                        room_data=room_data,
                                                        room_ID=room,
                                                        color="grey",
                                                        tol_value=tol_value,
                                                        edge_type="space",
                                                        grid_type="space",
                                                        floor_belongs_to=floor_id,
                                                        update_node=False,
                                                        direction_x=True,
                                                        direction_y=True,
                                                        direction_z=True,
                                                        connect_element_together=True,
                                                        connect_floors=False,
                                                        nearest_node_flag =True,
                                                        connect_node_flag=False,
                                                        intersects_flag=False)

                """
                        Erstellt Fenster und Tür Element von Raum r
                        """
                for element in room_elements:
                    print(f"Create element structure {element} for floor {floor_id}")
                    if room_elements[element]["type"] == "wall":
                        print(f"Create wall structure {element} for floor {floor_id}")
                        if room_elements[element]["global_corners"] is not None:
                            graph, center_wall = self.center_element(graph=graph,
                                                                 global_corners=room_elements[element][
                                                                     "global_corners"],
                                                                 color_nodes="grey",
                                                                 color_edges="grey",
                                                                 offset=0.75,
                                                                 belongs_to=room_elements[element]["belongs_to"],
                                                                 room_ID=element,
                                                                 edge_type="center_wall_forward",
                                                                 grid_type="center_wall_forward",
                                                                 node_type=["center_wall_forward"],
                                                                 floor_belongs_to=floor_id,
                                                                 tol_value=0.0,
                                                                 update_node=True,
                                                                 direction_x=True,
                                                                 direction_y=True,
                                                                 direction_z=True)

                    if room_elements[element]["type"] == "window":
                        if room_elements[element]["global_corners"] is not None:
                            # Projiziert Knoten auf nächstes Polygon
                            graph, projected_nodes = self.create_element_grid(graph=graph,
                                                                          edge_type="window",
                                                                          element_data=room_elements[element],
                                                                          element_ID=element,
                                                                          tol_value=tol_value,
                                                                          color_nodes="grey",
                                                                          color_edges="orange",
                                                                          grid_type=grid_type,
                                                                          floor_belongs_to=floor_id)
                            # Verbindet Projezierte Knoten über Snapping an die nächste Kante
                            if projected_nodes is not None and len(projected_nodes) > 0:
                                graph, snapped_nodes = self.connect_nodes_with_grid(graph=graph,
                                                                                node_list=projected_nodes,
                                                                                color="grey",
                                                                                # filter_edges
                                                                                all_edges_flag=False,
                                                                                all_edges_floor_flag=False,
                                                                                same_type_flag=False,
                                                                                belongs_to_floor=None,
                                                                                element_belongs_to_flag=True,
                                                                                connect_type_edges=["space"],
                                                                                # nearest_edges
                                                                                top_z_flag=False,
                                                                                bottom_z_flag=True,
                                                                                pos_x_flag=False,
                                                                                neg_x_flag=False,
                                                                                pos_y_flag=False,
                                                                                neg_y_flag=False,
                                                                                tol_value=0.0,
                                                                                # create_snapped_nodes
                                                                                update_node=True,
                                                                                # check_collision
                                                                                disjoint_flag=False,
                                                                                intersects_flag=True,
                                                                                within_flag=False,
                                                                                col_tolerance=0.1,
                                                                                collision_type_node=["space"],
                                                                                collision_flag=True,
                                                                                # check_neighbour_nodes_collision
                                                                                # type_node=["snapped_window_nodes"],
                                                                                type_node=["snapped_nodes"],
                                                                                neighbor_nodes_collision_type=[
                                                                                    "snapped_nodes",
                                                                                    "window"],
                                                                                # create_edge_snapped_nodes
                                                                                # edge_snapped_node_type="construction_edge",
                                                                                edge_snapped_node_type="construction_edge",
                                                                                remove_type_node=["space",
                                                                                                  "snapped_nodes"],
                                                                                grid_type="forward",
                                                                                new_edge_type="space",
                                                                                create_snapped_edge_flag=True)
                    if room_elements[element]["type"] == "door":
                        if room_elements[element]["global_corners"] is not None:
                            # Projiziert Knoten auf nächstes Polygon
                            graph, projected_nodes = self.create_element_grid(graph=graph,
                                                                          edge_type="door",
                                                                          element_data=room_elements[element],
                                                                          element_ID=element,
                                                                          tol_value=tol_value,
                                                                          color_nodes="grey",
                                                                          color_edges="green",
                                                                          grid_type=grid_type,
                                                                          floor_belongs_to=floor_id)
                            # Verbindet projizierte Knoten über Snapping an die nächste Kante
                            if projected_nodes is not None and len(projected_nodes) > 0:
                                graph, snapped_nodes = self.connect_nodes_with_grid(  # General
                                    graph=graph,
                                    node_list=projected_nodes,
                                    color="grey",
                                    # filter_edges
                                    all_edges_flag=False,
                                    all_edges_floor_flag=False,
                                    same_type_flag=False,
                                    belongs_to_floor=None,
                                    element_belongs_to_flag=True,
                                    connect_type_edges=["space"],
                                    # nearest_edges
                                    top_z_flag=False,
                                    bottom_z_flag=True,
                                    pos_x_flag=False,
                                    neg_x_flag=False,
                                    pos_y_flag=False,
                                    neg_y_flag=False,
                                    tol_value=0.1,
                                    # create_snapped_nodes
                                    update_node=True,
                                    # check_collision
                                    disjoint_flag=False,
                                    intersects_flag=True,
                                    within_flag=False,
                                    col_tolerance=0.1,
                                    collision_type_node=["space"],
                                    collision_flag=True,
                                    # check_neighbour_nodes_collision
                                    type_node=["snapped_nodes"],
                                    neighbor_nodes_collision_type=[],
                                    snapped_not_same_type_flag=True,
                                    # create_edge_snapped_nodes
                                    edge_snapped_node_type="construction_edge",
                                    remove_type_node=["space",
                                                      "snapped_nodes"],
                                    grid_type="forward",
                                    new_edge_type="space",
                                    create_snapped_edge_flag=True)

            """
                    Entfernte überschneidene Kanten und erstellt neue
                    """
            print(f"Solve Overlapping edges for floor {floor_id}")
            graph = self.edge_overlap(graph=graph,
                                  delete_degree=3,
                                  color="grey",
                                  type_node=["center_wall_forward"],
                                  edge_type="center_wall_forward",
                                  grid_type="forward")

            """
                    Erstelle neue Hilfsknoten Knoten miteinander
                    """
            nodes = ["center_wall_forward", "snapped_nodes"]
            snapped_nodes = []
            for node, data in graph.nodes(data=True):
                if set(data["type"]) & set(nodes) and data["floor_belongs_to"] == floor_id:
                    snapped_nodes.append(node)
            graph, nodes = self.connect_nodes_with_grid(graph=graph,
                                                    node_list=snapped_nodes,
                                                    color="grey",
                                                    # filter_edges
                                                    all_edges_flag=False,
                                                    all_edges_floor_flag=False,
                                                    same_type_flag=True,
                                                    belongs_to_floor=None,
                                                    element_belongs_to_flag=False,
                                                    connect_type_edges=["center_wall_forward"],
                                                    # nearest_edges
                                                    top_z_flag=False,
                                                    bottom_z_flag=False,
                                                    pos_x_flag=True,
                                                    neg_x_flag=True,
                                                    pos_y_flag=True,
                                                    neg_y_flag=True,
                                                    tol_value=0.0,
                                                    # create_snapped_nodes
                                                    update_node=True,
                                                    # type_node=["center_wall_forward"],
                                                    type_node=["center_wall_forward"],
                                                    # type_node=["snapped_window_nodes"],
                                                    # check_collision
                                                    disjoint_flag=False,
                                                    intersects_flag=True,
                                                    within_flag=False,
                                                    col_tolerance=0.1,
                                                    collision_type_node=["space"],
                                                    collision_flag=True,
                                                    # check_neighbour_nodes_collision
                                                    neighbor_nodes_collision_type=["space",
                                                                                   "snapped_nodes"],
                                                    # create_edge_snapped_nodes
                                                    edge_snapped_node_type="center_wall_forward",
                                                    remove_type_node=["center_wall_forward"],
                                                    grid_type="forward",
                                                    new_edge_type="center_wall_forward",
                                                    create_snapped_edge_flag=True)
            """
                    Verbinde neue Hilfsknoten mit Kanten miteinander
                    """
            print(f"Connect elements with center_wall_forward for floor {floor_id}")
            graph = self.create_edges(graph=graph,
                                  node_list=snapped_nodes,
                                  edge_type="center_wall_forward",
                                  grid_type="forward",
                                  tol_value=tol_value,
                                  direction_x=True,
                                  direction_y=True,
                                  direction_z=True,
                                  connect_types=True,
                                  color="grey",
                                  col_tol=0.1,
                                  node_type=["center_wall_forward", "snapped_nodes"],
                                  no_neighbour_collision_flag=True,
                                  neighbor_nodes_collision_type=["space"])


            """
                    Entferne Knoten eines bestimmten Typs, Speichert diese und check anschließend ob Graph zusammenhängend ist
                    """
            nodes = ["center_wall_forward", "snapped_nodes", "door", "window"]
            subgraph_nodes = [n for n, attr in graph.nodes(data=True) if any(t in attr.get("type", []) for t in nodes)]
            H = graph.subgraph(subgraph_nodes)
            H = H.copy()
            attribute_type_to_remove = 'space'
            edges_to_remove = []
            for u, v, attr in H.edges(data=True):
                if attr.get('type') == attribute_type_to_remove:
                    edges_to_remove.append((u, v))
            H.remove_edges_from(edges_to_remove)
            self.write_json_graph(graph=graph,
                                  filename=f"{floor_id}_floor.json")

            H = self.check_graph(graph=H, type=f"Floor_{i}_forward")
            # GeometryBuildingsNetworkx.visulize_networkx(graph=graph)
            # GeometryBuildingsNetworkx.visulize_networkx(graph=H)
            # plt.show()
            floor_graph_list.append(H)
        """
                Erstellt Hauptgraphen aus Teilgraphen
                Verbindet unzusammenhängenden Hauptgraph über zentrierte Wände
                """
        graph = self.add_graphs(graph_list=floor_graph_list)
        center_wall_nodes = [n for n, attr in graph.nodes(data=True) if
                             any(t in attr.get("type", []) for t in ["center_wall_forward"])]
        graph = self.create_edges(graph=graph,
                              node_list=center_wall_nodes,
                              edge_type="center_wall_forward",
                              grid_type="forward",
                              tol_value=tol_value,
                              direction_x=False,
                              direction_y=False,
                              direction_z=True,
                              connect_types=True,
                              color="grey",
                              col_tol=0.1,
                              node_type=["center_wall_forward"])
        graph = self.check_graph(graph=graph, type=f"Building")

        self.write_json_graph(graph=graph,
                              filename="network_building.json")
        
        # GeometryBuildingsNetworkx.visulize_networkx(graph=graph)
        # plt.show()
        return graph

    def is_collision(self, point1, point2, existing_edges):
        for edge in existing_edges:
            if (point1 == edge[0] and point2 == edge[1]) or (point1 == edge[1] and point2 == edge[0]):
                return True
        return False

    def create_snapped_nodes(self,
                             graph: nx.Graph(),
                             node: nx.Graph().nodes(),
                             grid_type: str,
                             new_snapped_node: tuple,
                             color: str,
                             type_node: list,
                             element: str,
                             belongs_to: str,
                             floor_belongs_to: str,
                             direction: str,
                             neighbor_nodes_collision_type: list,
                             tol_value: float = 0.0,
                             collision_type_node: list = ["space"],
                             update_node: bool = True,
                             disjoint_flag: bool = False,
                             intersects_flag: bool = True,
                             within_flag: bool = False,
                             col_tolerance: float = 0.1,
                             collision_flag: bool = True,
                             no_neighbour_collision_flag: bool = True
                             ):
        """
                Args:
                    graph (): Networkx Graphen
                    node (): Knoten, der verbunden werden soll
                    new_snapped_node (): Gesnappter Knoten
                    color (): Farbe des Knoten und der Kante
                    type_node (): Typ des Knotens
                    element (): Element des Knotens
                    grid_type (): Art des Netzes
                    belongs_to (): Knoten gehört zu Hauptelement (Space)
                    floor_belongs_to (): Knoten gehört zu Etage ID
                    snapped_edge (): Linie auf die der gesnappte Knoten gesnappt werden soll
                    edge_type_node ():
                    direction_x ():
                    direction_y ():
                    direction_z ():
                    tol_value ():
                    collision_type_node ():
                    update_node ():
                    disjoint_flag ():
                    intersects_flag ():
                    within_flag ():
                    create_snapped_edge_flag ():
                    col_tolerance ():
                    collision_flag ():

                Returns:
                """
        snapped_node = None
        if self.check_collision(graph=graph,
                                edge_point_A=graph.nodes[node]["pos"],
                                edge_point_B=new_snapped_node,
                                disjoint_flag=disjoint_flag,
                                intersects_flag=intersects_flag,
                                within_flag=within_flag,
                                tolerance=col_tolerance,
                                collision_type_node=collision_type_node,
                                collision_flag=collision_flag) is False:

            if self.check_neighbour_nodes_collision(graph=graph,
                                                    edge_point_A=graph.nodes[node]["pos"],
                                                    edge_point_B=new_snapped_node,
                                                    neighbor_nodes_collision_type=neighbor_nodes_collision_type,
                                                    no_neighbour_collision_flag=no_neighbour_collision_flag) is False:
                graph, snapped_node = self.create_nodes(graph=graph,
                                               points=new_snapped_node,
                                               color=color,
                                               grid_type=grid_type,
                                               type_node=type_node,
                                               element=element,
                                               belongs_to=belongs_to,
                                               floor_belongs_to=floor_belongs_to,
                                               direction=direction,
                                               tol_value=tol_value,
                                               update_node=update_node)
        return graph, snapped_node

    def create_edge_snapped_nodes(self,
                                  graph: nx.Graph(),
                                  node,
                                  remove_type_node: list,
                                  edge_type_node,
                                  snapped_node,
                                  color: str,
                                  edge_snapped_node_type: str,
                                  new_edge_type,
                                  grid_type,
                                  direction,
                                  snapped_edge,
                                  no_neighbour_collision_flag: bool = True,
                                  neighbor_nodes_collision_type: list = None,
                                  snapped_not_same_type_flag: bool = False,
                                  ):
        """

                Args:
                    graph ():
                    node ():
                    edge_type_node ():
                    snapped_node ():
                    color ():
                    new_edge_type ():
                    grid_type ():
                    direction ():
                    snapped_edge ():

                Returns:

                """
        if graph.has_edge(snapped_edge[0][0], snapped_edge[0][1]):
            graph.remove_edge(snapped_edge[0][0], snapped_edge[0][1])
        if graph.has_edge(snapped_edge[0][1], snapped_edge[0][0]):
            graph.remove_edge(snapped_edge[0][1], snapped_edge[0][0])
        if snapped_edge[0][0] != snapped_node:
            graph.add_edge(snapped_edge[0][0],
                       snapped_node,
                       color=color,
                       type=new_edge_type,
                       grid_type=grid_type,
                       direction=direction,
                       length=abs(
                           distance.euclidean(graph.nodes[snapped_edge[0][0]]["pos"], graph.nodes[snapped_node]["pos"])))
        if snapped_edge[0][1] != snapped_node:
            graph.add_edge(snapped_node,
                       snapped_edge[0][1],
                       color=color,
                       type=new_edge_type,
                       grid_type=grid_type,
                       direction=direction,
                       length=abs(
                           distance.euclidean(graph.nodes[snapped_edge[0][1]]["pos"], graph.nodes[snapped_node]["pos"])))
        if snapped_not_same_type_flag is True:
            if not set(graph.nodes[snapped_node]["type"]) & set(graph.nodes[node]["type"]):
                if snapped_node != node:
                    graph.add_edge(snapped_node,
                               node,
                               color=color,
                               type=edge_snapped_node_type,
                               grid_type=grid_type,
                               direction=direction,
                               length=abs(distance.euclidean(graph.nodes[node]["pos"], graph.nodes[snapped_node]["pos"])))
        else:
            if snapped_node != node:
                graph.add_edge(snapped_node,
                           node,
                           color=color,
                           type=edge_snapped_node_type,
                           grid_type=grid_type,
                           direction=direction,
                           length=abs(distance.euclidean(graph.nodes[node]["pos"], graph.nodes[snapped_node]["pos"])))

        graph = self.create_edges(graph=graph,
                              node_list=[node],
                              direction_x=True,
                              direction_y=True,
                              nearest_node_flag=True,
                              connect_types=True,
                              node_type=edge_type_node,
                              edge_type=new_edge_type,
                              color=color,
                              grid_type=grid_type,
                              no_neighbour_collision_flag=no_neighbour_collision_flag,
                              neighbor_nodes_collision_type=neighbor_nodes_collision_type)
        graph = self.create_edges(graph=graph,
                              node_list=[snapped_node],
                              direction_x=True,
                              direction_y=True,
                              nearest_node_flag=True,
                              connect_types=True,
                              node_type=edge_type_node,
                              edge_type=new_edge_type,
                              color=color,
                              grid_type=grid_type,
                              no_neighbour_collision_flag=no_neighbour_collision_flag,
                              neighbor_nodes_collision_type=neighbor_nodes_collision_type
                              )
        node_list = [snapped_node, node]
        combined_y_list, combined_x_list, combined_z_list = [], [], []
        for node in node_list:
            graph, z_list_1, x_list_1, y_list_1 = self.remove_edges_from_node(graph=graph,
                                                                          node=node)
            combined_y_list.extend(y_list_1)
            combined_x_list.extend(x_list_1)
            combined_z_list.extend(z_list_1)

        graph = self.create_edges(graph=graph,
                              node_list=combined_y_list,
                              direction_x=True,
                              direction_y=True,
                              direction_z=True,
                              nearest_node_flag=True,
                              # all_node_flag=True,
                              connect_types=True,
                              node_type=remove_type_node,
                              edge_type=new_edge_type,
                              color=color,
                              grid_type=grid_type,
                              no_neighbour_collision_flag=no_neighbour_collision_flag,
                              neighbor_nodes_collision_type=neighbor_nodes_collision_type
                              )

        graph = self.create_edges(graph=graph,
                              node_list=combined_x_list,
                              direction_x=True,
                              direction_y=True,
                              direction_z=True,
                              nearest_node_flag=True,
                              # all_node_flag=True,
                              connect_types=True,
                              node_type=remove_type_node,
                              edge_type=new_edge_type,
                              color=color,
                              grid_type=grid_type,
                              no_neighbour_collision_flag=no_neighbour_collision_flag,
                              neighbor_nodes_collision_type=neighbor_nodes_collision_type)

        graph = self.create_edges(graph=graph,
                              node_list=combined_z_list,
                              direction_x=True,
                              direction_y=True,
                              direction_z=True,
                              nearest_node_flag=True,
                              # all_node_flag=True,
                              connect_types=True,
                              node_type=remove_type_node,
                              edge_type=new_edge_type,
                              color=color,
                              grid_type=grid_type,
                              no_neighbour_collision_flag=no_neighbour_collision_flag,
                              neighbor_nodes_collision_type=neighbor_nodes_collision_type
                              )

        return graph



    def replace_edge_with_node(self,
                               node,
                               graph,
                               edge_list: list,
                               color: str = "grey"):
        """
                Args:
                    edge_list ():
                    color ():
                    node ():
                    graph ():
                Returns:
                """
        for edges in edge_list:
            if self.point_on_edge(graph=graph, node=node, edges=edges) is True:
                direction = graph.get_edge_data(edges[0], edges[1])["direction"]
                grid_type = graph.get_edge_data(edges[0], edges[1])["grid_type"]
                edge_type = graph.get_edge_data(edges[0], edges[1])["type"]
                # graph.remove_edge(edges[0], edges[1])
                graph.add_edge(edges[0],
                           node,
                           color=color,
                           type=edge_type,
                           grid_type=grid_type,
                           direction=direction,
                           length=abs(distance.euclidean(graph.nodes[edges[0]]["pos"], graph.nodes[node]["pos"])))
                graph.add_edge(edges[1],
                           node,
                           color=color,
                           type=edge_type,
                           grid_type=grid_type,
                           direction=direction,
                           length=abs(distance.euclidean(graph.nodes[edges[1]]["pos"], graph.nodes[node]["pos"])))
                # edge_list.remove((edges[0], edges[1]))
                edge_list.append((edges[0], node))
                edge_list.append((edges[1], node))

        return graph, edge_list

    def kit_grid(self, graph):
        """

                Args:
                    graph ():

                Returns:

                """
        graph_connected = nx.connected_components(graph)
        graph_largest_component = max(graph_connected, key=len)
        graph = graph.subgraph(graph_largest_component)
        for component in graph_connected:
            subgraph = graph.subgraph(component)
            nx.draw(G=subgraph, with_labels=True)
            plt.show()
        for node in graph.nodes():
            if graph.has_node(node):
                pass
            else:
                graph_connected = nx.connected_components(graph)

                graph_largest_component = max(graph_connected, key=len)
                graph = graph.subgraph(graph_largest_component)
        return graph

    @staticmethod
    def arrow3D(ax, x, y, z, dx, dy, dz, length, arrowstyle="-|>", color="black"):
        """

                Args:
                    ax ():
                    x ():
                    y ():
                    z ():
                    dx ():
                    dy ():
                    dz ():
                    length ():
                    arrowstyle ():
                    color ():
                """
        if length != 0:
            arrow = 0.1 / length
        else:
            arrow = 0.1 / 0.0001

        if isinstance(arrow, Quantity):
            arrow = arrow.magnitude

        ax.quiver(x, y, z, dx, dy, dz, color=color, arrow_length_ratio=arrow)
        # ax.quiver(x, y, z, dx, dy, dz, color=color, normalize=True)

    def visualize_networkx(self,
                           graph,
                           title: str = None, ):
        """
                [[[0.2 4.2 0.2]
                    [0.2 0.2 0.2]]
                Args:
                    graph ():

                """

        # node_xyz = np.array(sorted(nx.get_node_attributes(graph, "pos").values()))
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        node_xyz = np.array(sorted(nx.get_node_attributes(graph, "pos").values(), key=lambda x: (x[0], x[1], x[2])))
        node_colors = nx.get_node_attributes(graph, "color")
        node_colors_list = [node_colors[node] for node in graph.nodes()]
        # ax.scatter(*node_xyz.T, s=50, ec="w")
        # ax.scatter(*node_xyz.T, s=50, ec="w", c=node_colors_list)
        used_labels = set()
        for node, data in graph.nodes(data=True):
            pos = np.array(data["pos"])
            color = data["color"]
            s = 50
            if set(["Verteiler", "radiator_forward"]) & set(data["type"]):
                label = set(["Verteiler", "radiator_forward"]) & set(data["type"])
                label = list(label)[0]
                """if label == "Verteiler":
                            label = "Startknoten"
                        if label == "radiator_forward":
                            label = "Endknoten"""
                s = 50
            else:
                s = 10
                label = None
            if label not in used_labels:
                used_labels.add(label)
                ax.scatter(*pos, s=s, ec="w", c=color, label=label)
            else:
                ax.scatter(*pos, s=s, ec="w", c=color)
            # ax.scatter(*pos.T, s=s, ec="w", c=color, label=label)

        if graph.is_directed():
            for u, v in graph.edges():
                edge = np.array([(graph.nodes[u]['pos'], graph.nodes[v]['pos'])])
                direction = edge[0][1] - edge[0][0]
                # ax.quiver(*edge[0][0], *direction, color=graph.edges[u, v]['color'])
                length = graph.edges[u, v]['length']

                self.arrow3D(ax, *edge[0][0], *direction, arrowstyle="-|>",
                                            color=graph.edges[u, v]['color'],
                                            length=length)
        else:
            for u, v in graph.edges():
                edge = np.array([(graph.nodes[u]['pos'], graph.nodes[v]['pos'])])
                ax.plot(*edge.T, color=graph.edges[u, v]['color'])
                # ax.plot(*edge.T, color="red")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        ax.set_xlim(0, 43)
        # Achsenlimits festlegen
        ax.set_xlim(node_xyz[:, 0].min(), node_xyz[:, 0].max())
        ax.set_ylim(node_xyz[:, 1].min(), node_xyz[:, 1].max())
        ax.set_zlim(node_xyz[:, 2].min(), node_xyz[:, 2].max())
        ax.set_box_aspect([3, 1.5, 1])
        # ax.set_box_aspect([1, 1, 1])
        ax.legend()
        if title is None:
            plt.title(f'Gebäudegraph')
        else:

            plt.title(title)
        fig.tight_layout()

    def visualzation_networkx_3D(self, graph, minimum_trees: list, type_grid: str):

        """

                Args:
                    graph ():
                    minimum_trees ():
                """
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        # Graph Buildings graph
        node_xyz = np.array(sorted(nx.get_node_attributes(graph, "pos").values()))
        ax.scatter(*node_xyz.T, s=1, ec="w")
        for u, v in graph.edges():
            edge = np.array([(graph.nodes[u]['pos'], graph.nodes[v]['pos'])])
            ax.plot(*edge.T, color=graph.edges[u, v]['color'])

        # Graph Steiner Tree
        for minimum_tree in minimum_trees:
            for u, v in minimum_tree.edges():
                edge = np.array([(minimum_tree.nodes[u]['pos'], minimum_tree.nodes[v]['pos'])])
                if minimum_tree.graph["grid_type"] == "forward":
                    ax.plot(*edge.T, color="magenta")
                else:
                    ax.plot(*edge.T, color="blue")

            node_xyz = np.array(
                sorted([data["pos"] for n, data in minimum_tree.nodes(data=True) if {"radiator"} in set(data["type"])]))
            if len(node_xyz) > 0 and node_xyz is not None:
                ax.scatter(*node_xyz.T, s=10, ec="red")
            node_xyz = np.array(sorted([data["pos"][0] for n, data in minimum_tree.nodes(data=True) if
                                        set(data["type"]) not in {"heat_source"} and {"radiator"}]))
            # node_xyz = np.array(sorted([data["pos"][0] for n, data in minimum_tree.nodes(data=True) if "pos" in data]))
            if len(node_xyz) > 0 and node_xyz is not None:
                ax.scatter(node_xyz.T[0], node_xyz.T[1], node_xyz.T[2], s=100, ec="yellow")
        """for minimum_tree in minimum_trees:
                    edge_xyz = np.array([(minimum_tree.nodes[u]['pos'], minimum_tree.nodes[v]['pos']) for u, v in minimum_tree.edges()])
                    if len(edge_xyz) > 0 or edge_xyz is not None:
                        for vizedge in edge_xyz:
                            if minimum_tree.graph["grid_type"] == "forward":
                                ax.plot(*vizedge.T, color="tab:red")
                            else:
                                ax.plot(*vizedge.T, color="blue")"""
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        plt.title(f'Graphennetzwerk vom typ {type_grid}')
        fig.tight_layout()

    def create_node_on_edge_overlap(self,
                                    graph: nx.Graph(),
                                    color: str,
                                    e1: nx.Graph().edges(),
                                    grid_type: str,
                                    type_node: list,
                                    edge_type: str,
                                    tolerance: float = 0.1,
                                    type_flag: bool = False):
        """

                Args:
                    graph ():
                    color ():
                    type_node ():
                    connect_projected_node_flag ():
                    type_flag ():
                    all_edges_flag ():

                Returns:

                """
        # Iteriere über alle Kantenpaare
        #
        nodes = []
        intersect_node = None
        if graph.has_edge(e1[0], e1[1]) is True:
            type_connect_edge = graph.edges[(e1[0], e1[1])]["type"]
            for e2 in graph.edges(data=True):
                if e2 != e1:
                    if graph.nodes[e1[0]]['pos'][2] == graph.nodes[e1[1]]['pos'][2] == graph.nodes[e2[0]]['pos'][2] == \
                            graph.nodes[e2[1]]['pos'][2]:
                        type_edge = graph.edges[(e2[0], e2[1])]["type"]
                        if type_flag is True:
                            if type_connect_edge == type_edge == edge_type:
                                l1 = LineString([graph.nodes[e1[0]]['pos'][0:2], graph.nodes[e1[1]]['pos'][0:2]])
                                l2 = LineString([graph.nodes[e2[0]]['pos'][0:2], graph.nodes[e2[1]]['pos'][0:2]])
                                if l1.crosses(l2):
                                    intersection = l1.intersection(l2)
                                    pos = (intersection.x, intersection.y, graph.nodes[e2[0]]['pos'][2])
                                    graph, intersect_node = self.create_intersect_node(graph=graph,
                                                                                   grid_type=grid_type,
                                                                                   node=e1[0],
                                                                                   color=color,
                                                                                   pos=pos,
                                                                                   type_node=type_node)
                                    graph = self.delte_overlapped_edge(graph=graph,
                                                                   edge_1=e1[0],
                                                                   edge_2=e1[1],
                                                                   edge_3=e2[0],
                                                                   edge_4=e2[1])

                                    # Erstellt neue Kanten zwischen neuen Knoten und den alten Knoten
                                    graph = self.create_overlapped_edge(graph=graph,
                                                                    connected_node=intersect_node,
                                                                    edge_type=edge_type,
                                                                    edge_1=e1[0],
                                                                    edge_2=e1[1],
                                                                    edge_3=e2[0],
                                                                    edge_4=e2[1],
                                                                    color=color,
                                                                    grid_type=grid_type)

                                    if e1[0] not in nodes:
                                        nodes.append(e1[0])
                                    if e1[1] not in nodes:
                                        nodes.append(e1[1])
                                    if e2[0] not in nodes:
                                        nodes.append(e2[0])
                                    if e2[1] not in nodes:
                                        nodes.append(e2[1])

                                    return graph, nodes, intersect_node

        return graph, nodes, intersect_node

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
                       graph: nx.Graph(),
                       global_corners: list,
                       color_nodes: str,
                       color_edges: str,
                       offset: float,
                       belongs_to: str,
                       room_ID: str,
                       edge_type: str,
                       grid_type: str,
                       node_type: list,
                       floor_belongs_to: str,
                       tol_value: float = 0.0,
                       update_node: bool = True,
                       direction_x: bool = True,
                       direction_y: bool = True,
                       direction_z: bool = True,
                       ):
        """

                Args:
                    graph (): Networkx Graph.
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
            graph, center_node = self.create_nodes(graph=graph,
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
        graph = self.create_edges(graph=graph,
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

        return graph, node_list

    def steiner_graph(self,
                      graph,
                      nodes_floor,
                      delivery_nodes_floor,
                      intersection_nodes_floor,
                      shaft_node_floor,
                      terminal_nodes_floor,
                      z_value,
                      grid_type = "forward",
                      export = True
                      ):

        """The function creates a connected graph for each floor
        Args:
            graph,
            nodes_floor,
            delivery_nodes_floor,
            intersection_nodes_floor,
            shaft_node_floor,
            terminal_nodes_floor,
            z_value,
            grid_type = "forward"
        Returns:
           connected graph for each floor
       """

        def knick_in_graph(delivery_node):
            if delivery_node != []:
                # Extrahiere die X- und Y-Koordinaten
                x_coords = [x for x, _, _ in delivery_node[0]]
                y_coords = [y for _, y, _ in delivery_node[0]]
                z_coords = [z for _, _, z in delivery_node[0]]

                # Überprüfe, ob alle X-Koordinaten gleich sind oder alle Y-Koordinaten gleich sind
                same_x = all(x == x_coords[0] for x in x_coords)
                same_y = all(y == y_coords[0] for y in y_coords)
                same_z = all(z == z_coords[0] for z in z_coords)

                if same_x or same_y or same_z:
                    return False
                else:
                    return True
            else:
                None

        def metric_closure(G, weight):
            """Return the metric closure of a graph.

            The metric closure of a graph *G* is the complete graph in which each edge
            is weighted by the shortest path distance between the nodes in *G* .

            Parameters
            ----------
            G : NetworkX graph

            Returns
            -------
            NetworkX graph
                Metric closure of the graph `G`.

            """
            M = nx.Graph()

            Gnodes = set(G)

            # check for connected graph while processing first node
            all_paths_iter = nx.all_pairs_dijkstra(G, weight=weight)
            u, (distance, path) = next(all_paths_iter)
            if Gnodes - set(distance):
                msg = "G is not a connected graph. metric_closure is not defined."
                raise nx.NetworkXError(msg)
            Gnodes.remove(u)
            for v in Gnodes:
                M.add_edge(u, v, distance=distance[v], path=path[v])

            # first node done -- now process the rest
            for u, (distance, path) in all_paths_iter:
                Gnodes.remove(u)
                for v in Gnodes:
                    M.add_edge(u, v, distance=distance[v], path=path[v])

            return M

        def steiner_tree(G, terminal_nodes, weight):
            """Return an approximation to the minimum Steiner tree of a graph.

            The minimum Steiner tree of `G` w.r.t a set of `terminal_nodes`
            is a tree within `G` that spans those nodes and has minimum size
            (sum of edge weights) among all such trees.

            The minimum Steiner tree can be approximated by computing the minimum
            spanning tree of the subgraph of the metric closure of *G* induced by the
            terminal nodes, where the metric closure of *G* is the complete graph in
            which each edge is weighted by the shortest path distance between the
            nodes in *G* .
            This algorithm produces a tree whose weight is within a (2 - (2 / t))
            factor of the weight of the optimal Steiner tree where *t* is number of
            terminal nodes.

            Parameters
            ----------
            G : NetworkX graph

            terminal_nodes : list
                 A list of terminal nodes for which minimum steiner tree is
                 to be found.

            Returns
            -------
            NetworkX graph
                Approximation to the minimum steiner tree of `G` induced by
                `terminal_nodes` .

            Notes
            -----
            For multigraphs, the edge between two nodes with minimum weight is the
            edge put into the Steiner tree.


            References
            ----------
            .. [1] Steiner_tree_problem on Wikipedia.
               https://en.wikipedia.org/wiki/Steiner_tree_problem
            """
            # H is the subgraph induced by terminal_nodes in the metric closure M of G.
            M = metric_closure(G, weight=weight)
            H = M.subgraph(terminal_nodes)
            # Use the 'distance' attribute of each edge provided by M.
            mst_edges = nx.minimum_spanning_edges(H, weight="distance", data=True)
            # Create an iterator over each edge in each shortest path; repeats are okay
            edges = chain.from_iterable(pairwise(d["path"]) for u, v, d in mst_edges)
            # For multigraph we should add the minimal weight edge keys
            if G.is_multigraph():
                edges = (
                    (u, v, min(G[u][v], key=lambda k: G[u][v][k][weight])) for u, v in edges
                )
            T = G.edge_subgraph(edges)
            return T

        def euclidean_distance(point1, point2):
            """
            Calculating the distance between point1 and point2
            :param point1:
            :param point2:
            :return: Distance between point1 and point2
            """
            return round(
                math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2),
                2)

        def find_leaves(spanning_tree):
            leaves = []
            for node in spanning_tree:
                if len(spanning_tree[node]) == 1:  # Ein Blatt hat nur einen Nachbarn
                    leaves.append(node)
            return leaves

        """1. Optimierung"""
        # Erstellung des Steinerbaums
        steiner_baum = steiner_tree(graph, terminal_nodes_floor, weight="length")

        if export:
            self.visualize_graph(graph=steiner_baum,
                                 graph_steiner_tree=steiner_baum,
                                 z_value=z_value,
                                 node_coordinates=nodes_floor,
                                 delivery_nodes_coordinates=delivery_nodes_floor,
                                 intersection_nodes_coordinates=intersection_nodes_floor,
                                 building_shaft=shaft_node_floor,
                                 name=f"Vorlauf 1. Optimierung",
                                 unit_edge="m",
                                 )

        # Extraierung der Knoten und Katen aus dem Steinerbaum
        knoten = list(steiner_baum.nodes())
        kanten = list(steiner_baum.edges())

        # Erstellung des Baums
        tree = nx.Graph()

        # Hinzufügen der Knoten zum Baum
        coordinates = delivery_nodes_floor + intersection_nodes_floor
        for x, y, z in knoten:
            for point in coordinates:
                if point[0] == x and point[1] == y and point[2] == z:
                    tree.add_node((x, y, z))

        # Hinzufügen der Kanten zum Baum
        for kante in kanten:
            tree.add_edge(kante[0], kante[1], length=euclidean_distance(kante[0], kante[1]))

        # Hier wird der minimale Spannbaum des Steinerbaums berechnet
        minimum_spanning_tree = nx.minimum_spanning_tree(tree)
        

        """2. Optimierung"""
        # Hier wird überprüft, welche Punkte entlang eines Pfades, auf einer Achse liegen.
        # Ziel ist es die Steinerpunkte zu finden, die zwischen zwei Terminalen liegen, damit der Graph
        # optimiert werden kann
        coordinates_on_same_axis = list()
        for startknoten in delivery_nodes_floor:
            for zielknoten in delivery_nodes_floor:
                for path in nx.all_simple_paths(minimum_spanning_tree, startknoten, zielknoten):
                #for path in nx.all_simple_paths(steiner_baum, startknoten, zielknoten):
                    # Extrahiere die X- und Y-Koordinaten
                    x_coords = [x for x, _, _ in path]
                    y_coords = [y for _, y, _ in path]

                    # Überprüfe, ob alle X-Koordinaten gleich sind oder alle Y-Koordinaten gleich sind
                    same_x = all(x == x_coords[0] for x in x_coords)
                    same_y = all(y == y_coords[0] for y in y_coords)

                    if same_x or same_y:
                        for cord in path:
                            coordinates_on_same_axis.append(cord)

        # Doppelte entfernen:
        coordinates_on_same_axis = set(coordinates_on_same_axis)

        # Wenn die Koordinate ein Lüftungsausslass ist, muss diese ignoriert werden
        coordinates_on_same_axis = [item for item in coordinates_on_same_axis if item not in
                                    delivery_nodes_floor]

        # Hinzufügen der Koordinaten zu den Terminalen
        for coord in coordinates_on_same_axis:
            terminal_nodes_floor.append(coord)
        
        # Erstellung des neuen Steinerbaums
        steiner_baum = steiner_tree(graph, terminal_nodes_floor, weight="length")

        if export:
            self.visualize_graph(graph=steiner_baum,
                                 graph_steiner_tree=steiner_baum,
                                 z_value=z_value,
                                 node_coordinates=nodes_floor,
                                 delivery_nodes_coordinates=delivery_nodes_floor,
                                 intersection_nodes_coordinates=intersection_nodes_floor,
                                 building_shaft=shaft_node_floor,
                                 name=f"Vorlauf 2. Optimierung",
                                 unit_edge="m",
                                 )

        """3. Optimierung"""
        # Hier wird überprüft, ob unnötige Umlenkungen im Graphen vorhanden sind:
        node_list = delivery_nodes_floor+[shaft_node_floor]
        for delivery_node in node_list:
            if steiner_baum.degree(delivery_node) == 2:
                neighbors = list(nx.all_neighbors(steiner_baum, delivery_node))

                neighbor_delivery_node_one = neighbors[0]
                temp = list()
                i = 0
                while neighbor_delivery_node_one not in node_list:
                    temp.append(neighbor_delivery_node_one)
                    new_neighbor_node = list(nx.all_neighbors(steiner_baum, neighbor_delivery_node_one))
                    new_neighbor_node = [coord for coord in new_neighbor_node if coord != delivery_node]
                    neighbor_delivery_node_one = [coord for coord in new_neighbor_node if coord != temp[i - 1]]
                    neighbor_delivery_node_one = neighbor_delivery_node_one[0]
                    i += 1
                    if neighbor_delivery_node_one in node_list:
                        break

                neighbor_delivery_node_two = neighbors[1]
                temp = list()
                i = 0
                while neighbor_delivery_node_two not in node_list:
                    temp.append(neighbor_delivery_node_two)
                    new_neighbor_node = list(nx.all_neighbors(steiner_baum, neighbor_delivery_node_two))
                    new_neighbor_node = [coord for coord in new_neighbor_node if coord != delivery_node]
                    neighbor_delivery_node_two = [coord for coord in new_neighbor_node if coord != temp[i - 1]]
                    neighbor_delivery_node_two = neighbor_delivery_node_two[0]
                    i += 1
                    if neighbor_delivery_node_two in node_list:
                        break

                # Gibt den Pfad vom Nachbarauslass 1 zum Lüftungsauslass in Form von Knoten zurück
                delivery_node_to_one = list(nx.all_simple_paths(steiner_baum, delivery_node,
                                                                    neighbor_delivery_node_one))

                # Gibt den Pfad vom Lüftungsauslass zum Nachbarauslass 2 in Form von Knoten zurück
                delivery_node_to_two = list(nx.all_simple_paths(steiner_baum, delivery_node,
                                                                    neighbor_delivery_node_two))

                if knick_in_graph(delivery_node_to_one) == False and knick_in_graph(
                        delivery_node_to_two) == False:
                    pass
                elif knick_in_graph(delivery_node_to_one) == True:
                    if delivery_node_to_one != [] and delivery_node_to_two != []:
                        if delivery_node[0] == delivery_node_to_two[0][1][0]:
                            terminal_nodes_floor.append((delivery_node[0], neighbor_delivery_node_one[1], z_value))
                        elif delivery_node[1] == delivery_node_to_two[0][1][1]:
                            terminal_nodes_floor.append((neighbor_delivery_node_one[0], delivery_node[1], z_value))
                elif knick_in_graph(delivery_node_to_two) == True:
                    if delivery_node_to_one != [] and delivery_node_to_two != []:
                        if delivery_node[0] == delivery_node_to_one[0][1][0]:
                            terminal_nodes_floor.append((delivery_node[0], neighbor_delivery_node_two[1], z_value))
                        elif delivery_node[1] == delivery_node_to_one[0][1][1]:
                            terminal_nodes_floor.append((neighbor_delivery_node_two[0], delivery_node[1], z_value))

        # Erstellung des neuen Steinerbaums
        steiner_baum = steiner_tree(graph, terminal_nodes_floor, weight="length")

        if export:
            self.visualize_graph(graph=steiner_baum,
                                 graph_steiner_tree=steiner_baum,
                                 z_value=z_value,
                                 node_coordinates=nodes_floor,
                                 delivery_nodes_coordinates=delivery_nodes_floor,
                                 intersection_nodes_coordinates=intersection_nodes_floor,
                                 building_shaft=shaft_node_floor,
                                 name=f"Vorlauf 3. Optimierung",
                                 unit_edge="m",
                                 )

        """4. Optimierung"""
        # Hier werden die Blätter aus dem Graphen ausgelesen
        leaves = find_leaves(steiner_baum)

        # Entfernen der Blätter die kein Lüftungsauslass sind
        for leave in leaves:
            if leave not in node_list:
                terminal_nodes_floor.remove(leave)

        # Erstellung des neuen Steinerbaums
        steiner_baum = steiner_tree(graph, terminal_nodes_floor, weight="length")

        if export:
            self.visualize_graph(graph=steiner_baum,
                                 graph_steiner_tree=steiner_baum,
                                 z_value=z_value,
                                 node_coordinates=nodes_floor,
                                 delivery_nodes_coordinates=delivery_nodes_floor,
                                 intersection_nodes_coordinates=intersection_nodes_floor,
                                 building_shaft=shaft_node_floor,
                                 name=f"Vorlauf 4. Optimierung",
                                 unit_edge="m",
                                 )

        total_length = sum([edge[2]['length'] for edge in steiner_baum.edges(data=True)])
        return steiner_baum, total_length


    def add_graphs(self, graph_list, grid_type: str = "forward"):
        """

                Args:
                    graph_list ():

                Returns:

                """
        combined_graph = nx.Graph()

        for subgraph in graph_list:
            combined_graph = nx.union(combined_graph, subgraph)
            # combined_graph = nx.disjoint_union(combined_graph, subgraph)
        combined_graph.graph["circulation_direction"] = grid_type
        return combined_graph

    @staticmethod
    def directed_graph(graph, source_nodes, edge_type: str = "forward", grid_type: str = "forward", color: str = "red"):
        """
                Args:
                    graph ():
                    source_nodes ():
                Returns:
                """

        D = nx.DiGraph(grid_type=grid_type)
        D.add_nodes_from(graph.nodes(data=True))
        T = nx.bfs_tree(graph, source_nodes)
        for edges in T.edges():
            length = abs(distance.euclidean(graph.nodes[edges[0]]["pos"], graph.nodes[edges[1]]["pos"]))
            D.add_edge(edges[0], edges[1], type=edge_type, grid_type=grid_type, length=length, color=color)
        D.graph["grid_type"] = grid_type
        return D

    def create_directed_edges(self, graph, node_list, color: str, edge_type: str, grid_type: str):
        """

                Args:
                    graph ():
                    node_list ():
                    color ():
                    edge_type ():
                    grid_type ():

                Returns:

                """
        for i in range(len(node_list) - 1):
            length = abs(distance.euclidean(graph.nodes[node_list[i]]["pos"], graph.nodes[node_list[i + 1]]["pos"]))
            graph.add_edge(node_list[i],
                       node_list[i + 1],
                       color=color,
                       type=edge_type,
                       grid_type=grid_type,
                       length=length)

        return graph

    def remove_edges_from_node(self,
                               graph: nx.Graph(),
                               node: nx.Graph().nodes(),
                               tol_value: float = 0.0,
                               z_flag: bool = True,
                               y_flag: bool = True,
                               x_flag: bool = True,
                               ):
        """

                Args:
                    graph (): Networkx Graph
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
        node_pos = graph.nodes[node]["pos"]
        node_neighbor = list(graph.neighbors(node))
        y_list, x_list, z_list = [], [], []
        x_2, y_2, z_2 = node_pos
        for neighbor in node_neighbor:
            x_1, y_1, z_1 = graph.nodes[neighbor]['pos']
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
                    diff = graph.nodes[node]['pos'][2] - graph.nodes[z]['pos'][2]
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
                    if graph.has_edge(z, node):
                        graph.remove_edge(z, node)
                    elif graph.has_edge(node, z):
                        graph.remove_edge(node, z)
        # x edges
        if x_flag is True:
            if len(x_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_x_neighbor = None
                pos_x_neighbor = None
                for x in x_list:
                    diff = graph.nodes[node]['pos'][0] - graph.nodes[x]['pos'][0]
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
                    if graph.has_edge(x, node):
                        graph.remove_edge(x, node)
                    if graph.has_edge(node, x):
                        graph.remove_edge(node, x)
        # y edges
        if y_flag is True:
            if len(y_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_y_neighbor = None
                pos_y_neighbor = None
                for y in y_list:
                    diff = graph.nodes[node]['pos'][1] - graph.nodes[y]['pos'][1]
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
                    if graph.has_edge(y, node):
                        graph.remove_edge(y, node)
                    if graph.has_edge(node, y):
                        graph.remove_edge(node, y)
        return graph, z_list, x_list, y_list

    def remove_edges(self, graph, tol_value: float = 0.0):
        """
                color, edge_type, grid_type)
                Args:
                    graph ():
                Returns:
                """
        node_dict = {}
        edge_dict = {}

        for node in graph.nodes():
            if 'pos' in graph.nodes[node]:
                edge_dict[node] = list(graph.edges(node))
                node_dict[node] = list(graph.neighbors(node))
        graph = graph.copy(as_view=False)
        for node in node_dict:
            # neighbors = list(graph.neighbors(node))
            y_list, x_list, z_list = [], [], []
            x_1, y_1, z_1 = graph.nodes[node]['pos']
            # Nachbarknoten vom Knoten
            for neigh in node_dict[node]:
                # for neigh in neighbors:
                x_2, y_2, z_2 = graph.nodes[neigh]['pos']
                if abs(x_1 - x_2) <= tol_value and abs(y_1 - y_2) <= tol_value:
                    z_list.append(neigh)
                if abs(y_1 - y_2) <= tol_value and abs(z_1 - z_2) <= tol_value:
                    x_list.append(neigh)
                if abs(x_1 - x_2) <= tol_value and abs(z_1 - z_2) <= tol_value:
                    y_list.append(neigh)
            # z edges
            if len(z_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_z_neighbor = None
                pos_z_neighbor = None
                for z in z_list:
                    # diff = z_1 - graph.nodes[z]['pos'][2]
                    diff = graph.nodes[node]['pos'][2] - graph.nodes[z]['pos'][2]
                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_z_neighbor = z
                    elif diff < 0 and abs(diff) < min_neg_diff:
                        min_neg_diff = abs(diff)
                        pos_z_neighbor = z
                if neg_z_neighbor is not None:
                    z_list.remove(neg_z_neighbor)
                if pos_z_neighbor is not None:
                    z_list.remove(pos_z_neighbor)
                for z in z_list:
                    if graph.has_edge(z, node):
                        graph.remove_edge(z, node)
                    elif graph.has_edge(node, z):
                        graph.remove_edge(node, z)
            # x edges
            if len(x_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_x_neighbor = None
                pos_x_neighbor = None
                for x in x_list:
                    # diff = x_1 - graph.nodes[x]['pos'][0]
                    diff = graph.nodes[node]['pos'][0] - graph.nodes[x]['pos'][0]

                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_x_neighbor = x
                    elif diff < 0 and abs(diff) < min_neg_diff:
                        min_neg_diff = abs(diff)
                        pos_x_neighbor = x
                if neg_x_neighbor is not None:
                    x_list.remove(neg_x_neighbor)

                if pos_x_neighbor is not None:
                    x_list.remove(pos_x_neighbor)

                for x in x_list:
                    if graph.has_edge(x, node):
                        graph.remove_edge(x, node)
                    elif graph.has_edge(node, x):
                        graph.remove_edge(node, x)

            # y edges
            if len(y_list) > 0:
                min_pos_diff = float('inf')
                min_neg_diff = float('inf')
                neg_y_neighbor = None
                pos_y_neighbor = None
                for y in y_list:
                    # diff = y_1 - graph.nodes[y]['pos'][1]
                    diff = graph.nodes[node]['pos'][1] - graph.nodes[y]['pos'][1]
                    if diff > 0 and diff < min_pos_diff:
                        min_pos_diff = diff
                        neg_y_neighbor = y
                    elif diff < 0 and abs(diff) < min_neg_diff:
                        min_neg_diff = abs(diff)
                        pos_y_neighbor = y
                if neg_y_neighbor is not None:
                    y_list.remove(neg_y_neighbor)
                if pos_y_neighbor is not None:
                    y_list.remove(pos_y_neighbor)
                for y in y_list:
                    if graph.has_edge(y, node):
                        graph.remove_edge(y, node)
                    elif graph.has_edge(node, y):
                        graph.remove_edge(node, y)

        return graph

    def create_backward(self, graph, grid_type: str = "backward", offset: float = 0.1, color: str = "blue"):
        """

                Args:
                    graph ():
                    grid_type ():
                    offset ():

                Returns:

                """

        graph_reversed = graph.reverse()
        graph_reversed.graph["grid_type"] = grid_type
        # Offset für die Knotenpositionen berechnen
        node_positions = nx.get_node_attributes(graph, "pos")
        node_offset = {node: (pos[0] + offset, pos[1] + offset, pos[2]) for node, pos in node_positions.items()}
        nx.set_node_attributes(graph_reversed, node_offset, "pos")
        for node, data in graph_reversed.nodes(data=True):
            graph_reversed.nodes[node]['grid_type'] = grid_type
            if "radiator_forward" in data["type"]:
                graph_reversed.nodes[node]['type'] = ["radiator_backward"]
            if "radiator_forward_ground" in data["type"]:
                graph_reversed.nodes[node]['type'] = ["radiator_backward_ground"]
            if "start_node" in data["type"]:
                # graph_reversed.nodes[node]['type'].append("end_node")
                graph_reversed.nodes[node]['type'] = ["end_node", "Vereinigung"]
            if "Verteiler" in data["type"]:
                # graph_reversed.nodes[node]['type'].append("end_node")
                graph_reversed.nodes[node]['type'] = ["Vereinigung"]

        # Farbe der Kanten ändern
        edge_attributes = {(u, v): {"color": color} for u, v in graph_reversed.edges()}
        nx.set_edge_attributes(graph_reversed, edge_attributes)
        return graph_reversed










