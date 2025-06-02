import bim2sim
import matplotlib
#matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import networkx as nx
from networkx.readwrite import json_graph
import json
from itertools import chain
import math
import pandas as pd
import pandapipes as pp
import numpy as np
import requests
import pandapipes.plotting as plot
from pathlib import Path
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from decimal import Decimal, ROUND_HALF_UP
from networkx.utils import pairwise
from copy import deepcopy
from scipy.interpolate import interpolate, interp1d, griddata, LinearNDInterpolator
from pint import Quantity
import ifcopenshell.geom
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.gp import gp_Pnt
from OCC.Core.TopAbs import TopAbs_IN, TopAbs_ON

from bim2sim.utilities.common_functions import filter_elements

class DesignExaustLCA(ITask):
    """Design of the LCA

    Assumptions:
    Inputs: IFC model, rooms,

    Args:
        elements: bim2sim elements
    Returns:
        elements: bim2sim elements enriched with needed air flows
    """
    reads = ('elements',
             'graph_ventilation_duct_length_supply_air',
             'dict_steiner_tree_with_duct_cross_section')
    touches = ('corners_building',
               'building_shaft_exhaust_air',
               'graph_ventilation_duct_length_exhaust_air',
               'pressure_loss_exhaust_air',
               'dataframe_rooms_exhaust_air',
               'dataframe_distribution_network_exhaust_air',
               'dict_steiner_tree_with_air_volume_exhaust_air')

    def run(self, elements, graph_ventilation_duct_length_supply_air, dict_steiner_tree_with_duct_cross_section):

        self.lock = self.playground.sim_settings.lock

        self.elements = elements
        self.supply_graph = graph_ventilation_duct_length_supply_air
        self.dict_supply_graph_cross_section = dict_steiner_tree_with_duct_cross_section

        self.export_graphs = self.playground.sim_settings.export_graphs

        # Todo add the following to sim settings
        building_shaft_exhaust_air = [1, 2.8, -2]
        position_rlt = [25, building_shaft_exhaust_air[1], building_shaft_exhaust_air[2]]
        # y-Achse von Schacht und RLT müssen identisch sein
        cross_section_type = "optimal"  # choose between round, angular and optimal
        suspended_ceiling_space = 200 * ureg.millimeter  # The available height (in [mmm]) in the suspended ceiling is
        # specified here! This corresponds to the available distance between UKRD (lower edge of raw ceiling) and OKFD
        # (upper edge of finished ceiling), see https://www.ctb.de/_wiki/swb/Massbezuege.php


        self.logger.info("Start design LCA")
        thermal_zones = filter_elements(self.elements, 'ThermalZone')
        thermal_zones = [tz for tz in thermal_zones if tz.with_ahu == True]

        self.logger.info("Start calculating points of the ventilation outlet at the ceiling")
        # Here, the center points of the individual rooms are read from the IFC model and then shifted upwards by half
        # the height of the room. The point at the UKRD (lower edge of the bare ceiling) in the middle of the room is
        # therefore calculated. This is where the ventilation outlet is to be positioned later on

        (corner_points,
         airflow_volume_per_storey,
         dict_coordinate_with_space_type,
         dataframe_rooms,
         corners_building) = self.calculate_center_points(thermal_zones,
                                                          building_shaft_exhaust_air)
        self.logger.info("Finished calculating points of the ventilation outlet at the ceiling")

        self.logger.info("Calculating the Coordinates of the ceiling hights")
        # Here the coordinates of the heights at the UKRD are calculated and summarized in a set, as these values are
        # frequently needed in the further course, so they do not have to be recalculated again and again:
        z_coordinate_list = self.calculate_z_coordinate(corner_points)

        self.logger.info("Calculating intersection points")
        # The intersections of all points per storey are calculated here. A grid is created on the respective storey.
        # It is defined as the installation grid for the exhaust air. The individual points of the ventilation inlets
        # are not connected directly, but in practice and according to the standard, ventilation ducts are not laid
        # diagonally through a building
        intersection_points = self.intersection_points(corner_points,
                                                       z_coordinate_list)
        self.logger.info("Calculating intersection points successful")

        self.logger.info("Visualising points on the ceiling for the ventilation outlet:")
        self.visualisierung(corner_points,
                            intersection_points)

        self.logger.info("Visualising intersection points")
        self.visualization_points_by_level(corner_points,
                                           intersection_points,
                                           z_coordinate_list,
                                           building_shaft_exhaust_air)

        self.logger.info("Create graph for each storey")
        (dict_steiner_tree_with_duct_length,
         dict_steiner_tree_with_duct_cross_section,
         dict_steiner_tree_with_air_volume_exhaust_air,
         dict_steinertree_with_shell,
         dict_steiner_tree_with_calculated_cross_section) = self.create_graph(corner_points,
                                                                             intersection_points,
                                                                             z_coordinate_list,
                                                                             building_shaft_exhaust_air,
                                                                             cross_section_type,
                                                                             suspended_ceiling_space)

        self.logger.info("Connect shaft and ahu")
        (dict_steiner_tree_with_duct_length,
         dict_steiner_tree_with_duct_cross_section,
         dict_steiner_tree_with_air_volume_exhaust_air,
         dict_steinertree_with_shell,
         dict_steiner_tree_with_calculated_cross_section) = self.ahu_shaft(z_coordinate_list,
                                                                           building_shaft_exhaust_air,
                                                                           airflow_volume_per_storey,
                                                                           position_rlt,
                                                                           dict_steiner_tree_with_duct_length,
                                                                           dict_steiner_tree_with_duct_cross_section,
                                                                           dict_steiner_tree_with_air_volume_exhaust_air,
                                                                           dict_steinertree_with_shell,
                                                                           dict_steiner_tree_with_calculated_cross_section)

        self.logger.info("Create 3D-Graph")
        (graph_ventilation_duct_length_exhaust_air,
         graph_air_volume_flow,
         graph_duct_cross_section,
         graph_shell_surface,
         graph_calculated_diameter,
         dataframe_distribution_network_exhaust_air) = self.three_dimensional_graph(dict_steiner_tree_with_duct_length,
                                                                                    dict_steiner_tree_with_duct_cross_section,
                                                                                    dict_steiner_tree_with_air_volume_exhaust_air,
                                                                                    dict_steinertree_with_shell,
                                                                                    dict_steiner_tree_with_calculated_cross_section,
                                                                                    position_rlt,
                                                                                    dict_coordinate_with_space_type)

        self.logger.info("Start pressure loss calculation")
        pressure_loss, dataframe_distribution_network_exhaust_air = self.calculate_pressure_loss(dict_steiner_tree_with_duct_length,
                                                                                    z_coordinate_list,
                                                                                    position_rlt,
                                                                                    building_shaft_exhaust_air,
                                                                                    graph_ventilation_duct_length_exhaust_air,
                                                                                    graph_air_volume_flow,
                                                                                    graph_duct_cross_section,
                                                                                    graph_shell_surface,
                                                                                    graph_calculated_diameter,
                                                                                    dataframe_distribution_network_exhaust_air)

        self.logger.info("Connect rooms to graph")
        dataframe_rooms = self.connect_rooms(cross_section_type, suspended_ceiling_space, dataframe_rooms)

        self.logger.info("Calculate material quantities")
        (pressure_loss_exhaust_air,
         dataframe_rooms_exhaust_air,
         dataframe_distribution_network_exhaust_air) = self.calculate_material_quantities(pressure_loss,
                                                                                          dataframe_rooms,
                                                                                          dataframe_distribution_network_exhaust_air)

        return (corners_building,
                building_shaft_exhaust_air,
                graph_ventilation_duct_length_exhaust_air,
                pressure_loss_exhaust_air,
                dataframe_rooms_exhaust_air,
                dataframe_distribution_network_exhaust_air,
                dict_steiner_tree_with_air_volume_exhaust_air)

    def calculate_center_points(self, thermal_zones, building_shaft_exhaust_air):
        """Function calculates position of the outlet of the LVA

        Args:
            thermal_zones: thermal_zones bim2sim element
            building_shaft_exhaust_air: shaft coordinates
        Returns:
            corner points of the room at the ceiling
        """
        # Listen:
        room_ceiling_ventilation_outlet = []
        room_type = []

        building_coordinates = list()
        for tz in thermal_zones:
            if tz.with_ahu:
                building_coordinates.append([round(tz.space_center.X(), 1),
                                             round(tz.space_center.Y(), 1),
                                             round(tz.space_center.Z(), 1)])

        # find min x, y, z
        min_x = min(building_coordinates, key=lambda k: k[0])[0]
        min_y = min(building_coordinates, key=lambda k: k[1])[1]
        min_z = min(building_coordinates, key=lambda k: k[2])[2]

        # find max für x, y, z
        max_x = max(building_coordinates, key=lambda k: k[0])[0]
        max_y = max(building_coordinates, key=lambda k: k[1])[1]
        max_z = max(building_coordinates, key=lambda k: k[2])[2]

        center_building_x = (min_x + max_x) / 2
        center_building_y = (min_y + max_y) / 2
        center_building_z = (min_z + max_z) / 2

        center_building = (center_building_x, center_building_y, center_building_z)

        list_corner_one = []
        list_corner_two = []

        for tz in thermal_zones:
            if tz.with_ahu:
                center = [round(tz.space_center.X(), 1),
                          round(tz.space_center.Y(), 1),
                          round(tz.space_center.Z(), 1)]
                name = tz.name

                corner_one = [round(tz.space_corners[0].X(), 1),
                             round(tz.space_corners[0].Y(), 1),
                             round(tz.space_corners[0].Z(), 1)]

                list_corner_one.append(corner_one)

                corner_two = [round(tz.space_corners[1].X(), 1),
                             round(tz.space_corners[1].Y(), 1),
                             round(tz.space_corners[1].Z(), 1)]

                list_corner_two.append(corner_two)

                exhaust_air_inlet = [0, 0, 0]

                if center[0] > center_building[0]:
                    exhaust_air_inlet[0] = corner_two[0] - 1
                elif center[0] < center_building[0]:
                    exhaust_air_inlet[0] = corner_one[0] + 1
                elif center[0] == center_building[0]:
                    exhaust_air_inlet[0] = center[0]

                if center[1] > center_building[1]:
                    exhaust_air_inlet[1] = corner_two[1] - 1
                elif center[1] < center_building[1]:
                    exhaust_air_inlet[1] = corner_one[1] + 1
                elif center[1] == center_building[1]:
                    exhaust_air_inlet[1] = center[1]

                room_ceiling_ventilation_outlet.append([round(exhaust_air_inlet[0], 1),
                                                        round(exhaust_air_inlet[1], 1),
                                                        round(tz.space_center.Z() + tz.height.magnitude / 2,
                                                                           2),
                                                        math.ceil(tz.air_flow.magnitude) * ureg.meter**3 / ureg.hour])
                room_type.append(tz.usage)

        # find min x, y, z
        lowest_x_corner = min(list_corner_one, key=lambda k: k[0])[0]
        lowest_y_corner = min(list_corner_one, key=lambda k: k[1])[1]
        lowest_z_corner = min(list_corner_one, key=lambda k: k[2])[2]

        # find max x, y, z
        highest_x_corner = max(list_corner_two, key=lambda k: k[0])[0]
        highest_y_corner = max(list_corner_two, key=lambda k: k[1])[1]
        highest_z_corner = max(list_corner_two, key=lambda k: k[2])[2]

        corner_building = ((lowest_x_corner, lowest_y_corner, lowest_z_corner),
                           (highest_x_corner, highest_y_corner, highest_z_corner))

        # As the points do not lie exactly on a line, although the rooms are actually next to each other,
        # some rooms have slightly different depths. Therefore, the coordinates must be adjusted.
        # A small shift of the ventilation outlet will not cause a major change in reality,
        # as the ventilation outlets are either connected with a flexible hose or directly from the main duct.

        # Z-coordinates
        z_axis = set()
        for i in range(len(room_ceiling_ventilation_outlet)):
            z_axis.add(room_ceiling_ventilation_outlet[i][2])

        grouped_coordinates_x = {}
        for x, y, z, a in room_ceiling_ventilation_outlet:
            if z not in grouped_coordinates_x:
                grouped_coordinates_x[z] = []
            grouped_coordinates_x[z].append((x, y, z, a))

        # X-coordinates
        adjusted_coords_x = []
        for z_coord in z_axis:
            sort = sorted(grouped_coordinates_x[z_coord], key=lambda coord: (coord[0], coord[1]))

            i = 0
            while i < len(sort):
                x1, y1, z1, a1 = sort[i]
                total_x = x1
                count = 1

                j = i + 1
                while j < len(sort) and sort[j][0] - x1 <= 0.75:
                    total_x += sort[j][0]
                    count += 1
                    j += 1

                x_avg = total_x / count
                for _ in range(i, j):
                    _, y, z, a = sort[i]
                    adjusted_coords_x.append((round(x_avg, 1), y, z, a))
                    i += 1

        # Dict sorted by Z-coordinates
        grouped_coordinates_y = {}
        for x, y, z, a in adjusted_coords_x:
            if z not in grouped_coordinates_y:
                grouped_coordinates_y[z] = []
            grouped_coordinates_y[z].append((x, y, z, a))

        adjusted_coords_y = []

        # y-coordinates
        for z_coord in z_axis:
            room_ceiling_ventilation_outlet = grouped_coordinates_y[z_coord]

            room_ceiling_ventilation_outlet.sort(key=lambda coord: coord[1])

            i = 0
            while i < len(room_ceiling_ventilation_outlet):
                current_coord = room_ceiling_ventilation_outlet[i]
                sum_y = current_coord[1]
                count = 1

                j = i + 1
                while j < len(room_ceiling_ventilation_outlet) and room_ceiling_ventilation_outlet[j][1] - \
                        current_coord[1] < 0.5:
                    sum_y += room_ceiling_ventilation_outlet[j][1]
                    count += 1
                    j += 1

                average_y = sum_y / count

                for k in range(i, j):
                    x, _, z, a = room_ceiling_ventilation_outlet[k]
                    adjusted_coords_y.append((x, round(average_y, 1), z, a))

                i = j

        room_ceiling_ventilation_outlet = adjusted_coords_y

        dict_coordinate_with_space_type = dict()
        for index, coordinate in enumerate(room_ceiling_ventilation_outlet):
            coordinate = (coordinate[0], coordinate[1], coordinate[2])
            dict_coordinate_with_space_type[coordinate] = room_type[index]

        dict_coordinate_with_air_volume = dict()
        for index, coordinate in enumerate(room_ceiling_ventilation_outlet):
            point = (coordinate[0], coordinate[1], coordinate[2])
            dict_coordinate_with_air_volume[point] = coordinate[3]

        # Here, the starting points (shaft outlets) are added for each level and the total air volume for the level is calculated.
        # is calculated. This is used for the graph

        airflow_volume_per_storey = {}

        for sublist in room_ceiling_ventilation_outlet:
            z = sublist[2]  # Third entry (Index 2) is 'z'
            a = sublist[3]  # Fourth entry (Index 3) is 'a'
            if z in airflow_volume_per_storey:
                airflow_volume_per_storey[z] += a
            else:
                airflow_volume_per_storey[z] = a

        dataframe_rooms = pd.DataFrame()
        dataframe_rooms["coordinate"] = list(dict_coordinate_with_space_type.keys())
        dataframe_rooms["X"] = [x for x, _, _ in dataframe_rooms["coordinate"]]
        dataframe_rooms["Y"] = [y for _, y, _ in dataframe_rooms["coordinate"]]
        dataframe_rooms["Z"] = [z for _, _, z in dataframe_rooms["coordinate"]]
        dataframe_rooms["room type"] = dataframe_rooms["coordinate"].map(dict_coordinate_with_space_type)
        dataframe_rooms["volume flow"] = dataframe_rooms["coordinate"].map(dict_coordinate_with_air_volume)

        for z_coord in z_axis:
            room_ceiling_ventilation_outlet.append(
                (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_coord,
                 airflow_volume_per_storey[z_coord]))

        return room_ceiling_ventilation_outlet, airflow_volume_per_storey, dict_coordinate_with_space_type, dataframe_rooms, corner_building

    def calculate_z_coordinate(self, center):
        z_coordinate_list = set()
        for i in range(len(center)):
            z_coordinate_list.add(center[i][2])
        return sorted(z_coordinate_list)

    def intersection_points(self, ceiling_point, z_coordinate_list):
        intersection_points_list = []

        for z_value in z_coordinate_list:
            filtered_coordinates_list = [coord for coord in ceiling_point if coord[2] == z_value]

            for z_value in range(len(filtered_coordinates_list)):
                for j in range(z_value + 1, len(filtered_coordinates_list)):
                    p1 = filtered_coordinates_list[z_value]
                    p2 = filtered_coordinates_list[j]
                    intersection_points_list.append((p2[0], p1[1], p1[2], 0))
                    intersection_points_list.append((p1[0], p2[1], p2[2], 0))

        # Delete double coordinates
        intersection_points_list = list(set(intersection_points_list))

        filtered_intersection_points = []

        for ip in intersection_points_list:
            if not any(cp[:3] == ip[:3] for cp in ceiling_point):
                filtered_intersection_points.append(ip)

        return filtered_intersection_points

    def write_json_graph(self, graph, filename):

        for edge in graph.edges(data=True):
            for attr, value in edge[2].items():
                if isinstance(value, Quantity):
                    graph.edges[(edge[0],edge[1])][attr] = value.magnitude
        for node in graph.nodes(data=True):
            for attr, value in node[1].items():
                if isinstance(value, Quantity):
                    graph.nodes[node[0]][attr] = value.magnitude

        filepath = self.paths.export / 'ventilation system' / 'exhaust air'
        filepath.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Read {filename} Graph from file {filepath}")
        data = json_graph.node_link_data(graph)
        with self.lock:
            with open(filepath / filename, 'w') as f:
                json.dump(data, f, indent=4)

    def visualisierung(self, room_ceiling_ventilation_outlet, intersection):
        """The function visualizes the points in a diagram

        Args:
            room_ceiling_ventilation_outlet: Point at the ceiling in the middle of the room
            air_flow_building:
        Returns:
            3D diagramm
        """
        if self.export_graphs:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

            plt.subplots_adjust(right=0.75)

            coordinates1 = room_ceiling_ventilation_outlet
            coordinates2 = intersection

            x1, y1, z1, a1 = zip(*coordinates1)
            x2, y2, z2, a2 = zip(*coordinates2)

            ax.scatter(x2, y2, z2, c='red', marker='x', label='Intersection points')

            ax.scatter(x1, y1, z1, c='blue', marker='D', label='Air inlets')

            ax.set_xlabel('X-Axis [m]')
            ax.set_ylabel('Y-Axis [m]')
            ax.set_zlabel('Z-Axis [m]')

            ax.legend(loc="center left", bbox_to_anchor=(1, 0))

            # plt.show()
            plt.close()

    def visualization_points_by_level(self, corner_points, intersection, z_coordinate_list, building_shaft_exhaust_air):
        """The function visualizes the points in a diagram
        Args:
            corner_points: Coordinates of room corner at the ceiling
            intersection: intersection points at the ceiling
            z_coordinate_list: z-Coordinates for each storey
            building_shaft_exhaust_air: building shaft coordinates
        Returns:
           2D diagramm for each ceiling
       """
        if self.export_graphs:
            for z_value in z_coordinate_list:
                xy_values = [(x, y) for x, y, z, a in intersection if z == z_value]
                xy_shaft = (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1])
                xy_values_center = [(x, y) for x, y, z, a in corner_points if z == z_value]

                # Delete xy_shaft out of xy_values and xy_values_center
                xy_values = [xy for xy in xy_values if xy != xy_shaft]
                xy_values_center = [xy for xy in xy_values_center if xy != xy_shaft]

                plt.figure(num=f"Floor plan: {z_value}", figsize=(15, 8), dpi=200)
                plt.xlabel('X-Axis [m]')
                plt.ylabel('Y-Axis [m]')
                plt.grid(False)
                plt.subplots_adjust(left=0.1, bottom=0.1, right=0.96,
                                    top=0.96)

                # Plot for intersection points without shaft
                plt.scatter(*zip(*xy_values), color="r", marker='o', label="Intersection points")

                # Plot for shaft
                plt.scatter(xy_shaft[0], xy_shaft[1], color="g", marker='s', label="Shaft")

                # Plot for air inlets without shaft
                plt.scatter(*zip(*xy_values_center), color="b", marker='D', label="Air inlet")

                plt.title(f'Height: {z_value}')
                plt.legend(loc="best")

                folder_path = Path(self.paths.export / 'ventilation system' / 'exhaust air' / 'plots' / 'blue prints')

                # Create folder
                folder_path.mkdir(parents=True, exist_ok=True)

                # Save graph
                plot_name = "Flor plan Z " + f"{z_value}" + ".png"
                path_and_name = folder_path / plot_name
                plt.savefig(path_and_name)

                # plt.show()
                plt.close()

    def visualisierung_graph(self,
                             G,
                             steiner_tree,
                             z_value,
                             coordinates_without_airflow,
                             filtered_coords_ceiling_without_airflow,
                             filtered_coords_intersection_without_airflow,
                             edge_label,
                             name,
                             edge_unit,
                             total_shell_surface,
                             building_shaft_exhaust_air
                             ):
        """
        :param G: Graph
        :param steiner_tree: Steinerbaum
        :param z_value: Z-axis
        :param coordinates_without_airflow: Schnittpunkte
        :param filtered_coords_ceiling_without_airflow: Koordinaten ohne Volumenstrom
        :param filtered_coords_intersection_without_airflow: Schnittpunkte ohne Volumenstrom
        :param name: name of plot
        :param edge_unit: unit of edge for legend
        :param total_shell_surface: sum of shell surface area
        """
        plt.figure(figsize=(8.3, 5.8) )
        plt.xlabel('X-Axis [m]')
        plt.ylabel('Y-Axis [m]')
        plt.title(name + f", Z: {z_value}")
        plt.grid(False)
        plt.subplots_adjust(left=0.04, bottom=0.04, right=0.96,
                            top=0.96)

        pos = {node: (node[0], node[1]) for node in coordinates_without_airflow}

        entry_to_remove = (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value)

        filtered_coords_ceiling_without_airflow = [entry for entry in filtered_coords_ceiling_without_airflow if
                                                   entry != entry_to_remove]

        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=filtered_coords_ceiling_without_airflow,
                               node_shape='D',
                               node_color='blue',
                               node_size=10)
        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=[(building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value)],
                               node_shape="s",
                               node_color="green",
                               node_size=10)

        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=filtered_coords_intersection_without_airflow,
                               node_shape='o',
                               node_color='red',
                               node_size=50)

        nx.draw_networkx_edges(G, pos, width=1)
        nx.draw_networkx_edges(steiner_tree, pos, width=1, style="-", edge_color="blue")

        # edge labels
        edge_labels = nx.get_edge_attributes(steiner_tree, edge_label)
        try:
            edge_labels_without_unit = {key: float(value.magnitude) for key, value in edge_labels.items()}
        except AttributeError:
            edge_labels_without_unit = edge_labels
        for key, value in edge_labels_without_unit.items():
            try:
                if "Ø" in value:
                    zahl = value.split("Ø")[1].split()[0]  # Nimmt den Teil nach "Ø" und dann die Zahl vor der Einheit
                    edge_labels_without_unit[key] = f"Ø{zahl}"
                elif "x" in value:
                    zahlen = value.split(" x ")
                    breite = zahlen[0].split()[0]
                    hoehe = zahlen[1].split()[0]
                    edge_labels_without_unit[key] = f"{breite} x {hoehe}"
            except:
                None

        # Legend
        legend_ceiling = plt.Line2D([0], [0], marker='D', color='w', label='Air inlet in m³ pro h',
                                    markerfacecolor='blue',
                                    markersize=10)
        legend_intersection = plt.Line2D([0], [0], marker='o', color='w', label='Intersection point',
                                         markerfacecolor='red', markersize=6)
        legend_shaft = plt.Line2D([0], [0], marker='s', color='w', label='Shaft',
                                  markerfacecolor='green', markersize=10)
        legend_steiner_edge = plt.Line2D([0], [0], color='blue', lw=4, linestyle='-.',
                                         label=f'Steiner edge in {edge_unit}')

        if total_shell_surface is not False:
            legend_mantelflaeche = plt.Line2D([0], [0], lw=0, label=f'Shell surface: {total_shell_surface} [m²]')

            plt.legend(
                handles=[legend_ceiling, legend_intersection, legend_shaft, legend_steiner_edge, legend_mantelflaeche],
                loc='best',
                fontsize=8)
        else:
            plt.legend(handles=[legend_ceiling, legend_intersection, legend_shaft, legend_steiner_edge],
                       loc='best')  # , bbox_to_anchor=(1.1, 0.5)

        folder_path = Path(self.paths.export / 'ventilation system' / 'exhaust air' / 'plots' / f"Z_{z_value}")

        # Erstelle den Ordner
        folder_path.mkdir(parents=True, exist_ok=True)

        plot_name = name + " Z " + f"{z_value}" + ".png"
        path_and_name = folder_path / plot_name
        plt.gca().patch.set_alpha(0)
        plt.xlim(-5, 50)
        plt.ylim(-5, 30)
        plt.savefig(path_and_name, transparent=True)

        # plt.show()
        plt.close()


    def necessary_cross_section(self, volume_flow):
        """
        This function calculates the necessary cross section of ducts according to the local air volume flow
        Args:
            volume_flow:
        Returns:
            cross_section [m²]
        """

        # Calculation of cross section with air flow velocity of 5 m³/s according to
        # "Leitfaden zur Auslegung von lufttechnischen Anlagen" page 10 (www.aerotechnik.de)

        cross_section = (volume_flow / (5 * (ureg.meter / ureg.second))).to('meter**2')
        return cross_section

    # air duct dimensions according to EN 1505 table 1
    df_EN_1505 = pd.DataFrame({
        "width": [200 * ureg.millimeter, 250 * ureg.millimeter, 300 * ureg.millimeter, 400 * ureg.millimeter,
                   500 * ureg.millimeter, 600 * ureg.millimeter, 800 * ureg.millimeter, 1000 * ureg.millimeter,
                   1200 * ureg.millimeter, 1400 * ureg.millimeter, 1600 * ureg.millimeter, 1800 * ureg.millimeter,
                   2000 * ureg.millimeter],
        100 * ureg.millimeter: [0.020 * ureg.meter ** 2, 0.025 * ureg.meter ** 2, 0.030 * ureg.meter ** 2,
                                0.040 * ureg.meter ** 2, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
                                np.nan, np.nan],
        150 * ureg.millimeter: [0.030 * ureg.meter ** 2, 0.038 * ureg.meter ** 2, 0.045 * ureg.meter ** 2,
                                0.060 * ureg.meter ** 2, 0.075 * ureg.meter ** 2, 0.090 * ureg.meter ** 2, np.nan,
                                np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
        200 * ureg.millimeter: [0.04 * ureg.meter ** 2, 0.05 * ureg.meter ** 2, 0.06 * ureg.meter ** 2,
                                0.08 * ureg.meter ** 2, 0.10 * ureg.meter ** 2, 0.12 * ureg.meter ** 2,
                                0.16 * ureg.meter ** 2, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
        250 * ureg.millimeter: [np.nan, 0.063 * ureg.meter ** 2, 0.075 * ureg.meter ** 2, 0.100 * ureg.meter ** 2,
                                0.130 * ureg.meter ** 2, 0.150 * ureg.meter ** 2, 0.200 * ureg.meter ** 2,
                                0.250 * ureg.meter ** 2, np.nan, np.nan, np.nan, np.nan, np.nan],
        300 * ureg.millimeter: [np.nan, np.nan, 0.090 * ureg.meter ** 2, 0.120 * ureg.meter ** 2,
                                0.150 * ureg.meter ** 2, 0.180 * ureg.meter ** 2, 0.240 * ureg.meter ** 2,
                                0.300 * ureg.meter ** 2, 0.360 * ureg.meter ** 2, np.nan, np.nan, np.nan, np.nan],
        400 * ureg.millimeter: [np.nan, np.nan, np.nan, 0.160 * ureg.meter ** 2, 0.200 * ureg.meter ** 2,
                                0.240 * ureg.meter ** 2, 0.320 * ureg.meter ** 2, 0.400 * ureg.meter ** 2,
                                0.480 * ureg.meter ** 2, 0.640 * ureg.meter ** 2, np.nan, np.nan, np.nan],
        500 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, 0.250 * ureg.meter ** 2, 0.300 * ureg.meter ** 2,
                                0.400 * ureg.meter ** 2, 0.500 * ureg.meter ** 2, 0.600 * ureg.meter ** 2,
                                0.800 * ureg.meter ** 2, 1.0 * ureg.meter ** 2, np.nan, np.nan],
        600 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, 0.360 * ureg.meter ** 2,
                                0.480 * ureg.meter ** 2, 0.600 * ureg.meter ** 2, 0.720 * ureg.meter ** 2,
                                0.960 * ureg.meter ** 2, 1.2 * ureg.meter ** 2, 1.44 * ureg.meter ** 2, np.nan],
        800 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, 0.560 * ureg.meter ** 2,
                                0.700 * ureg.meter ** 2, 0.840 * ureg.meter ** 2, 1.120 * ureg.meter ** 2,
                                1.4 * ureg.meter ** 2, 1.68 * ureg.meter ** 2, np.nan],
        1000 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, 0.640 * ureg.meter ** 2,
                                 0.800 * ureg.meter ** 2, 0.960 * ureg.meter ** 2, 1.28 * ureg.meter ** 2,
                                 1.6 * ureg.meter ** 2, 1.92 * ureg.meter ** 2],
        1200 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
                                 0.900 * ureg.meter ** 2, 1.080 * ureg.meter ** 2, 1.44 * ureg.meter ** 2,
                                 1.8 * ureg.meter ** 2, 2.16 * ureg.meter ** 2],
        1400 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
                                 1.000 * ureg.meter ** 2, 1.20 * ureg.meter ** 2, 1.60 * ureg.meter ** 2,
                                 2.0 * ureg.meter ** 2],
        1600 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
                                 1.44 * ureg.meter ** 2, 1.68 * ureg.meter ** 2, 1.92 * ureg.meter ** 2],
        1800 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
                                 np.nan, 2.16 * ureg.meter ** 2, 2.40 * ureg.meter ** 2]
    })

    def dimensions_angular_cross_section(self, duct_cross_section, suspended_ceiling_space=2000 * ureg.millimeter,
                                         df_EN_1505=df_EN_1505):
        """
        Function calculates the dimensions of an angle cross-section
        :param duct_cross_section: required duct cross section
        :param suspended_ceiling_space: space in the suspended ceiling
        :param df_EN_1505: DIN EN
        :return: cross_section
        """

        # Create a list of heights as numerical values
        height = pd.to_numeric(df_EN_1505.columns[1:], errors='coerce')

        # Filter the data for heights up to the available height in the suspended_ceiling_space
        filtered_heights = height[height <= suspended_ceiling_space]

        # Calculate the differences and ratios for each combination
        combinations = []
        for index, row in df_EN_1505.iterrows():
            width = row['width']
            for height in filtered_heights:
                surface = row[height]
                if not pd.isna(surface) and surface >= duct_cross_section:
                    diff = abs(surface - duct_cross_section).magnitude
                    ratio = min(width, height) / max(width, height)  # Ratio smaller divided by the
                    # larger
                    combinations.append((width, height, surface, diff, ratio))

        # Create a new dataframe from the combinations
        combinations_df = pd.DataFrame(combinations,
                                       columns=['width', 'height', 'surface', 'Diff', 'ratio'])

        # Find the best combination
        best_combination_index = (combinations_df['Diff'] + abs(combinations_df['Diff'] - 1)).idxmin()
        best_width = combinations_df.at[best_combination_index, 'width']
        best_height = combinations_df.at[best_combination_index, 'height']
        cross_section = f"{best_width} x {best_height}"

        return cross_section

    def dimensions_round_cross_section(self, duct_cross_section, suspended_ceiling_space=2000):
        # ventilation_duct_round_diameter: Is a dict, which has the cross_section [m²] as input variable and the diameter [mm] as
        # output variable is the diameter [mm] according to EN 1506:2007 (D) 4. table 1

        ventilation_duct_round_diameter = {  # 0.00312: 60, nicht lieferbar
            0.00503 * ureg.meter ** 2: 80 * ureg.millimeter,
            0.00785 * ureg.meter ** 2: 100 * ureg.millimeter,
            0.0123 * ureg.meter ** 2: 125 * ureg.millimeter,
            0.0201 * ureg.meter ** 2: 160 * ureg.millimeter,
            0.0314 * ureg.meter ** 2: 200 * ureg.millimeter,
            0.0491 * ureg.meter ** 2: 250 * ureg.millimeter,
            0.0779 * ureg.meter ** 2: 315 * ureg.millimeter,
            0.126 * ureg.meter ** 2: 400 * ureg.millimeter,
            0.196 * ureg.meter ** 2: 500 * ureg.millimeter,
            0.312 * ureg.meter ** 2: 630 * ureg.millimeter,
            0.503 * ureg.meter ** 2: 800 * ureg.millimeter,
            0.785 * ureg.meter ** 2: 1000 * ureg.millimeter,
            1.23 * ureg.meter ** 2: 1250 * ureg.millimeter
        }
        sorted_key = sorted(ventilation_duct_round_diameter.keys())
        for key in sorted_key:
            if key > duct_cross_section and ventilation_duct_round_diameter[key] <= suspended_ceiling_space:
                return f"Ø{ventilation_duct_round_diameter[key]}"
            elif key > duct_cross_section and ventilation_duct_round_diameter[key] > suspended_ceiling_space:
                return f"suspended_ceiling_space too low"

    def dimensions_ventilation_duct(self, cross_section_type, duct_cross_section,
                                    suspended_ceiling_space=2000 * ureg.millimeter):
        """
        Args:
            cross_section_type: round, angular, optimal
            duct_cross_section: required duct_cross_section in m²
            suspended_ceiling_space: available height in the suspended ceiling
        Returns:
             Diameter or edge lengths a x b of the duct
        """

        if cross_section_type == "round":
            return self.dimensions_round_cross_section(duct_cross_section, suspended_ceiling_space)

        elif cross_section_type == "angular":
            return self.dimensions_angular_cross_section(duct_cross_section, suspended_ceiling_space)

        elif cross_section_type == "optimal":
            if self.dimensions_round_cross_section(duct_cross_section,
                                                   suspended_ceiling_space) == "suspended_ceiling_space too low":
                return self.dimensions_angular_cross_section(duct_cross_section, suspended_ceiling_space)
            else:
                return self.dimensions_round_cross_section(duct_cross_section, suspended_ceiling_space)

    def diameter_round_channel(self, duct_cross_section):
        # # ventilation_duct_round_diameter: Is a dict, which has the cross_section [m²] as input variable and the diameter [mm] as
        # diameter [mm] according to EN 1506:2007 (D) 4. table 1

        ventilation_duct_round_diameter = {  # 0.00312: 60, nicht lieferbar
            0.00503 * ureg.meter ** 2: 80 * ureg.millimeter,
            0.00785 * ureg.meter ** 2: 100 * ureg.millimeter,
            0.0123 * ureg.meter ** 2: 125 * ureg.millimeter,
            0.0201 * ureg.meter ** 2: 160 * ureg.millimeter,
            0.0314 * ureg.meter ** 2: 200 * ureg.millimeter,
            0.0491 * ureg.meter ** 2: 250 * ureg.millimeter,
            0.0779 * ureg.meter ** 2: 315 * ureg.millimeter,
            0.126 * ureg.meter ** 2: 400 * ureg.millimeter,
            0.196 * ureg.meter ** 2: 500 * ureg.millimeter,
            0.312 * ureg.meter ** 2: 630 * ureg.millimeter,
            0.503 * ureg.meter ** 2: 800 * ureg.millimeter,
            0.785 * ureg.meter ** 2: 1000 * ureg.millimeter,
            1.23 * ureg.meter ** 2: 1250 * ureg.millimeter
        }
        sorted_key = sorted(ventilation_duct_round_diameter.keys())
        for key in sorted_key:
            if key > duct_cross_section:
                return ventilation_duct_round_diameter[key]

    def coat_area_angular_ventilation_duct(self, duct_cross_section, suspended_ceiling_space=2000 * ureg.millimeter,
                                           df_EN_1505=df_EN_1505):
        # Create a list of heights as numerical values
        height = pd.to_numeric(df_EN_1505.columns[1:], errors='coerce')

        # Filter the data for heights up to the maximum height
        filtered_heights = height[height <= suspended_ceiling_space]

        # Calculate the differences and ratios for each combination
        combinations = []
        for index, row in df_EN_1505.iterrows():
            width = row['width']
            for height in filtered_heights:
                surface = row[height]
                if not pd.isna(surface) and surface >= duct_cross_section:
                    diff = abs(surface - duct_cross_section).magnitude
                    ratio = min(width, height) / max(width,
                                                     height)
                    combinations.append((width, height, surface, diff, ratio))

        # Create a new dataframe from the combinations
        combinations_df = pd.DataFrame(combinations,
                                       columns=['width', 'height', 'surface', 'Diff', 'ratio'])

        # Find the best combination
        best_combination_index = (combinations_df['Diff'] + abs(combinations_df['Diff'] - 1)).idxmin()
        best_width = combinations_df.at[best_combination_index, 'width']
        best_height = combinations_df.at[best_combination_index, 'height']

        circumference = (2 * best_width + 2 * best_height).to(ureg.meter)

        return circumference

    def equivalent_diameter(self, duct_cross_section, suspended_ceiling_space=2000 * ureg.millimeter,
                            df_EN_1505=df_EN_1505):
        # Create a list of heights as numerical values
        height = pd.to_numeric(df_EN_1505.columns[1:], errors='coerce')

        # Filter the data for heights up to the maximum height
        filtered_heights = height[height <= suspended_ceiling_space]

        # Calculate the differences and ratios for each combination
        combinations = []
        for index, row in df_EN_1505.iterrows():
            width = row['width']
            for height in filtered_heights:
                surface = row[height]
                if not pd.isna(surface) and surface >= duct_cross_section:
                    diff = abs(surface - duct_cross_section).magnitude
                    ratio = min(width, height) / max(width,
                                                     height)
                    combinations.append((width, height, surface, diff, ratio))

        # Create a new dataframe from the combinations
        combinations_df = pd.DataFrame(combinations,
                                       columns=['width', 'height', 'surface', 'Diff', 'ratio'])

        # Find the best combination
        best_combination_index = (combinations_df['Diff'] + abs(combinations_df['Diff'] - 1)).idxmin()
        best_width = combinations_df.at[best_combination_index, 'width']
        best_height = combinations_df.at[best_combination_index, 'height']

        # For air ducts with a rectangular cross-section (a × b), the hydraulic diameter according to VDI 2087 is
        equivalent_diameter = (2 * best_width * best_height) / (best_width + best_height)

        return equivalent_diameter

    def coat_area_ventilation_duct(self, cross_section_type, duct_cross_section, suspended_ceiling_space=2000):
        """
        :param cross_section_type: round, angular, optimal
        :param duct_cross_section: duct cross-section in m²
        :param suspended_ceiling_space: available height in the suspended ceiling
        :return: coat area
        """
        if cross_section_type == "round":
            return (math.pi * self.diameter_round_channel(duct_cross_section)).to(ureg.meter)

        elif cross_section_type == "angular":
            return self.coat_area_angular_ventilation_duct(duct_cross_section)

        elif cross_section_type == "optimal":
            if self.diameter_round_channel(duct_cross_section) <= suspended_ceiling_space:
                return (math.pi * self.diameter_round_channel(duct_cross_section)).to(ureg.meter)
            else:
                return self.coat_area_angular_ventilation_duct(duct_cross_section, suspended_ceiling_space)

    def calculated_diameter(self, cross_section_type, duct_cross_section, suspended_ceiling_space=2000):
        """
        :param cross_section_type: round, angular oder optimal
        :param duct_cross_section: duct cross section in m²
        :param suspended_ceiling_space: available height in the suspended ceiling
        :return: calculated diameter of the ventilation duct
        """

        if cross_section_type == "round":
            return self.diameter_round_channel(duct_cross_section)

        elif cross_section_type == "angular":
            return self.equivalent_diameter(duct_cross_section)

        elif cross_section_type == "optimal":
            if self.diameter_round_channel(duct_cross_section) <= suspended_ceiling_space:
                return self.diameter_round_channel(duct_cross_section)
            else:
                return self.equivalent_diameter(duct_cross_section, suspended_ceiling_space)

    def euclidean_distance(self, punkt1, punkt2):
        """
        Calculating the distance between point1 and 2
        :param punkt1:
        :param punkt2:
        :return: Distance between punkt1 and punkt2
        """
        return round(
            math.sqrt((punkt2[0] - punkt1[0]) ** 2 + (punkt2[1] - punkt1[1]) ** 2 + (punkt2[2] - punkt1[2]) ** 2),
            2)


    def find_leaves(self, spanning_tree):
        leaves = []
        for node in spanning_tree:
            if len(spanning_tree[node]) == 1:  # Ein Blatt hat nur einen Nachbarn
                leaves.append(node)
        return leaves

    def find_collisions(self, supply_graph, exhaust_graph):
        def orientation(p, q, r):
            """Get orientation of triples (p, q, r)
            Returns:
            0 -> p, q and r are colinear
            1 -> Clockwise
            2 -> Anti-clockwise
            """
            val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
            if val == 0:
                return 0  # kollinear
            elif val > 0:
                return 1  # im Uhrzeigersinn
            else:
                return 2  # gegen den Uhrzeigersinn

        def find_crossing_edges(p1, q1, p2, q2):
            """Check if edges (p1, q1) and (p2, q2) are cutting each other"""
            o1 = orientation(p1, q1, p2)
            o2 = orientation(p1, q1, q2)
            o3 = orientation(p2, q2, p1)
            o4 = orientation(p2, q2, q1)

            if o1 != o2 and o3 != o4:
                return True
            return False

        def crossing_point(p1, q1, p2, q2):
            """Calculate crossing point of edges (p1, q1) and (p2, q2)"""
            A1 = q1[1] - p1[1]
            B1 = p1[0] - q1[0]
            C1 = A1 * p1[0] + B1 * p1[1]

            A2 = q2[1] - p2[1]
            B2 = p2[0] - q2[0]
            C2 = A2 * p2[0] + B2 * p2[1]

            determinant = A1 * B2 - A2 * B1

            if determinant == 0:
                return None
            else:
                # Berechnung des Schnittpunkts
                x = (B2 * C1 - B1 * C2) / determinant
                y = (A1 * C2 - A2 * C1) / determinant
                return (x, y)

        colinear_edges = set(supply_graph.edges()) & set(exhaust_graph.edges())

        crossing_edges = []
        crossing_points = []
        for (u1, v1) in exhaust_graph.edges():
            for (u2, v2) in supply_graph.edges():
                if find_crossing_edges(u1, v1, u2, v2) and (u1, v1) not in crossing_edges:
                    cross_point = crossing_point(u1, v1, u2, v2)
                    if (cross_point not in (u2, v2)) or \
                        (cross_point == u2 and supply_graph.degree[u2] != 1) or \
                        (cross_point == v2 and supply_graph.degree[v2] != 1):
                            crossing_edges.append(((u2, v2),(u1,v1)))
                            crossing_points.append(cross_point)

        return colinear_edges, crossing_edges, crossing_points

    def check_if_graph_in_building_boundaries(self, graph, z_value):

        def is_point_inside_shape(shape, point):
            """
            Check if a point is inside or on the boundary of a TopoDS_Compound shape.
            Args:
                shape (TopoDS_Shape): The shape to check.
                point (tuple): The coordinates of the point as a tuple (x, y, z).
            Returns:
                bool: True if the point is inside the shape or on its boundary, False otherwise.
            """
            classifier = BRepClass3d_SolidClassifier(shape)
            classifier.Perform(gp_Pnt(*point), 1e-6)
            return classifier.State() in (TopAbs_IN, TopAbs_ON)

        def is_edge_inside_shape(shape, point1, point2, iteration=0.1):
            """
            Check if an edge is inside or on the boundary of a TopoDS_Compound shape.

            Args:
                shape (TopoDS_Shape): The shape to check.
                point1 (tuple): The coordinates of the first point of the edge as a tuple (x, y, z).
                point2 (tuple): The coordinates of the second point of the edge as a tuple (x, y, z).
                num_points (int): The number of points to check along the edge.

            Returns:
                bool: True if the entire edge is inside the shape or on its boundary, False otherwise.
            """
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
            """
            Calculating the distance between point1 and point2
            :param point1:
            :param point2:
            :return: Distance between point1 and point2
            """
            return round(
                math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2),
                2)

        # Check if nodes and edges are inside the building geometry and not running through staircases, etc.

        settings_products = ifcopenshell.geom.main.settings()
        settings_products.set(settings_products.USE_PYTHON_OPENCASCADE, True)
        stories = filter_elements(self.elements, 'Storey')

        storey_z_values = []
        for storey in stories:
            storey_z_values.append(storey.position[2])
        closest_z_value = min(storey_z_values, key=lambda x:abs(x-z_value))

        storey = stories[storey_z_values.index(closest_z_value)]

        slabs = filter_elements(storey.elements, 'InnerFloor')
        groundfloors = filter_elements(storey.elements, 'GroundFloor')
        slabs_and_baseslabs = slabs + groundfloors
        storey_floor_shapes = []
        for bottom_ele in slabs_and_baseslabs:
            if hasattr(bottom_ele.ifc, 'Representation'):
                shape = ifcopenshell.geom.create_shape(
                    settings_products, bottom_ele.ifc).geometry
                storey_floor_shapes.append(shape)

        nodes_floor = [node for node in graph.nodes]
        for node in nodes_floor: # Assuming the nodes have 'x' and 'y' attributes
            if not any(is_point_inside_shape(shape, node) for shape in storey_floor_shapes):
                self.logger.info(f"Node {node} is not inside the building boundaries")
                if any(type in graph.nodes[node]["type"] for type in ["radiator_forward",
                                                                      "radiator_backward"]):
                    assert KeyError(f"Delivery node {node} not in building boundaries")
                graph.remove_node(node)

        edges_floor = [edge for edge in graph.edges()]
        for edge in edges_floor:
            if not any(is_edge_inside_shape(shape, edge[0], edge[1]) for shape in storey_floor_shapes):
                self.logger.info(f"Edge {edge} does not intersect boundaries")
                graph.remove_edge(edge[0], edge[1])
        return graph

    def minimize_collisions_with_supply_graph(self, supply_graph, exhaust_graph, terminal_nodes):

        def check_terminal_node_connection(exhaust_graph, terminal_nodes, shaft_node):
            connected_components = list(nx.connected_components(exhaust_graph))
            for components in connected_components:
                if shaft_node in components:
                    if all(element in components for element in terminal_nodes):
                        return True
            return False


        colinear_edges, crossing_edges, crossing_points = self.find_collisions(supply_graph, exhaust_graph)
        exhaust_crossing_edges = [edge[1] for edge in crossing_edges]

        for node, data in exhaust_graph.nodes(data=True):
            if data['color'] == 'green':
                shaft_node = node

        exhaust_graph.remove_edges_from(colinear_edges)
        exhaust_graph.remove_edges_from(exhaust_crossing_edges)

        if not check_terminal_node_connection(exhaust_graph, terminal_nodes, shaft_node):

            not_connected_terminal_nodes = []
            connected_components = list(nx.connected_components(exhaust_graph))
            for components in connected_components:
                if shaft_node not in components:
                    for terminal_node in terminal_nodes:
                        if terminal_node in components and terminal_node not in not_connected_terminal_nodes:
                            not_connected_terminal_nodes.append(terminal_node)

            new_nodes = []
            for terminal_node in not_connected_terminal_nodes:
                deleted_edges_from_terminal_node = [edge for edge in exhaust_crossing_edges if terminal_node in [edge[0],edge[1]]]
                for edge in deleted_edges_from_terminal_node:
                    exhaust_graph.add_edge(edge[0], edge[1], length=self.euclidean_distance(edge[0], edge[1]))
                    for node in edge:
                        if node != terminal_node:
                            new_nodes.append(node)

        if not check_terminal_node_connection(exhaust_graph, terminal_nodes, shaft_node):

            trigger = True
            i = 0
            while trigger:
                i += 1
                new_new_nodes = []
                for node in new_nodes:
                    edges_to_be_added_again = [edge for edge in exhaust_crossing_edges if node in [edge[0], edge[1]] and
                                               edge not in exhaust_graph.edges()]
                    for edge in edges_to_be_added_again:
                        exhaust_graph.add_edge(edge[0], edge[1], length=self.euclidean_distance(edge[0], edge[1]))
                        for new_node in edge:
                            if new_node != node:
                                new_new_nodes.append(new_node)
                new_nodes = new_new_nodes

                if check_terminal_node_connection(exhaust_graph, terminal_nodes, shaft_node):
                    trigger = False

                if i == 200:
                    assert KeyError("Exhaust graph cannot be connected properly!")

        for components in list(nx.connected_components(exhaust_graph)):
            if all(element in components for element in terminal_nodes):
                exhaust_graph = exhaust_graph.subgraph(list(components))

        return exhaust_graph

    # Todo Ab hier weiter aufräumen
    def create_graph(self, ceiling_point, intersection_points, z_coordinate_list, building_shaft_exhaust_air,
                     querschnittsart, suspended_ceiling_space):
        """The function creates a connected graph for each floor
        Args:
           ceiling_point: Point at the ceiling in the middle of the room
           intersection points: intersection points at the ceiling
           z_coordinate_list: z coordinates for each storey ceiling
           building_shaft_exhaust_air: Coordinate of the shaft
           querschnittsart: rund, eckig oder optimal
           suspended_ceiling_space: verfügbare Höhe (in [mmm]) in der Zwischendecke angegeben! Diese
            entspricht dem verfügbaren Abstand zwischen UKRD (Unterkante Rohdecke) und OKFD (Oberkante Fertigdecke),
            siehe https://www.ctb.de/_wiki/swb/Massbezuege.php
        Returns:
           connected graph for each floor
       """

        def knick_in_lueftungsleitung(lueftungsauslass_zu_x):
            if lueftungsauslass_zu_x != []:
                # Extrahiere die X- und Y-Koordinaten
                x_coords = [x for x, _, _ in lueftungsauslass_zu_x[0]]
                y_coords = [y for _, y, _ in lueftungsauslass_zu_x[0]]

                # Überprüfe, ob alle X-Koordinaten gleich sind oder alle Y-Koordinaten gleich sind
                same_x = all(x == x_coords[0] for x in x_coords)
                same_y = all(y == y_coords[0] for y in y_coords)

                if same_x == True or same_y == True:
                    return False
                else:
                    return True
            else:
                None

        def metric_closure(G, weight="weight"):
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

        def steiner_tree(G, terminal_nodes, weight="weight"):
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

        # Hier werden leere Dictonaries für die einzelnen Höhen erstellt:
        dict_steiner_tree_with_duct_length = {schluessel: None for schluessel in z_coordinate_list}
        dict_steiner_tree_with_air_volume_exhaust_air = {schluessel: None for schluessel in z_coordinate_list}
        dict_steiner_tree_with_duct_cross_section = {schluessel: None for schluessel in z_coordinate_list}
        dict_steiner_tree_with_calculated_cross_section = {schluessel: None for schluessel in z_coordinate_list}
        dict_steinertree_with_shell = {schluessel: None for schluessel in z_coordinate_list}

        for z_value in z_coordinate_list:

            # Hier werden die Koordinaten nach Ebene gefiltert
            filtered_coords_ceiling = [coord for coord in ceiling_point if coord[2] == z_value]
            filtered_coords_intersection = [coord for coord in intersection_points if coord[2] == z_value]
            coordinates = filtered_coords_intersection + filtered_coords_ceiling

            # Koordinaten ohne Luftmengen:
            filtered_coords_ceiling_without_airflow = [(x, y, z) for x, y, z, a in filtered_coords_ceiling]
            filtered_coords_intersection_without_airflow = [(x, y, z) for x, y, z, a in
                                                            filtered_coords_intersection]
            coordinates_without_airflow = (filtered_coords_ceiling_without_airflow
                                           + filtered_coords_intersection_without_airflow)

            # Erstellt den Graphen
            G = nx.Graph()

            # Terminals:
            # Terminals sind die vordefinierten Knoten in einem Graphen, die in der Lösung des Steinerbaum-Problems
            # unbedingt miteinander verbunden werden müssen
            terminals = list()

            # Hinzufügen der Knoten für Lüftungsauslässe zu Terminals
            for x, y, z, a in filtered_coords_ceiling:
                if x == building_shaft_exhaust_air[0] and y == building_shaft_exhaust_air[1]:
                    G.add_node((x, y, z), weight=a, color="green")
                else:
                    G.add_node((x, y, z), weight=a, color="orange")
                if a > 0:  # Bedingung, um Terminals zu bestimmen (z.B. Gewicht > 0)
                    terminals.append((x, y, z))

            for x, y, z, a in filtered_coords_intersection:
                G.add_node((x, y, z), weight=0, color="red")

            # Kanten entlang der X-Achse hinzufügen
            unique_coords = set(coord[0] for coord in coordinates_without_airflow)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in coordinates_without_airflow if coord[0] == u],
                                            key=lambda c: c[1 - 0])
                for i in range(len(nodes_on_same_axis) - 1):
                    gewicht_kante_y = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], length=gewicht_kante_y)

            # Kanten entlang der Y-Achse hinzufügen
            unique_coords = set(coord[1] for coord in coordinates_without_airflow)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in coordinates_without_airflow if coord[1] == u],
                                            key=lambda c: c[1 - 1])
                for i in range(len(nodes_on_same_axis) - 1):
                    gewicht_kante_x = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], length=gewicht_kante_x)

            """
            #### TESTING OF COLLISION ALGORITHM

            # TEST SUPPLY GRAPH

            nodes_mesh_supply = []
            x = 37.95
            y = 5.25
            for i in range(12):
                for j in range(12):
                    node = (x + i * 0.5, y + j * 0.5, -0.3)
                    nodes_mesh_supply.append(node)

            test_supply = self.supply_graph.copy()

            test_nodes_supply = [(38.5, 5.5, -0.3), (4.5, 11.5, -0.3), (40.0, 9.0, -0.3), (41, 2.8, -0.3), (39.0, 6.5, -0.3), (39.5, 5.0, -0.3), (39.0, 11.0, -0.3), (39.0, 10.5, -0.3), (43.5, 11.0, -0.3), (38.5, 7.5, -0.3), (40.0, 6.5, -0.3), (42.0, 7.5, -0.3), (10.5, 8.0, -0.3), (43.0, 6.0, -0.3), (38.0, 8.0, -0.3), (38.5, 10.0, -0.3), (43.0, 5.5, -0.3), (41.5, 6.0, -0.3), (43.0, 10.0, -0.3), (43.5, 8.5, -0.3), (38.0, 5.5, -0.3), (42.0, 9.5, -0.3), (42.5, 8.0, -0.3), (3.1, 4.5, -0.3), (41.0, 5.0, -0.3), (38.0, 10.0, -0.3), (43.0, 7.5, -0.3), (41.5, 8.0, -0.3), (4.5, 8.0, -0.3), (41.5, 7.5, -0.3), (40.0, 7.5, -0.3), (38.0, 7.5, -0.3), (41.0, 7.0, -0.3), (39.5, 6.0, -0.3), (35.9, 8.0, -0.3), (44.0, 7.0, -0.3), (41.5, 9.5, -0.3), (40.0, 9.5, -0.3), (38.5, 8.5, -0.3), (42.0, 7.0, -0.3), (39.0, 5.0, -0.3), (39.5, 8.0, -0.3), (39.5, 7.5, -0.3), (40.0, 5.0, -0.3), (44.0, 9.0, -0.3), (38.5, 10.5, -0.3), (40.5, 8.0, -0.3), (39.0, 7.0, -0.3), (42.5, 9.0, -0.3), (44.0, 8.5, -0.3), (25.4, 11.5, -0.3), (43.0, 8.5, -0.3), (43.5, 7.0, -0.3), (44.0, 6.5, -0.3), (39.5, 9.5, -0.3), (38.5, 6.0, -0.3), (42.0, 8.0, -0.3), (42.5, 6.5, -0.3), (44.0, 10.5, -0.3), (42.5, 11.0, -0.3), (21.0, 11.5, -0.3), (42.5, 10.5, -0.3), (43.5, 9.0, -0.3), (42.0, 5.5, -0.3), (38.0, 6.0, -0.3), (38.5, 8.0, -0.3), (40.5, 9.0, -0.3), (42.0, 10.0, -0.3), (13.5, 11.5, -0.3), (16.6, 11.5, -0.3), (41.0, 9.5, -0.3), (40.0, 8.0, -0.3), (40.5, 6.5, -0.3), (40.5, 11.0, -0.3), (39.0, 8.0, -0.3), (43.5, 5.5, -0.3), (40.5, 10.5, -0.3), (41.5, 5.5, -0.3), (40.0, 5.5, -0.3), (43.5, 10.0, -0.3), (41.5, 10.0, -0.3), (39.5, 10.5, -0.3), (38.5, 9.0, -0.3), (40.5, 8.5, -0.3), (43.5, 7.5, -0.3), (44.0, 5.0, -0.3), (39.0, 9.5, -0.3), (38.5, 6.5, -0.3), (42.5, 5.0, -0.3), (7.5, 11.5, -0.3), (39.5, 5.5, -0.3), (43.0, 9.0, -0.3), (21.0, 8.0, -0.3), (42.5, 7.0, -0.3), (38.0, 9.0, -0.3), (3.1, 8.0, -0.3), (43.0, 6.5, -0.3), (43.5, 5.0, -0.3), (38.0, 8.5, -0.3), (43.0, 11.0, -0.3), (41.5, 6.5, -0.3), (40.5, 5.0, -0.3), (42.0, 6.0, -0.3), (43.0, 10.5, -0.3), (16.6, 8.0, -0.3), (41.5, 11.0, -0.3), (9.1, 8.0, -0.3), (41.0, 6.0, -0.3), (38.0, 11.0, -0.3), (41.5, 10.5, -0.3), (42.5, 8.5, -0.3), (41.0, 5.5, -0.3), (38.0, 10.5, -0.3), (41.0, 10.0, -0.3), (41.5, 8.5, -0.3), (40.5, 7.0, -0.3), (41.0, 7.5, -0.3), (39.5, 6.5, -0.3), (38.5, 5.0, -0.3), (39.5, 11.0, -0.3), (44.0, 7.5, -0.3), (39.0, 6.0, -0.3), (1.6, 11.5, -0.3), (39.0, 5.5, -0.3), (43.5, 6.0, -0.3), (39.0, 10.0, -0.3), (39.5, 8.5, -0.3), (40.0, 6.0, -0.3), (25.4, 8.0, -0.3), (44.0, 9.5, -0.3), (43.0, 5.0, -0.3), (40.0, 10.0, -0.3), (39.0, 7.5, -0.3), (42.5, 9.5, -0.3), (43.5, 8.0, -0.3), (38.0, 5.0, -0.3), (42.0, 9.0, -0.3), (42.0, 8.5, -0.3), (43.0, 7.0, -0.3), (38.5, 11.0, -0.3), (41.5, 7.0, -0.3), (40.0, 7.0, -0.3), (43.5, 9.5, -0.3), (38.0, 7.0, -0.3), (38.0, 6.5, -0.3), (42.0, 10.5, -0.3), (40.5, 9.5, -0.3), (41.5, 9.0, -0.3), (13.5, 8.0, -0.3), (40.0, 8.5, -0.3), (40.0, 11.0, -0.3), (43.5, 6.5, -0.3), (41.0, 8.0, -0.3), (39.0, 8.5, -0.3), (39.5, 7.0, -0.3), (1.6, 8, -0.3), (43.5, 10.5, -0.3), (44.0, 8.0, -0.3), (40.0, 10.5, -0.3), (38.5, 9.5, -0.3), (43.0, 8.0, -0.3), (44.0, 6.0, -0.3), (39.5, 9.0, -0.3), (44.0, 5.5, -0.3), (42.5, 6.0, -0.3), (7.5, 8.0, -0.3), (44.0, 10.0, -0.3), (42.5, 5.5, -0.3), (42.5, 10.0, -0.3), (42.0, 5.0, -0.3), (10.5, 11.5, -0.3), (43.0, 9.5, -0.3), (38.5, 7.0, -0.3), (42.5, 7.5, -0.3), (38.0, 9.5, -0.3), (41.0, 9.0, -0.3), (40.5, 6.0, -0.3), (9.1, 4.5, -0.3), (41.0, 8.5, -0.3), (42.0, 6.5, -0.3), (40.5, 5.5, -0.3), (40.5, 10.0, -0.3), (41.0, 6.5, -0.3), (41.5, 5.0, -0.3), (26.9, 8.0, -0.3), (41.0, 11.0, -0.3), (39.5, 10.0, -0.3), (41.0, 10.5, -0.3), (40.5, 7.5, -0.3), (44.0, 11.0, -0.3), (42.0, 11.0, -0.3), (39.0, 9.0, -0.3)]

            for node in nodes_mesh_supply:
                if node not in test_supply.nodes():
                    test_supply.add_node(node, color="red")
            # Kanten entlang der X-Achse hinzufügen
            unique_coords = set(coord[0] for coord in nodes_mesh_supply)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in nodes_mesh_supply if coord[0] == u],
                                            key=lambda c: c[1 - 0])
                for i in range(len(nodes_on_same_axis) - 1):
                    gewicht_kante_y = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    test_supply.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], length=gewicht_kante_y,
                                  color="black")
            # Kanten entlang der Y-Achse hinzufügen
            unique_coords = set(coord[1] for coord in nodes_mesh_supply)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in nodes_mesh_supply if coord[1] == u],
                                            key=lambda c: c[1 - 1])
                for i in range(len(nodes_on_same_axis) - 1):
                    gewicht_kante_x = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    test_supply.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], length=gewicht_kante_x,
                                  color="black")

            #self.visualize_networkx(graph=test_supply)
            #plt.show()


            # TEST EXHAUST GRAPH

            nodes_mesh_exhaust = []
            x = 37.7
            y = 5
            for i in range(13):
                for j in range(13):
                    node = (x + i * 0.5, y + j * 0.5, -0.3)
                    nodes_mesh_exhaust.append(node)
            nodes_graph_exhaust = [node for node in G.nodes()]
            nodes_exhaust = list(set(nodes_mesh_exhaust + nodes_graph_exhaust))
            test_exhaust = nx.Graph()

            for node in nodes_exhaust:
                if node not in test_exhaust.nodes():
                    test_exhaust.add_node(node, color="red")

            # Kanten entlang der X-Achse hinzufügen
            unique_coords = set(coord[0] for coord in nodes_exhaust)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in nodes_exhaust if coord[0] == u],
                                            key=lambda c: c[1 - 0])
                for i in range(len(nodes_on_same_axis) - 1):
                    gewicht_kante_y = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    test_exhaust.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], length=gewicht_kante_y,
                                         color="black")
            # Kanten entlang der Y-Achse hinzufügen
            unique_coords = set(coord[1] for coord in nodes_exhaust)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in nodes_exhaust if coord[1] == u],
                                            key=lambda c: c[1 - 1])
                for i in range(len(nodes_on_same_axis) - 1):
                    gewicht_kante_x = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    test_exhaust.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], length=gewicht_kante_x,
                                         color="black")

            #self.visualize_networkx(graph=test_exhaust)
            #plt.show()


            #test1 = self.minimize_collisions_with_supply_graph(test_supply, test_exhaust, terminals)
            """

            self.logger.info("Check if nodes and edges of forward graph are inside the boundaries of the building")
            G = self.check_if_graph_in_building_boundaries(G, z_value)
            self.logger.info("Check done")

            # Checke Kollisionen mit Zuluftgraph und lösche entsprechende Kanten im Abluftgraph
            G = self.minimize_collisions_with_supply_graph(self.supply_graph, G, terminals)

            # Erstellung des Steinerbaums
            steiner_baum = steiner_tree(G, terminals, weight="length")

            if self.export_graphs:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          edge_label = "length",
                                          name=f"Steinerbaum 0. Optimierung",
                                          edge_unit="m",
                                          total_shell_surface=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            # Extraierung der Knoten und Katen aus dem Steinerbaum
            knoten = list(steiner_baum.nodes())
            kanten = list(steiner_baum.edges())

            # Erstellung des Baums
            tree = nx.Graph()

            # Hinzufügen der Knoten zum Baum
            for x, y, z in knoten:
                for point in coordinates:
                    if point[0] == x and point[1] == y and point[2] == z:
                        tree.add_node((x, y, z), weight=point[3])

            # Hinzufügen der Kanten zum Baum
            for kante in kanten:
                tree.add_edge(kante[0], kante[1], length=self.euclidean_distance(kante[0], kante[1]))

            # Hier wird der minimale Spannbaum des Steinerbaums berechnet
            minimum_spanning_tree = nx.minimum_spanning_tree(tree)

            """Optimierungsschritt 1"""
            # Hier wird überprüft, welche Punkte entlang eines Pfades, auf einer Achse liegen.
            # Ziel ist es die Steinerpunkte zu finden, die zwischen zwei Terminalen liegen, damit der Graph
            # optimiert werden kann
            coordinates_on_same_axis = list()
            for startknoten in filtered_coords_ceiling_without_airflow:
                for zielknoten in filtered_coords_ceiling_without_airflow:
                    for path in nx.all_simple_paths(minimum_spanning_tree, startknoten, zielknoten):
                        # Extrahiere die X- und Y-Koordinaten
                        x_coords = [x for x, _, _ in path]
                        y_coords = [y for _, y, _ in path]

                        # Überprüfe, ob alle X-Koordinaten gleich sind oder alle Y-Koordinaten gleich sind
                        same_x = all(x == x_coords[0] for x in x_coords)
                        same_y = all(y == y_coords[0] for y in y_coords)

                        if same_x == True or same_y == True:
                            for cord in path:
                                coordinates_on_same_axis.append(cord)

            # Doppelte entfernen:
            coordinates_on_same_axis = set(coordinates_on_same_axis)

            # Wenn die coordinate ein Lüftungsausslass ist, muss diese ignoriert werden
            coordinates_on_same_axis = [item for item in coordinates_on_same_axis if item not in
                                        filtered_coords_ceiling_without_airflow]

            # Hinzufügen der Koordinaten zu den Terminalen
            for coord in coordinates_on_same_axis:
                terminals.append(coord)

            # Erstellung des neuen Steinerbaums
            steiner_baum = steiner_tree(G, terminals, weight="length")

            if self.export_graphs:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          edge_label = "length",
                                          name=f"Steinerbaum 1. Optimierung",
                                          edge_unit="m",
                                          total_shell_surface=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            """Optimierungschritt 2"""
            # Hier wird überprüft, ob unnötige Umlenkungen im Graphen vorhanden sind:
            for lueftungsauslass in filtered_coords_ceiling_without_airflow:
                if steiner_baum.degree(lueftungsauslass) == 2:
                    neighbors = list(nx.all_neighbors(steiner_baum, lueftungsauslass))

                    nachbarauslass_eins = neighbors[0]
                    temp = list()
                    i = 0
                    while nachbarauslass_eins not in filtered_coords_ceiling_without_airflow:
                        temp.append(nachbarauslass_eins)
                        neue_nachbarn = list(nx.all_neighbors(steiner_baum, nachbarauslass_eins))
                        neue_nachbarn = [koord for koord in neue_nachbarn if koord != lueftungsauslass]
                        nachbarauslass_eins = [koord for koord in neue_nachbarn if koord != temp[i - 1]]
                        nachbarauslass_eins = nachbarauslass_eins[0]
                        i += 1
                        if nachbarauslass_eins in filtered_coords_ceiling_without_airflow:
                            break

                    nachbarauslass_zwei = neighbors[1]
                    temp = list()
                    i = 0
                    while nachbarauslass_zwei not in filtered_coords_ceiling_without_airflow:
                        temp.append(nachbarauslass_zwei)
                        neue_nachbarn = list(nx.all_neighbors(steiner_baum, nachbarauslass_zwei))
                        neue_nachbarn = [koord for koord in neue_nachbarn if koord != lueftungsauslass]
                        nachbarauslass_zwei = [koord for koord in neue_nachbarn if koord != temp[i - 1]]
                        nachbarauslass_zwei = nachbarauslass_zwei[0]
                        i += 1
                        if nachbarauslass_zwei in filtered_coords_ceiling_without_airflow:
                            break

                    # Gibt den Pfad vom Nachbarauslass 1 zum Lüftungsauslass in Form von Knoten zurück
                    lueftungsauslass_zu_eins = list(nx.all_simple_paths(steiner_baum, lueftungsauslass,
                                                                        nachbarauslass_eins))

                    # Gibt den Pfad vom Lüftungsauslass zum Nachbarauslass 2 in Form von Knoten zurück
                    lueftungsauslass_zu_zwei = list(nx.all_simple_paths(steiner_baum, lueftungsauslass,
                                                                        nachbarauslass_zwei))

                    if knick_in_lueftungsleitung(lueftungsauslass_zu_eins) == False and knick_in_lueftungsleitung(
                            lueftungsauslass_zu_zwei) == False:
                        None
                    elif knick_in_lueftungsleitung(lueftungsauslass_zu_eins) == True:
                        if lueftungsauslass_zu_eins != [] and lueftungsauslass_zu_zwei != []:
                            if lueftungsauslass[0] == lueftungsauslass_zu_zwei[0][1][0]:
                                terminals.append((lueftungsauslass[0], nachbarauslass_eins[1], z_value))
                            elif lueftungsauslass[1] == lueftungsauslass_zu_zwei[0][1][1]:
                                terminals.append((nachbarauslass_eins[0], lueftungsauslass[1], z_value))
                    elif knick_in_lueftungsleitung(lueftungsauslass_zu_zwei) == True:
                        if lueftungsauslass_zu_eins != [] and lueftungsauslass_zu_zwei != []:
                            if lueftungsauslass[0] == lueftungsauslass_zu_eins[0][1][0]:
                                terminals.append((lueftungsauslass[0], nachbarauslass_zwei[1], z_value))
                            elif lueftungsauslass[1] == lueftungsauslass_zu_eins[0][1][1]:
                                terminals.append((nachbarauslass_zwei[0], lueftungsauslass[1], z_value))

            # Erstellung des neuen Steinerbaums
            steiner_baum = steiner_tree(G, terminals, weight="length")

            if self.export_graphs:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          edge_label = "length",
                                          name=f"Steinerbaum 2. Optimierung",
                                          edge_unit="m",
                                          total_shell_surface=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            """3. Optimierung"""
            # Hier werden die Blätter aus dem Graphen ausgelesen
            blaetter = self.find_leaves(steiner_baum)

            # Entfernen der Blätter die kein Lüftungsauslass sind
            for blatt in blaetter:
                if blatt not in filtered_coords_ceiling_without_airflow:
                    terminals.remove(blatt)

            # Erstellung des neuen Steinerbaums
            steiner_baum = steiner_tree(G, terminals, weight="length")

            # Add unit
            for u, v, data in steiner_baum.edges(data=True):
                gewicht_ohne_einheit = data['length']

                # Füge die Einheit meter hinzu
                gewicht_mit_einheit = gewicht_ohne_einheit * ureg.meter

                # Aktualisiere das Gewicht der Kante im Steinerbaum
                data['length'] = gewicht_mit_einheit

            if self.export_graphs:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          edge_label = "length",
                                          name=f"Steinerbaum 3. Optimierung",
                                          edge_unit="m",
                                          total_shell_surface=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            # Steinerbaum mit Leitungslängen
            dict_steiner_tree_with_duct_length[z_value] = deepcopy(steiner_baum)

            # Hier wird der Startpunt zu den Blättern gesetzt
            start_punkt = (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value)

            # Erstellung des Baums (hier wird der neue, erste verbesserte Baum erstellt! Die Punkte, welche alle
            # zwischen zwei Lüftungsauslässen liegen, werden genutzt, um andere Kanäle auch über die gleich
            # Achse zu verlegen

            # Extraierung der Knoten und Kanten aus dem Steinerbaum
            knoten = list(steiner_baum.nodes())
            kanten = list(steiner_baum.edges())

            tree = nx.Graph()

            # Hinzufügen der Knoten zum Baum
            for x, y, z in knoten:
                for point in coordinates:
                    if point[0] == x and point[1] == y and point[2] == z:
                        tree.add_node((x, y, z), weight=point[3])

            # Hinzufügen der Kanten zum Baum
            for kante in kanten:
                tree.add_edge(kante[0], kante[1], length=self.euclidean_distance(kante[0], kante[1]))

            # Hier wird der minimale Spannbaum des Steinerbaums berechnet
            minimum_spanning_tree = nx.minimum_spanning_tree(tree)

            # Hier werden die Wege im Baum vom Lüftungsauslass zum Startpunkt ausgelesen
            ceiling_point_to_root_list = list()
            for point in filtered_coords_ceiling_without_airflow:
                for path in nx.all_simple_edge_paths(minimum_spanning_tree, point, start_punkt):
                    ceiling_point_to_root_list.append(path)

            # Hier werden die Gewichte der Kanten im Steinerbaum gelöscht, da sonst die Luftmenge auf den
            # Abstand addiert wird. Es darf aber auch anfangs nicht das Gewicht der Kante zu 0 gesetzt
            # werden, da sonst der Steinerbaum nicht korrekt berechnet wird
            for u, v in steiner_baum.edges():
                steiner_baum[u][v]["volume flow"] = 0

            # Hier werden die Luftvolumina entlang des Strangs aufaddiert
            for ceiling_point_to_root in ceiling_point_to_root_list:
                for startpunkt, zielpunkt in ceiling_point_to_root:
                    # Suche die Lüftungsmenge zur coordinate:
                    wert = None
                    for x, y, z, a in coordinates:
                        if x == ceiling_point_to_root[0][0][0] and y == ceiling_point_to_root[0][0][1] and z == \
                                ceiling_point_to_root[0][0][2]:
                            wert = a
                    steiner_baum[startpunkt][zielpunkt]["volume flow"] += wert

            # Hier wird der einzelne Steinerbaum mit Volumenstrom der Liste hinzugefügt
            dict_steiner_tree_with_air_volume_exhaust_air[z_value] = deepcopy(steiner_baum)

            if self.export_graphs:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          edge_label="volume flow",
                                          name=f"Steinerbaum mit Luftmenge m³ pro h",
                                          edge_unit="m³/h",
                                          total_shell_surface=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )


            for u, v in steiner_baum.edges():
                steiner_baum[u][v]["cross_section"] = self.dimensions_ventilation_duct(querschnittsart,
                                                                             self.necessary_cross_section(
                                                                                 steiner_baum[u][v][
                                                                                     "volume flow"]),
                                                                             suspended_ceiling_space)

            # Hinzufügen des Graphens zum Dict
            dict_steiner_tree_with_duct_cross_section[z_value] = deepcopy(steiner_baum)

            if self.export_graphs:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          edge_label="cross_section",
                                          name=f"Steinerbaum mit Kanalquerschnitt in mm",
                                          edge_unit="mm",
                                          total_shell_surface=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            # Hier wird der Leitung der äquivalente Durchmesser des Kanals zugeordnet
            for u, v in steiner_baum.edges():
                steiner_baum[u][v]["equivalent_diameter"] = self.calculated_diameter(querschnittsart,
                                                                                     self.necessary_cross_section(
                                                                                                 steiner_baum[
                                                                                                     u][v][
                                                                                                     "volume flow"]),
                                                                                     suspended_ceiling_space)

            # Zum Dict hinzufügen
            dict_steiner_tree_with_calculated_cross_section[z_value] = deepcopy(steiner_baum)

            if self.export_graphs:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          edge_label="equivalent_diameter",
                                          name=f"Steinerbaum mit rechnerischem Durchmesser in mm",
                                          edge_unit="mm",
                                          total_shell_surface=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )
            # Um die gesamte Menge der Mantelfläche zu bestimmen, muss diese aufaddiert werden:
            gesamte_matnelflaeche_luftleitung = 0

            # Hier wird der Leitung die Mantelfläche des Kanals zugeordnet
            for u, v in steiner_baum.edges():
                steiner_baum[u][v]["circumference"] = round(self.coat_area_ventilation_duct(querschnittsart,
                                                                                            self.necessary_cross_section(
                                                                                  steiner_baum[u][v]["volume flow"]),
                                                                                            suspended_ceiling_space), 2
                                                     )

                gesamte_matnelflaeche_luftleitung += round(steiner_baum[u][v]["volume flow"], 2)

            # Hinzufügen des Graphens zum Dict
            dict_steinertree_with_shell[z_value] = deepcopy(steiner_baum)

            if self.export_graphs:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          edge_label="circumference",
                                          name=f"Steinerbaum mit Mantelfläche",
                                          edge_unit="m²/m",
                                          total_shell_surface="",
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            self.write_json_graph(graph=steiner_baum,
                                  filename=f"exhaust_air_floor_Z_{z_value}.json")

        return (
            dict_steiner_tree_with_duct_length, dict_steiner_tree_with_duct_cross_section, dict_steiner_tree_with_air_volume_exhaust_air,
            dict_steinertree_with_shell, dict_steiner_tree_with_calculated_cross_section)

    def ahu_shaft(self,
                  z_coordinate_list,
                  building_shaft_exhaust_air,
                  airflow_volume_per_storey,
                  position_rlt,
                  dict_steiner_tree_with_duct_length,
                  dict_steiner_tree_with_duct_cross_section,
                  dict_steiner_tree_with_air_volume,
                  dict_steiner_tree_with_sheath_area,
                  dict_steiner_tree_with_calculated_cross_section):

        nodes_schacht = list()
        z_coordinate_list = list(z_coordinate_list)
        # Ab hier wird er Graph für das RLT-Gerät bis zum Schacht erstellt.
        Schacht = nx.Graph()

        for z_value in z_coordinate_list:
            # Hinzufügen der Knoten
            Schacht.add_node((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value),
                             weight=airflow_volume_per_storey[z_value], color="green")
            nodes_schacht.append((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value,
                                  airflow_volume_per_storey[z_value]))

        # Ab hier wird der Graph über die Geschosse hinweg erstellt:
        # Kanten für Schacht hinzufügen:
        for i in range(len(z_coordinate_list) - 1):
            weight = self.euclidean_distance(
                [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], float(z_coordinate_list[i])],
                [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1],
                 float(z_coordinate_list[i + 1])]) * ureg.meter
            Schacht.add_edge((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_coordinate_list[i]),
                             (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_coordinate_list[i + 1]),
                             length=weight)

        # Summe Airflow
        summe_airflow = sum(airflow_volume_per_storey.values())

        # Knoten der RLT-Anlage mit Gesamtluftmenge anreichern
        Schacht.add_node((position_rlt[0], position_rlt[1], position_rlt[2]),
                         weight=summe_airflow, color="green")

        Schacht.add_node((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_rlt[2]),
                         weight=summe_airflow, color="green")

        # Verbinden der RLT Anlage mit dem Schacht
        rlt_schacht_weight = self.euclidean_distance([position_rlt[0], position_rlt[1], position_rlt[2]],
                                                     [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1],
                                                       position_rlt[2]]
                                                     ) * ureg.meter

        Schacht.add_edge((position_rlt[0], position_rlt[1], position_rlt[2]),
                         (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_rlt[2]),
                         length=rlt_schacht_weight)

        # Wenn die RLT nicht in der Ebene einer Decke liegt, muss die Luftleitung noch mit dem Schacht verbunden werden
        list_schacht_nodes = list(Schacht.nodes())
        closest = None
        min_distance = float('inf')

        for coord in list_schacht_nodes:
            # Skip if it's the same coordinate
            if coord == (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_rlt[2]):
                continue
            # Check if the x and y coordinates are the same
            if coord[0] == building_shaft_exhaust_air[0] and coord[1] == building_shaft_exhaust_air[1]:
                distance = abs(coord[2] - position_rlt[2])
                if distance < min_distance:
                    min_distance = distance
                    closest = coord

        verbindung_weight = self.euclidean_distance(
            [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_rlt[2]],
            closest
        ) * ureg.meter
        Schacht.add_edge((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_rlt[2]),
                         closest,
                         length=verbindung_weight)

        # Zum Dict hinzufügen
        dict_steiner_tree_with_duct_length["Schacht"] = deepcopy(Schacht)

        position_rlt_ohne_airflow = (position_rlt[0], position_rlt[1], position_rlt[2])

        # Hier werden die Wege im Baum vom Lüftungsauslass zum Startpunkt ausgelesen
        schacht_to_rlt = list()
        for point in Schacht.nodes():
            for path in nx.all_simple_edge_paths(Schacht, point, position_rlt_ohne_airflow):
                schacht_to_rlt.append(path)

        # Hier werden die Gewichte der Kanten im Steinerbaum gelöscht, da sonst die Luftmenge auf den
        # Abstand addiert wird. Es darf aber auch anfangs nicht das Gewicht der Kante zu 0 gesetzt
        # werden, da sonst der Steinerbaum nicht korrekt berechnet wird
        for u, v in Schacht.edges():
            Schacht[u][v]["volume flow"] = 0

        # Hier werden die Luftvolumina entlang des Strangs aufaddiert
        for schachtpunkt_zu_rlt in schacht_to_rlt:
            for startpunkt, zielpunkt in schachtpunkt_zu_rlt:
                # Suche die Lüftungsmenge zur coordinate:
                wert = int()
                for x, y, z, a in nodes_schacht:
                    if x == schachtpunkt_zu_rlt[0][0][0] and y == schachtpunkt_zu_rlt[0][0][1] and z == \
                            schachtpunkt_zu_rlt[0][0][2]:
                        wert = a
                Schacht[startpunkt][zielpunkt]["volume flow"] += wert

        # Zum Dict hinzufügen
        dict_steiner_tree_with_air_volume["Schacht"] = deepcopy(Schacht)

        # Kanalquerschnitt Schacht und RLT zu Schacht bestimmen
        for u, v in Schacht.edges():
            Schacht[u][v]["cross_section"] = self.dimensions_ventilation_duct("eckig",
                                                                               self.necessary_cross_section(
                                                                                   Schacht[u][v][
                                                                                       "volume flow"]),
                                                                               suspended_ceiling_space=2000
                                                                               )

        # Zum Dict hinzufügen
        dict_steiner_tree_with_duct_cross_section["Schacht"] = deepcopy(Schacht)

        # Hier wird der Leitung die Mantelfläche des Kanals zugeordnet
        for u, v in Schacht.edges():
            Schacht[u][v]["circumference"] = round(self.coat_area_ventilation_duct("eckig",
                                                                                   self.necessary_cross_section(
                                                                         Schacht[u][v]["volume flow"]),
                                                                                   suspended_ceiling_space=2000
                                                                                   ),
                                            2
                                            )

        # Zum Dict hinzufügen
        dict_steiner_tree_with_sheath_area["Schacht"] = deepcopy(Schacht)

        # Hier wird der Leitung der äquivalente Durchmesser des Kanals zugeordnet
        for u, v in Schacht.edges():
            Schacht[u][v]["equivalent_diameter"] = self.calculated_diameter("eckig",
                                                                            self.necessary_cross_section(
                                                                                       Schacht[u][v]["volume flow"]),
                                                                            suspended_ceiling_space=2000)

        # Zum Dict hinzufügen
        dict_steiner_tree_with_calculated_cross_section["Schacht"] = deepcopy(Schacht)

        self.write_json_graph(graph=Schacht,
                              filename=f"exhaust_air_shaft.json")

        return (dict_steiner_tree_with_duct_length,
                dict_steiner_tree_with_duct_cross_section,
                dict_steiner_tree_with_air_volume,
                dict_steiner_tree_with_sheath_area,
                dict_steiner_tree_with_calculated_cross_section)

    def finde_abmessung(self, text: str):
        if "Ø" in text:
            # Fall 1: "Ø" gefolgt von einer Zahl
            zahl = ureg(text.split("Ø")[1])  # Teilt den String am "Ø" und nimmt den zweiten Teil
            return zahl
        else:
            # Fall 2: "250 x 200" Format
            zahlen = text.split(" x ")  # Teilt den String bei " x "
            breite = ureg(zahlen[0])
            hoehe = ureg(zahlen[1])
            return breite, hoehe

    def three_dimensional_graph(self,
                                dict_steiner_tree_with_duct_length,
                                dict_steiner_tree_with_duct_cross_section,
                                dict_steiner_tree_with_air_volume_exhaust_air,
                                dict_steinertree_with_shell,
                                dict_steiner_tree_with_calculated_cross_section,
                                position_rlt,
                                dict_coordinate_with_space_type):

        # Eine Hilfsfunktion, um den Graphen rekursiv zu durchlaufen, die Kanten zu richten und die Gewichte zu übernehmen
        def add_edges_and_nodes(G, current_node, H, parent=None):
            # Kopieren Sie die Knotenattribute von H zu G
            G.add_node(current_node, **H.nodes[current_node])
            for neighbor in H.neighbors(current_node):
                if neighbor != parent:
                    # Das Gewicht und ggf. weitere Attribute für die Kante abrufen
                    edge_data = H.get_edge_data(current_node, neighbor)
                    # Fügen Sie eine gerichtete Kante mit den kopierten Attributen hinzu
                    G.add_edge(current_node, neighbor, **edge_data)
                    # Rekursiver Aufruf für den Nachbarn
                    add_edges_and_nodes(G, neighbor, H, current_node)

        # Hier werden leere Graphen erstellt. Diese werden im weiteren Verlauf mit den Graphen der einzelnen Ebenen
        # angereichert
        graph_leitungslaenge = nx.Graph()
        graph_air_volume_flow = nx.Graph()
        graph_duct_cross_section = nx.Graph()
        graph_shell_surface = nx.Graph()
        graph_calculated_diameter = nx.Graph()

        position_rlt = (position_rlt[0], position_rlt[1], position_rlt[2])

        # für Leitungslänge
        for baum in dict_steiner_tree_with_duct_length.values():
            graph_leitungslaenge = nx.compose(graph_leitungslaenge, baum)

        # Graph für Leitungslänge in einen gerichteten Graphen umwandeln
        graph_leitungslaenge_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_leitungslaenge_gerichtet, position_rlt, graph_leitungslaenge)

        # für Luftmengen
        for baum in dict_steiner_tree_with_air_volume_exhaust_air.values():
            graph_air_volume_flow = nx.compose(graph_air_volume_flow, baum)

        # Graph für Luftmengen in einen gerichteten Graphen umwandeln
        graph_luftmengen_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_luftmengen_gerichtet, position_rlt, graph_air_volume_flow)

        # für Kanalquerschnitt
        for baum in dict_steiner_tree_with_duct_cross_section.values():
            graph_duct_cross_section = nx.compose(graph_duct_cross_section, baum)

        # Graph für Kanalquerschnitt in einen gerichteten Graphen umwandeln
        graph_kanalquerschnitt_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_kanalquerschnitt_gerichtet, position_rlt, graph_duct_cross_section)

        # für Mantelfläche
        for baum in dict_steinertree_with_shell.values():
            graph_shell_surface = nx.compose(graph_shell_surface, baum)

        # Graph für Mantelfläche in einen gerichteten Graphen umwandeln
        graph_mantelflaeche_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_mantelflaeche_gerichtet, position_rlt, graph_shell_surface)

        # für rechnerischen Querschnitt
        for baum in dict_steiner_tree_with_calculated_cross_section.values():
            graph_calculated_diameter = nx.compose(graph_calculated_diameter, baum)

        # Graph für rechnerischen Querschnitt in einen gerichteten Graphen umwandeln
        graph_rechnerischer_durchmesser_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_rechnerischer_durchmesser_gerichtet, position_rlt, graph_calculated_diameter)

        dataframe_distribution_network_exhaust_air = pd.DataFrame(columns=[
            'starting_node',
            'target_node',
            'edge',
            'room type starting_node',
            'room type target_node',
            'duct length',
            'Air volume',
            'duct cross section',
            'Surface area',
            'calculated diameter'
        ])

        # Daten der Datenbank hinzufügen
        for u, v in graph_leitungslaenge_gerichtet.edges():
            temp_df = pd.DataFrame({
                'starting_node': [v],  # Gedreht da Abluft
                'target_node': [u],  # Gedreht da Abluft
                'edge': [(v, u)],  # Gedreht da Abluft
                'room type starting_node': [dict_coordinate_with_space_type.get(v, None)],
                'room type target_node': [dict_coordinate_with_space_type.get(u, None)],
                'duct length': [graph_leitungslaenge_gerichtet.get_edge_data(u, v)["length"]],
                'Air volume': [graph_luftmengen_gerichtet.get_edge_data(u, v)["volume flow"]],
                'duct cross section': [graph_kanalquerschnitt_gerichtet.get_edge_data(u, v)["cross_section"]],
                'Surface area': [graph_mantelflaeche_gerichtet.get_edge_data(u, v)["circumference"] *
                                 graph_leitungslaenge_gerichtet.get_edge_data(u, v)["length"]],
                'calculated diameter': [graph_rechnerischer_durchmesser_gerichtet.get_edge_data(u, v)["equivalent_diameter"]]
            })
            dataframe_distribution_network_exhaust_air = pd.concat([dataframe_distribution_network_exhaust_air, temp_df],
                                                                  ignore_index=True)

        for index, zeile in dataframe_distribution_network_exhaust_air.iterrows():
            kanalquerschnitt = zeile['duct cross section']

            if "Ø" in kanalquerschnitt:
                # Finde den Durchmesser und aktualisiere den entsprechenden Wert in der Datenbank
                dataframe_distribution_network_exhaust_air.at[index, 'diameter'] = str(
                    self.finde_abmessung(kanalquerschnitt))

            elif "x" in kanalquerschnitt:
                # Finde Breite und Höhe, zerlege den Querschnittswert und aktualisiere die entsprechenden Werte in der Datenbank
                breite, hoehe = self.finde_abmessung(kanalquerschnitt)
                dataframe_distribution_network_exhaust_air.at[index, 'width'] = str(breite)
                dataframe_distribution_network_exhaust_air.at[index, 'height'] = str(hoehe)

        if self.export_graphs:
            # Darstellung des 3D-Graphens:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

            # Knotenpositionen in 3D
            pos = {coord: (coord[0], coord[1], coord[2]) for coord in list(graph_air_volume_flow.nodes())}

            # Knoten zeichnen
            for node, weight in nx.get_node_attributes(graph_air_volume_flow, 'weight').items():
                if weight > 0:  # Überprüfen, ob das Gewicht größer als 0 ist
                    color = 'blue'
                else:
                    color = 'red'  # Andernfalls rot (oder eine andere Farbe für Gewicht = 0)

                # Zeichnen des Knotens mit der bestimmten Farbe
                ax.scatter(*node, color=color)

            # Kanten zeichnen
            for edge in graph_air_volume_flow.edges():
                start, end = edge
                x_start, y_start, z_start = pos[start]
                x_end, y_end, z_end = pos[end]
                ax.plot([x_start, x_end], [y_start, y_end], [z_start, z_end], "black")

            # Achsenbeschriftungen und Titel
            ax.set_xlabel('X-Achse [m]')
            ax.set_ylabel('Y-Achse [m]')
            ax.set_zlabel('Z-Achse [m]')
            ax.set_title("3D Graph Zuluft")

            # Füge eine Legende hinzu, falls gewünscht
            ax.legend()

            # Diagramm anzeigen
            plt.close()

        return (graph_leitungslaenge_gerichtet,
                graph_luftmengen_gerichtet,
                graph_kanalquerschnitt_gerichtet,
                graph_mantelflaeche_gerichtet,
                graph_rechnerischer_durchmesser_gerichtet,
                dataframe_distribution_network_exhaust_air
                )

    def calculate_pressure_loss(self,
                     dict_steiner_tree_with_duct_length,
                     z_coordinate_list,
                     position_rlt,
                     position_schacht,
                     graph_leitungslaenge,
                     graph_air_volume_flow,
                     graph_duct_cross_section,
                     graph_shell_surface,
                     graph_calculated_diameter,
                     dataframe_distribution_network_exhaust_air):
        # Standardwerte für Berechnung
        rho = 1.204 * (ureg.kilogram / (ureg.meter ** 3))  # Dichte der Luft bei Standardbedingungen
        nu = 1.33 * 0.00001  # Dynamische Viskosität der Luft

        def darstellung_t_stueck(eingang1, eingang2, kanal):
            """
            Erstelle eine 3D-Graphen des T-Stücks
            :param eingang1: Lufteinleitung 1 in T-Stück
            :param eingang2: Lufteinleitung 2 in T-Stück
            :param kanal: Kanal
            :return: Grafik
            """
            # Erstellen eines 3D-Plots
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

            # Funktion zum Zeichnen eines Pfeils
            def zeichne_pfeil(start, ende, farbe, stil='solid'):
                ax.quiver(start[0], start[1], start[2], ende[0] - start[0], ende[1] - start[1], ende[2] - start[2],
                          color=farbe, linestyle=stil, arrow_length_ratio=0.1)

            # Zeichnen der Linien mit Pfeilen
            zeichne_pfeil(eingang1[0], eingang1[1], 'green',
                          'dashed')  # Eingang1
            zeichne_pfeil(eingang2[0], eingang2[1], 'red',
                          'dashed')  # Eingang2
            zeichne_pfeil(kanal[0], kanal[1], 'blue')  # Kanal gestrichelt in Blau

            # Setzen der Achsenbeschriftungen
            ax.set_xlabel('X Achse')
            ax.set_ylabel('Y Achse')
            ax.set_zlabel('Z Achse')

            # Titel des Plots
            ax.set_title('3D Darstellung der Leitungen')

            # Anpassen der Achsengrenzen basierend auf den Koordinaten
            alle_koordinaten = eingang1 + eingang2 + kanal
            x_min, x_max = min(k[0] for k in alle_koordinaten), max(k[0] for k in alle_koordinaten)
            y_min, y_max = min(k[1] for k in alle_koordinaten), max(k[1] for k in alle_koordinaten)
            z_min, z_max = min(k[2] for k in alle_koordinaten), max(k[2] for k in alle_koordinaten)

            ax.set_xlim([x_min - 1, x_max + 1])
            ax.set_ylim([y_min - 1, y_max + 1])
            ax.set_zlim([z_min - 1, z_max + 1])

            # Anzeigen des Plots
            # plt.show()

            plt.close()

        def check_if_lines_are_aligned(line1, line2):
            """
            Überprüft ob zwei Geraden im Raum paralell sind
            :param line1: Linie 1 (x,y,z)
            :param line2: Linie 2 (x,y,z)
            :return: True or False
            """
            # Berechnung der Richtungsvektoren für beide Geraden
            vector1 = np.array([line1[1][0] - line1[0][0], line1[1][1] - line1[0][1], line1[1][2] - line1[0][2]])
            vector2 = np.array([line2[1][0] - line2[0][0], line2[1][1] - line2[0][1], line2[1][2] - line2[0][2]])

            # Überprüfen, ob die Vektoren Vielfache voneinander sind
            # Dies erfolgt durch Kreuzprodukt, das null sein sollte, wenn sie ausgerichtet sind
            cross_product = np.cross(vector1, vector2)

            return np.all(cross_product == 0)

        def widerstandsbeiwert_bogen_rund(winkel: int, mittlerer_radius: float, durchmesser: float) -> float:
            """
            Berechnet den Widerstandsbeiwert fpr einen Bogen rund A01 nach VDI 3803 Blatt 6
            :param winkel: Winkel in Grad
            :param mittlerer_radius: Mittlerer Radius des Bogens in Metern
            :param durchmesser: Durchmesser der Leitung in Metern
            :return: Widerstandsbeiwert Bogen rund A01 nach VDI 3803 Blatt 6
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * winkel)

            b = None
            if 0.5 <= mittlerer_radius / durchmesser <= 1.0:
                b = 0.21 / ((mittlerer_radius / durchmesser) ** 2.5)
            elif 1 <= mittlerer_radius / durchmesser:
                b = (0.21 / (math.sqrt(mittlerer_radius / durchmesser)))

            c = 1

            return a * b * c

        def widerstandsbeiwert_bogen_eckig(winkel, mittlerer_radius, hoehe, breite, rechnerischer_durchmesser):
            """
            Berechnet den Widerstandsbeiwert für einen Bogen eckig A02 nach VDI 3803 Blatt 6
            :param winkel: Winkel in Grad
            :param mittlerer_radius: mittlerer Radius des Bogens in Metern
            :param hoehe: Hoehe der Leitung in Metern
            :param breite: Breite der Leiutung in Metern
            :param rechnerischer_durchmesser: Rechnerischer Durchmesser der Leitung in Metern
            :return: Widerstandsbeiwert Bogen eckig
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * winkel)

            b = 0
            if 0.5 <= (mittlerer_radius / rechnerischer_durchmesser) <= 1.0:
                b = 0.21 / ((mittlerer_radius / rechnerischer_durchmesser) ** 2.5)
            elif 1 <= mittlerer_radius / rechnerischer_durchmesser:
                b = (0.21 / (math.sqrt(mittlerer_radius / rechnerischer_durchmesser)))

            c = (- 1.03663 * 10 ** (-4) * (hoehe / breite) ** 5 + 0.00338 * (hoehe / breite) ** 4 - 0.04277 * (
                    hoehe / breite)
                 ** 3 + 0.25496 * (hoehe / breite) ** 2 - 0.66296 * (hoehe / breite) + 1.4499)

            return a * b * c

        def widerstandsbeiwert_querschnittsverengung_stetig(d_1, d_2):
            """
            Berechnet den Widerstandsbeiwert bei einer Querschnittsverengung A15 nach VDI 3803 Blatt 6
            :param d_1: Durchmesser Lufteingang in Metern
            :param d_2: Durchmesser Luftausgang in Metern
            :return: Widerstandsbeiwert für Querschnittsverengung
            """

            if d_1 <= d_2:
                self.logger.error("Durchmesser 2 darf nicht größer als Durchmesser 1 sein!")

            else:
                l = 0.3 * ureg.meter  # Als Standardlänge werden 0,5 Meter festgelegt

                # Winkel
                beta = math.degrees(math.atan((d_1 - d_2) / (2 * l)))

                # Beiwert:
                k_1 = - 0.0125 + 0.00135 * beta

                # Querschnitt 1:
                A_1 = math.pi * d_1 ** 2 / 4

                # Querschnitt 2:
                A_2 = math.pi * d_2 ** 2 / 4

                zeta_1 = - (k_1) * (A_2 / A_1) ** 2 + k_1

                if zeta_1 < 0:
                    zeta_1 = 0

                return zeta_1

        def widerstandsbeiwert_querschnittserweiterung_stetig(d_1, d_2):
            """
            Berechnet den Widerstandsbeiwert bei einer Querschnittserweiterung A14 nach VDI 3803 Blatt 6
            :param d_1: Durchmesser Lufteingang in Metern
            :param d_2: Durchmesser Luftausgang in Metern
            :return: Widerstandsbeiwert für Querschnittserweiterung
            """

            if d_1 >= d_2:
                self.logger.error("Durchmesser 1 darf nicht größer als Durchmesser 2 sein!")

            else:
                l = 0.3 * ureg.meter  # Als Standardlänge werden 0,5 Meter festgelegt

                # Winkel
                beta = math.degrees(math.atan((d_2 - d_1) / (2 * l)))

                # Beiwert:
                eta_D = 1.01 / (1 + 10 ** (-0.05333 * (24.15 - beta)))

                # Querschnitt 1:
                A_1 = math.pi * d_1 ** 2 / 4

                # Querschnitt 2:
                A_2 = math.pi * d_2 ** 2 / 4

                zeta_1 = (1 - A_1 / A_2) ** 2 * (1 - eta_D)

                return zeta_1

        def widerstandsbeiwert_T_stueck_trennung_rund(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                      v_A: float,
                                                      richtung: str) -> float:
            """
            Berechnet den Widerstandbeiwert für eine T-Trennung A22 nach VDI 3803 Blatt 6
            :param d: Durchmesser des Eingang in Metern
            :param v: Volumenstrom des Eingangs in m³/h
            :param d_D: Durchmesser des Durchgangs in Metern
            :param v_D: Volumenstrom des Durchgangs in m³/h
            :param d_A: Durchmesser des Abgangs in Metern
            :param v_A: Volumenstrom des Abgangs in m³/h
            :param richtung: "Durchgangsrichtung" oder "abzweigende Richtung"
            :return: Widerstandbeiwert für eine T-Trennung A22
            """

            # Querschnitt Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Durchgang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgang
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            # Beiwert
            K_D = 0.4

            if richtung == "Durchgangsrichtung":
                zeta_D = (K_D * (1 - w_D / w) ** 2) / (w_D / w) ** 2
                return zeta_D
            elif richtung == "abzweigende Richtung":
                # Es wird Form "a" nach VDI 3803 Blatt 6 gewählt
                zeta_A = 0.26 + 55.29 * math.exp(-(w_A / w) / 0.1286) + 555.26 * math.exp(
                    -(w_A / w) / 0.041) + 5.73 * math.exp(-(w_A / w) / 0.431)
                return zeta_A
            else:
                self.logger.error("Keine oder falsche Richtungseingabe")

        def widerstandsbeiwert_T_stueck_trennung_eckig(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                       v_A: float, richtung: str) -> float:
            """
            Berechnet den Widerstandbeiwert für eine T-Trennung A24 nach VDI 3803 Blatt 6
            :param d: rechnerischer Durchmesser des Eingang in Metern
            :param v: Volumenstrom des Eingangs in m³/h
            :param d_D: rechnerischer Durchmesser des Durchgangs in Metern
            :param v_D: Volumenstrom des Durchgangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abgangs in Metern
            :param v_A: Volumenstrom des Abgangs in m³/h
            :param richtung: "Durchgangsrichtung" oder "abzweigende Richtung"
            :return: Widerstandbeiwert für eine T-Trennung A24
            """

            # Querschnitt Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Durchgang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgang
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            if richtung == "Durchgangsrichtung":
                K_1 = 183.3
                K_2 = 0.06
                K_3 = 0.17

                zeta_D = K_1 / (math.exp(w_D / w * 1 / K_2)) + K_3

                return zeta_D

            elif richtung == "abzweigende Richtung":
                K_1 = 301.95
                K_2 = 0.06
                K_3 = 0.75

                zeta_D = K_1 / (math.exp(w_A / w * 1 / K_2)) + K_3

                return zeta_D
            else:
                self.logger.error("Keine oder falsche Richtungseingabe")

        def widerstandsbeiwert_kruemmerendstueck_eckig(a: float, b: float, d: float, v: float, d_A: float, v_A: float):
            """
            Berechnet den Widerstandsbeiwert für Krümmerabzweig A25 nach VDI 3803
            :param a: Höhe des Eingangs in Metern
            :param b: Breite des Eingangs in Metern
            :param d: rechnerischer Durchmesser des Eingangs in Metern
            :param v: Volumenstrom des Eingangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abzweiges in Metern
            :param v_A: Volumenstrom des Abzweiges in m³/h
            :return: Widerstandsbeiwert für Krümmerabzweig A25 nach VDI 3803
            """

            # Querschnitt Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            K_1 = 0.0644
            K_2 = 0.0727
            K_3 = 0.3746
            K_4 = -3.4885

            zeta_A = (K_1 * a / b + K_2) * (w_A / w) ** (K_3 * math.log(a / b) + K_4)

            return zeta_A

        def widerstandsbeiwert_T_endstueck_rund(d: float, v: float, d_A: float, v_A: float):
            """
            Berechnet den Widerstandsbeiwert für ein T-Stück rund A27 nach VDI 3803
            :param d: rechnerischer Durchmesser des Eingangs in Metern
            :param v: Volumenstrom des Eingangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abzweiges in Metern
            :param v_A: Volumenstrom des Abzweiges in m³/h
            :return: Widerstandsbeiwert für ein T-Stück rund A27 nach VDI 3803
            """

            # Querschnitt Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            Y_0 = 0.662
            A_1 = 128.6
            t_1 = 0.0922
            A_2 = 15.13
            t_2 = 0.3138

            zeta_A = Y_0 + A_1 * math.exp(-(w_A / w) * 1 / t_1) + A_2 * math.exp(-(w_A / w) * 1 / t_2)

            return zeta_A

        def wiederstandsbeiwert_T_endstueck_stromvereinigung_rund(d_A: float, v_A: float, d: float, v: float):
            """
            Berechnet den Widerstandsbeiwert für ein T-Stück rund A30 nach VDI 3803 Blatt 6
            :param d_A: rechnerischer Durchmesser des Eingangs in Metern
            :param v_A: Volumenstrom des Eingangs in m³/h
            :param d: rechnerischer Durchmesser des HAuptstroms Kanals in Metern
            :param v: Volumenstrom des Hauptstrom Kanals in m³/h
            :return: Widerstandsbeiwert für ein T-Stück rund A30 nach VDI 3803
            """
            # Beiwerte
            K_1 = 109.63
            K_2 = -35.79
            K_3 = 0.013
            K_4 = 0.144
            K_5 = 1.829
            K_6 = -0.38

            # Querschnitt Kanal:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Hauptkanal
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Teilstrom:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Teilstrom
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            zeta = (K_1 / (A_A / A) + K_2) * math.exp((-w_A / w) / (K_3 / (A_A / A + K_4))) + (
                        K_5 * (1 / (A_A / A)) ** K_6)

            return zeta

        def wiederstandsbeiwert_T_endstueck_stromvereinigung_eckig():
            """
            Berechnet den Widerstandsbeiwert für ein T-Stück eckig A31 nach VDI 3803 Blatt 6
            :return: Wiederstandsbeiwert auf der sicheren Seite
            """
            return 0.28

        def wiederstandsbeiwert_T_stueck_stromvereinigung_rund(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                               v_A: float, richtung: str, alpha: float = 90) -> float:
            """
            Berechnet den Widerstandbeiwert für eine T-Vereinigung A28 nach VDI 3803 Blatt 6
            :param d: rechnerischer Durchmesser des Kanals in Metern
            :param v: Volumenstrom des Kanals in m³/h
            :param d_D: rechnerischer Durchmesser des Eingangs des Durchgangs in Metern
            :param v_D: Volumenstrom des Eingangs des Durchgangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abgangs in Metern
            :param v_A: Volumenstrom des Abgangs in m³/h
            :param richtung: "Durchgangsrichtung" oder "zuströmende Richtung"
            :param alpha: Winkel in Grad
            :return: Widerstandbeiwert für eine T-Vereinigung A28
            """

            # ToDo This function doesnt work if there is an additional air inlet/outlet at the junction,
            # which creates a 4 way junction instead of a t-fitting, since A_D + A_A might be smaller than A.
            # This case also isnt included in VDI 3803 Blatt 6

            # Querschnitt Kanals:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Kanals
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Durchgangsrichtung Eingang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgangrichtung Eingang
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            if richtung == "Durchgangsrichtung":
                if A_A + A_D > A or A_D == A:
                    # Beiwerte
                    K1 = -906.220
                    K2 = -740.620
                    K3 = -0.197
                    K4 = 0.132
                    K5 = 0.078
                    K6 = 0.0054
                    K7 = -158.058
                    K8 = -1.517
                    K9 = 152.528
                    K10 = 34.897
                    K11 = 0.530
                    K12 = -0.527
                    K13 = -11.215
                    K14 = -1.705
                    K15 = 1.799

                    xi = (K1 * (A_A / A) + K2) * np.exp(-(w_A / w) / (K3 * (A_A / A) + K4) + K5 * A_A / A + K6)
                    a = K7 + K9 * np.exp(((A_A / A) - K8) / K10)
                    b = K11 + K12 * np.exp((A_A / A) / K13)
                    c = K14 * (A_A / A) + K15

                    gamma = a + b * alpha ** c

                    # Widerstandsbeiwert ζ_D
                    zeta = xi * gamma

                    return zeta

                # elif A_A + A_D == A:
                # Temporary solution for problem described above
                elif A_A + A_D <= A:
                    K1 = 43.836
                    K2 = 26.78
                    K3 = 0.20
                    K4 = 2.7804
                    K5 = -0.6327

                    zeta = (K1 * A_A / A + K2) * math.exp(-(w_A / w) / K3) + (K4 * A_A / A + K5)

                    return zeta

            elif richtung == "zuströmende Richtung":
                if A_A + A_D > A or A_D == A:
                    # Beiwerte
                    K1 = 80.953
                    K2 = -64.126
                    K3 = 0.17
                    K4 = 0.5784
                    K5 = 0.4834

                    zeta = (K1 * A_A / A + K2) * math.exp(-(w_A / w) / K3) + (K4 * A_A / A + K5)

                    return zeta

                # elif A_A + A_D == A:
                # Temporary solution for problem described above
                elif A_A + A_D <= A:
                    # Beiwerte
                    K1 = -232.1
                    K2 = -38.743
                    K3 = 0.171
                    K4 = -2.477
                    K5 = 0.597

                    zeta = (K1 * A_A / A + K2) * math.exp(-(w_A / w) / K3) + (K4 * A_A / A + K5)

                    return zeta

        def wiederstandsbeiwert_T_stueck_stromvereinigung_eckig(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                                v_A: float, richtung: str) -> float:
            """
            Berechnet den Widerstandbeiwert für eine T-Vereinigung A28 nach VDI 3803 Blatt 6
            :param d: rechnerischer Durchmesser des Kanals in Metern
            :param v: Volumenstrom des Kanals in m³/h
            :param d_D: rechnerischer Durchmesser des Eingangs des Durchgangs in Metern
            :param v_D: Volumenstrom des Eingangs des Durchgangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abgangs in Metern
            :param v_A: Volumenstrom des Abgangs in m³/h
            :param richtung: "Durchgangsrichtung" oder "zuströmende Richtung"
            :return: Widerstandbeiwert für eine T-Vereinigung A29 nach VDI 3803-6
            """
            # Querschnitt Kanals:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Kanals
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Durchgangsrichtung Eingang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgangrichtung Eingang
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            if richtung == "Durchgangsrichtung":
                # Eingabewerte
                input_points = np.array([
                    [1.0, 0.5],  # A_D/A, A_A/A für die erste Zeile
                    [0.5, 0.5],  # A_D/A, A_A/A für die zweite Zeile
                    [1.0, 1.0]  # A_D/A, A_A/A für die dritte Zeile
                ])

                # a-Werte
                a2_values = np.array([-0.5604, -1.8281, -0.2756])
                a1_values = np.array([1.0706, 2.8312, 1.7256])
                a0_values = np.array([-0.2466, -0.6536, -1.8292])

                # Zweidimensionale Interpolationsfunktionen für a2, a1, a0
                def interpolate_2d_durchgehende_richtung(A_D, A_A, A):
                    input_point = np.array([(A_D / A, A_A / A)])

                    # Verwendung von 'nearest' als Workaround für Extrapolation
                    a2 = griddata(input_points, a2_values, input_point, method='nearest')[0]
                    a1 = griddata(input_points, a1_values, input_point, method='nearest')[0]
                    a0 = griddata(input_points, a0_values, input_point, method='nearest')[0]

                    return a2, a1, a0

                a2, a1, a0 = interpolate_2d_durchgehende_richtung(A_D, A_A, A)

                zeta = a2 * (1 / (w_D / w)) ** 2 + a1 * (1 / (w_D / w)) + a0

                return zeta

            elif richtung == "zuströmende Richtung":
                # Eingabewerte
                input_points = np.array([
                    [1.0, 0.5],  # A_D/A, A_A/A für die erste Zeile
                    [0.5, 0.5],  # A_D/A, A_A/A für die zweite Zeile
                    [1.0, 1.0]  # A_D/A, A_A/A für die dritte Zeile
                ])

                # b-Werte
                b2_values = np.array([-0.5769, -2.644, -0.8982])
                b1_values = np.array([0.5072, 2.7448, 2.8556])
                b0_values = np.array([0.4924, -0.1258, -1.5221])

                # Zweidimensionale Interpolationsfunktionen für b2, b1, b0
                def interpolate_2d_abzweigende_richtung(A_D, A_A, A):
                    input_point = np.array([(A_D / A, A_A / A)])

                    # Verwendung von 'nearest' als Workaround für Extrapolation
                    b2 = griddata(input_points, b2_values, input_point, method='nearest')[0]
                    b1 = griddata(input_points, b1_values, input_point, method='nearest')[0]
                    b0 = griddata(input_points, b0_values, input_point, method='nearest')[0]

                    return b2, b1, b0

                b2, b1, b0 = interpolate_2d_abzweigende_richtung(A_D, A_A, A)

                zeta = b2 * (1 / (w_A / w)) ** 2 + b1 * (1 / (w_A / w)) + b0

                return zeta

        # Position der RLT-Auslesen
        position_rlt = (position_rlt[0], position_rlt[1], position_rlt[2])

        # Erstellung einer BFS-Reihenfolge ab dem Startpunkt
        lueftungskanal_zuluft_richtung = list(nx.edge_bfs(graph_leitungslaenge, position_rlt))

        # Für die Abluft muss die Luft vom Deckeneinlass zur RLT strömen. Daher muss die Richtung der Koordinaten
        # umgedreht werden

        lueftungskanal_abluft_richtung = [(b, a) for a, b in lueftungskanal_zuluft_richtung]

        graph_leitungslaenge_abluft = nx.DiGraph()

        # Kanten in der BFS-Reihenfolge zum neuen Graphen hinzufügen
        for edge in lueftungskanal_abluft_richtung:
            graph_leitungslaenge_abluft.add_edge(*edge)

        # Druckverlustberechnung
        # Netz erstellen:
        net = pp.create_empty_network(fluid="air")

        # Auslesen des Fluides
        fluid = pp.get_fluid(net)

        # Auslesen der Dichte
        dichte = fluid.get_density(temperature=293.15) * ureg.kilogram / ureg.meter ** 3

        # Definition der Parameter für die Junctions
        name_junction = [coordinate for coordinate in list(graph_leitungslaenge_abluft.nodes())]
        index_junction = [index for index, wert in enumerate(name_junction)]

        # Erstellen einer Liste für jede Koordinatenachse
        x_koordinaten = [coordinate[0] for coordinate in list(graph_leitungslaenge_abluft.nodes())]
        y_koordinaten = [coordinate[1] for coordinate in list(graph_leitungslaenge_abluft.nodes())]
        z_koordinaten = [coordinate[2] for coordinate in list(graph_leitungslaenge_abluft.nodes())]

        """2D-Koordinaten erstellen"""
        # Da nur 3D Koordinaten vorhanden sind, jedoch 3D Koordinaten gebraucht werden wird ein Dict erstellt, welches
        # jeder 3D coordinate einen 2D-coordinate zuweist
        zwei_d_koodrinaten = dict()
        position_schacht_graph = (position_schacht[0], position_schacht[1], position_schacht[2])

        # Leitung von RLT zu Schacht
        pfad_rlt_zu_schacht = list(nx.all_simple_paths(graph_leitungslaenge, position_rlt, position_schacht_graph))[0]
        anzahl_punkte_pfad_rlt_zu_schacht = len(pfad_rlt_zu_schacht)

        for point in pfad_rlt_zu_schacht:
            zwei_d_koodrinaten[point] = (-anzahl_punkte_pfad_rlt_zu_schacht, 0)
            anzahl_punkte_pfad_rlt_zu_schacht -= 1

        anzahl_knoten_mit_mindestens_drei_kanten = len(
            [node for node, degree in graph_leitungslaenge.degree() if degree >= 3])

        # Versuch, alle Keys in Zahlen umzuwandeln und zu sortieren
        sorted_keys = sorted(
            (key for key in dict_steiner_tree_with_duct_length.keys() if key != "Schacht"),
            key=lambda x: float(x)
        )

        y = 0  # Start y-coordinate



        for key in sorted_keys:
            graph_geschoss = dict_steiner_tree_with_duct_length[key]

            # TODO Pressure loss coefficient for collisions of exhaust and supply air distribution systems should be
            #  added here (
            #  - Check, if crossing point is an end node of the exhaust air distribution system -> Then do nothing
            #  - Else, calculate pressure loss coefficient
            #       - If sum of height of both systems at crossing point < height of suspended ceiling => "Cable bridge"
            #       - Else rejuvenation and expansion of one or both

            """
            supply_graph_cross_section = self.dict_supply_graph_cross_section[key]
            colinear_edges, crossing_edges, crossing_points = self.find_collisions(supply_graph_cross_section, graph_geschoss)
            exhaust_crossing_edges = [edge[0] for edge in crossing_edges]
            supply_crossing_edges = [edge[1] for edge in crossing_edges]

            for edge in list(colinear_edges):
                collisions[edge] = {}
                collisions[edge]["pos"] = edge
            for i in range(len(supply_crossing_edges)-1):
                if (crossing_points[i] not in (supply_crossing_edges[i][0][:2], supply_crossing_edges[i][1][:2])) or \
                  (crossing_points[i] == supply_crossing_edges[i][0][:2] and graph_geschoss.degree[supply_crossing_edges[i][0][:2]] != 1) or \
                  (crossing_points[i] == supply_crossing_edges[i][1][:2] and graph_geschoss.degree[supply_crossing_edges[i][1][:2]] != 1):
                    collisions.append(supply_crossing_edges[i])
                    collisions[supply_crossing_edges[i]] = {}
                    collisions[supply_crossing_edges[i]]["pos"] = supply_crossing_edges[i]
            """



            schacht_knoten = [node for node in graph_geschoss.nodes()
                              if node[0] == position_schacht[0] and node[1] == position_rlt[1]][0]

            # Blattknoten identifizieren (Knoten mit Grad 1)
            blatt_knoten = [node for node in graph_geschoss.nodes()
                            if graph_geschoss.degree(node) == 1 and node != schacht_knoten]

            # Pfade vom Startknoten zu jedem Blattknoten berechnen
            pfade = [nx.shortest_path(graph_geschoss, source=schacht_knoten, target=blatt) for blatt in blatt_knoten]

            # Pfade nach ihrer Länge sortieren
            sortierte_pfade = sorted(pfade, key=len, reverse=True)

            x = 0

            for point in sortierte_pfade[0]:
                if point not in zwei_d_koodrinaten:
                    zwei_d_koodrinaten[point] = (x, y)
                x += 2
            x = -2
            y += 2

            pfad_zaehler = 0
            wieder_runter = 0

            for pfad in sortierte_pfade[1:]:
                i = 0
                rest_laenge_pfad = len(pfad)
                zaehler_neue_punkte = 0
                zaehler_punkte_vorhanden = 0
                for point in pfad:
                    if point not in zwei_d_koodrinaten:
                        zaehler_neue_punkte += 1
                        zwei_d_koodrinaten[point] = (x, y)

                        if pfad_zaehler == 0:
                            x += 2

                        if pfad_zaehler >= 1:
                            if i >= pfad_zaehler:
                                x += 2
                            else:
                                y += 2
                                i += 2

                    elif point in zwei_d_koodrinaten:
                        zaehler_punkte_vorhanden += 1
                        x += 2
                        rest_laenge_pfad -= 1

                y -= i
                x = -2
                pfad_zaehler += 1

            wieder_runter = max(wieder_runter, i) + 4
            y += wieder_runter

        """2D-Koordinaten erstellt"""

        # Erstelle mehrerer Junctions
        for junction in range(len(index_junction)):
            pp.create_junction(net,
                               name=str(name_junction[junction]),
                               index=index_junction[junction],
                               pn_bar=0,
                               tfluid_k=293.15,
                               geodata=zwei_d_koodrinaten[name_junction[junction]],
                               x=x_koordinaten[junction],
                               y=y_koordinaten[junction],
                               height_m=z_koordinaten[junction]
                               )

        # Definition der Parameter für die Pipe
        name_pipe = dataframe_distribution_network_exhaust_air["edge"].tolist()
        length_pipe = dataframe_distribution_network_exhaust_air["duct length"].tolist()
        from_junction = dataframe_distribution_network_exhaust_air["starting_node"].tolist()
        to_junction = dataframe_distribution_network_exhaust_air["target_node"].tolist()
        diameter_pipe = dataframe_distribution_network_exhaust_air["calculated diameter"].tolist()

        # Hinzufügen der Rohre zum Netz
        for index, pipe in enumerate(name_pipe):
            pp.create_pipe_from_parameters(net,
                                           from_junction=int(name_junction.index(from_junction[index])),
                                           to_junction=int(name_junction.index(to_junction[index])),
                                           nr_junctions=index,
                                           length_km=length_pipe[index].to(ureg.kilometer).magnitude,
                                           diameter_m=diameter_pipe[index].to(ureg.meter).magnitude,
                                           k_mm=0.15,
                                           name=str(name_pipe[index]),
                                           loss_coefficient=0
                                           )

        """Ab hier werden die Verlustbeiwerte der Rohre angepasst"""
        for index, pipe in enumerate(name_pipe):

            # Nachbarn des Startknotens
            neighbors = list(nx.all_neighbors(graph_leitungslaenge_abluft, from_junction[index]))

            """Bögen:"""
            if len(neighbors) == 2:  # Bögen finden
                eingehende_kante = list(graph_leitungslaenge_abluft.in_edges(from_junction[index]))[0]
                ausgehende_kante = list(graph_leitungslaenge_abluft.out_edges(from_junction[index]))[0]

                # Rechnerischer Durchmesser des Kanals
                rechnerischer_durchmesser = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == to_junction[index]),
                    'calculated diameter'
                ].iloc[0].to(ureg.meter)

                # Abmessung des Kanals
                abmessung_kanal = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == to_junction[index]),
                    'duct cross section'
                ].iloc[0]

                if not check_if_lines_are_aligned(eingehende_kante, ausgehende_kante):

                    zeta_bogen = None
                    if "Ø" in abmessung_kanal:
                        durchmesser = self.finde_abmessung(abmessung_kanal)
                        zeta_bogen = widerstandsbeiwert_bogen_rund(winkel=90,
                                                                   mittlerer_radius=0.75 * ureg.meter,
                                                                   durchmesser=durchmesser)
                        # self.logger.info(f"Zeta-Bogen rund: {zeta_bogen}")

                    elif "x" in abmessung_kanal:
                        breite = self.finde_abmessung(abmessung_kanal)[0].to(ureg.meter)
                        hoehe = self.finde_abmessung(abmessung_kanal)[1].to(ureg.meter)
                        zeta_bogen = widerstandsbeiwert_bogen_eckig(winkel=90,
                                                                    mittlerer_radius=0.75 * ureg.meter,
                                                                    hoehe=hoehe,
                                                                    breite=breite,
                                                                    rechnerischer_durchmesser=rechnerischer_durchmesser
                                                                    )
                        # self.logger.info(f"Zeta Bogen eckig: {zeta_bogen}")

                    # Ändern des loss_coefficient-Werts
                    net['pipe'].at[index, 'loss_coefficient'] += zeta_bogen

                    dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                      'target_node'] == to_junction[
                                                                      index], 'Zeta Bogen'] = zeta_bogen

            """Reduzierungen"""
            if len(neighbors) == 2:
                kanal = name_pipe[index]

                eingehende_kante = list(graph_leitungslaenge_abluft.in_edges(from_junction[index]))[0]
                ausgehende_kante = list(graph_leitungslaenge_abluft.out_edges(from_junction[index]))[0]

                """ Daten für Widerstandsbeiwerte"""
                # Durchmesser des Eingangs:
                d = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == eingehende_kante[0]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == eingehende_kante[1]),
                    'calculated diameter'
                ].iloc[0].to(ureg.meter)

                # Durchmesser des Durchgangs:
                d_D = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == ausgehende_kante[0]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == ausgehende_kante[1]),
                    'calculated diameter'
                ].iloc[0].to(ureg.meter)

                if d > d_D:
                    zeta_reduzierung = widerstandsbeiwert_querschnittsverengung_stetig(d, d_D)

                    # self.logger.info(f"Zeta Reduzierung: {zeta_reduzierung}")

                    net['pipe'].at[index, 'loss_coefficient'] += zeta_reduzierung

                    dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                      'target_node'] == to_junction[
                                                                      index], 'Zeta Reduzierung'] = zeta_reduzierung

                elif d_D > d:
                    zeta_erweiterung = widerstandsbeiwert_querschnittserweiterung_stetig(d, d_D)

                    # self.logger.info(f"Zeta Erweiterung: {zeta_erweiterung}")

                    net['pipe'].at[index, 'loss_coefficient'] += zeta_erweiterung

                    dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                      'target_node'] == to_junction[
                                                                      index], 'Zeta Erweiterung'] = zeta_erweiterung

            """T-Stücke"""
            if len(neighbors) == 3:  # T-Stücke finden
                kanal = name_pipe[index]

                # Rechnerischer Durchmesser des Kanals
                rechnerischer_durchmesser_kanal = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == to_junction[index]),
                    'calculated diameter'
                ].iloc[0].to(ureg.meter)

                # Abmessung des Kanals
                abmessung_kanal = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == to_junction[index]),
                    'duct cross section'
                ].iloc[0]

                luftmenge_kanal = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == to_junction[index]),
                    'Air volume'
                ].iloc[0]

                # Liste der eingehenden Kanten
                eingehende_kanten = list(graph_leitungslaenge_abluft.in_edges(from_junction[index]))

                # Aufteilen in eingehende Kante 1
                eingehende_kante_1 = eingehende_kanten[0]
                # Aufteilen in eingenden Kante 2
                eingehende_kante_2 = eingehende_kanten[1]

                # Lage überprüfen, sonst tauschen
                if check_if_lines_are_aligned(eingehende_kante_2, kanal):
                    eingehende_kante_1 = eingehende_kanten[1]
                    eingehende_kante_2 = eingehende_kanten[0]

                # Rechnerischer Durchmesser eingehende Kante 1
                rechnerischer_durchmesser_eingehende_kante_1 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == eingehende_kante_1[0]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == eingehende_kante_1[1]),
                    'calculated diameter'
                ].iloc[0].to(ureg.meter)

                # Abmessung des Kanals eingehende Kante 1
                abmessung_kanal_eingehende_kante_1 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == eingehende_kante_1[0]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == eingehende_kante_1[1]),
                    'duct cross section'
                ].iloc[0]

                luftmenge_eingehende_kante_1 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == eingehende_kante_1[0]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == eingehende_kante_1[1]),
                    'Air volume'
                ].iloc[0]

                # Rechnerischer Durchmesser eingehende Kante 2
                rechnerischer_durchmesser_eingehende_kante_2 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == eingehende_kante_2[0]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == eingehende_kante_2[1]),
                    'calculated diameter'
                ].iloc[0].to(ureg.meter)

                # Abmessung des Kanals eingehende Kante 1
                abmessung_kanal_eingehende_kante_2 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == eingehende_kante_2[0]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == eingehende_kante_2[1]),
                    'duct cross section'
                ].iloc[0]

                luftmenge_eingehende_kante_2 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['starting_node'] == eingehende_kante_2[0]) &
                    (dataframe_distribution_network_exhaust_air['target_node'] == eingehende_kante_2[1]),
                    'Air volume'
                ].iloc[0]

                # 3D Darstellung des T-Stücks
                # darstellung_t_stueck(eingehende_kante_1, eingehende_kante_2, kanal)

                """ Daten für Widerstandsbeiwerte"""
                if check_if_lines_are_aligned(eingehende_kante_1, eingehende_kante_2) == True:
                    # Eingehende Kante 1 --→ ←-- Eingehende Kante 2
                    #                       ↓
                    #                     Kanal

                    if "Ø" in abmessung_kanal:
                        if rechnerischer_durchmesser_eingehende_kante_1 > rechnerischer_durchmesser_eingehende_kante_2:
                            zeta_eingehende_kante_1 = wiederstandsbeiwert_T_endstueck_stromvereinigung_rund(
                                d_A=rechnerischer_durchmesser_eingehende_kante_1,
                                v_A=luftmenge_eingehende_kante_1,
                                d=rechnerischer_durchmesser_kanal,
                                v=luftmenge_kanal)

                            net['pipe'].at[
                                name_pipe.index(eingehende_kante_1), 'loss_coefficient'] += zeta_eingehende_kante_1
                            dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                              'edge'] == eingehende_kante_1, 'Zeta T-Stück'] = zeta_eingehende_kante_1

                            zeta_eingehende_kante_2 = wiederstandsbeiwert_T_endstueck_stromvereinigung_rund(
                                d_A=rechnerischer_durchmesser_eingehende_kante_2,
                                v_A=luftmenge_eingehende_kante_2,
                                d=rechnerischer_durchmesser_kanal,
                                v=luftmenge_kanal) + widerstandsbeiwert_querschnittserweiterung_stetig(
                                rechnerischer_durchmesser_eingehende_kante_2,
                                rechnerischer_durchmesser_eingehende_kante_1)

                            net['pipe'].at[
                                name_pipe.index(eingehende_kante_2), 'loss_coefficient'] += zeta_eingehende_kante_2
                            dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                              'edge'] == eingehende_kante_2, 'Zeta T-Stück'] = zeta_eingehende_kante_2

                        elif rechnerischer_durchmesser_eingehende_kante_2 > rechnerischer_durchmesser_eingehende_kante_1:
                            zeta_eingehende_kante_2 = wiederstandsbeiwert_T_endstueck_stromvereinigung_rund(
                                d_A=rechnerischer_durchmesser_eingehende_kante_2,
                                v_A=luftmenge_eingehende_kante_2,
                                d=rechnerischer_durchmesser_kanal,
                                v=luftmenge_kanal)

                            net['pipe'].at[
                                name_pipe.index(eingehende_kante_2), 'loss_coefficient'] += zeta_eingehende_kante_2
                            dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                              'edge'] == eingehende_kante_2, 'Zeta T-Stück'] = zeta_eingehende_kante_2

                            zeta_eingehende_kante_1 = wiederstandsbeiwert_T_endstueck_stromvereinigung_rund(
                                d_A=rechnerischer_durchmesser_eingehende_kante_1,
                                v_A=luftmenge_eingehende_kante_1,
                                d=rechnerischer_durchmesser_kanal,
                                v=luftmenge_kanal) + widerstandsbeiwert_querschnittserweiterung_stetig(
                                rechnerischer_durchmesser_eingehende_kante_1,
                                rechnerischer_durchmesser_eingehende_kante_2)

                            net['pipe'].at[
                                name_pipe.index(eingehende_kante_1), 'loss_coefficient'] += zeta_eingehende_kante_1
                            dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                              'edge'] == eingehende_kante_1, 'Zeta T-Stück'] = zeta_eingehende_kante_1
                    elif "x" in abmessung_kanal:
                        zeta_eingehende_kante_1 = wiederstandsbeiwert_T_endstueck_stromvereinigung_eckig()

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_1), 'loss_coefficient'] += zeta_eingehende_kante_1
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'edge'] == eingehende_kante_1, 'Zeta T-Stück'] = zeta_eingehende_kante_1

                        zeta_eingehende_kante_2 = wiederstandsbeiwert_T_endstueck_stromvereinigung_eckig()

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_2), 'loss_coefficient'] += zeta_eingehende_kante_2
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'edge'] == eingehende_kante_2, 'Zeta T-Stück'] = zeta_eingehende_kante_2

                if check_if_lines_are_aligned(eingehende_kante_1, kanal) == True:
                    # Eingehende Kante 1 --→ --→ Kanal
                    #                       ↑
                    #               Eingehende Kante 2
                    if "Ø" in abmessung_kanal:
                        zeta_eingehende_kante_1 = wiederstandsbeiwert_T_stueck_stromvereinigung_rund(
                            d=rechnerischer_durchmesser_kanal,
                            v=luftmenge_kanal,
                            d_D=rechnerischer_durchmesser_eingehende_kante_1,
                            v_D=luftmenge_eingehende_kante_1,
                            d_A=rechnerischer_durchmesser_eingehende_kante_2,
                            v_A=luftmenge_eingehende_kante_2,
                            richtung="Durchgangsrichtung")

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_1), 'loss_coefficient'] += zeta_eingehende_kante_1
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'edge'] == eingehende_kante_1, 'Zeta T-Stück'] = zeta_eingehende_kante_1

                        zeta_eingehende_kante_2 = wiederstandsbeiwert_T_stueck_stromvereinigung_rund(
                            d=rechnerischer_durchmesser_kanal,
                            v=luftmenge_kanal,
                            d_D=rechnerischer_durchmesser_eingehende_kante_1,
                            v_D=luftmenge_eingehende_kante_1,
                            d_A=rechnerischer_durchmesser_eingehende_kante_2,
                            v_A=luftmenge_eingehende_kante_2,
                            richtung="zuströmende Richtung")

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_2), 'loss_coefficient'] += zeta_eingehende_kante_2
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'edge'] == eingehende_kante_2, 'Zeta T-Stück'] = zeta_eingehende_kante_2

                    if "x" in abmessung_kanal:
                        zeta_eingehende_kante_1 = wiederstandsbeiwert_T_stueck_stromvereinigung_eckig(
                            d=rechnerischer_durchmesser_kanal,
                            v=luftmenge_kanal,
                            d_D=rechnerischer_durchmesser_eingehende_kante_1,
                            v_D=luftmenge_eingehende_kante_1,
                            d_A=rechnerischer_durchmesser_eingehende_kante_2,
                            v_A=luftmenge_eingehende_kante_2,
                            richtung="Durchgangsrichtung")

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_1), 'loss_coefficient'] += zeta_eingehende_kante_1
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'edge'] == eingehende_kante_1, 'Zeta T-Stück'] = zeta_eingehende_kante_1

                        zeta_eingehende_kante_2 = wiederstandsbeiwert_T_stueck_stromvereinigung_eckig(
                            d=rechnerischer_durchmesser_kanal,
                            v=luftmenge_kanal,
                            d_D=rechnerischer_durchmesser_eingehende_kante_1,
                            v_D=luftmenge_eingehende_kante_1,
                            d_A=rechnerischer_durchmesser_eingehende_kante_2,
                            v_A=luftmenge_eingehende_kante_2,
                            richtung="zuströmende Richtung")

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_2), 'loss_coefficient'] += zeta_eingehende_kante_2
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'edge'] == eingehende_kante_2, 'Zeta T-Stück'] = zeta_eingehende_kante_2

        # Luftmengen aus Graphen
        luftmengen = nx.get_node_attributes(graph_air_volume_flow, 'weight')

        # Index der RLT-Anlage finden
        index_rlt = name_junction.index(tuple(position_rlt))
        luftmenge_rlt = luftmengen[position_rlt]
        mdot_kg_per_s_rlt = (luftmenge_rlt * dichte).to(ureg.kilogram / ureg.second)

        # Externes Grid erstellen, da dann die Visualisierung besser ist
        pp.create_ext_grid(net, junction=index_rlt, p_bar=0, t_k=293.15, name="RLT-Anlage")

        # Hinzufügen der RLT-Anlage zum Netz
        pp.create_source(net,
                         mdot_kg_per_s=-mdot_kg_per_s_rlt.magnitude,
                         junction=index_rlt,
                         p_bar=0,
                         t_k=293.15,
                         name="RLT-Anlage")

        liste_lueftungsauslaesse = list()

        # Hinzugen der Lüftungsauslässe
        for index, element in enumerate(luftmengen):
            if element == tuple(position_rlt):
                continue  # Überspringt den aktuellen Durchlauf
            if element[0] == position_schacht[0] and element[1] == position_schacht[1]:
                continue
            if luftmengen[element] == 0:
                continue
            pp.create_sink(net,
                           junction=name_junction.index(element),
                           mdot_kg_per_s=(-luftmengen[element] * dichte).to(ureg.kilogram / ureg.second).magnitude,
                           )
            liste_lueftungsauslaesse.append(name_junction.index(element))

        # Die eigentliche Berechnung wird mit dem pipeflow-Kommando gestartet:
        pp.pipeflow(net)

        # Bestimmung des Druckverlustes
        maxr_druckverlust = abs(net.res_junction["p_bar"].min())
        differenz = net.res_junction["p_bar"].min()

        # Identifizierung der Quelle durch ihren Namen oder Index
        source_index = net['source'].index[net['source']['name'] == "RLT-Anlage"][0]
        # Identifizieren des externen Grids durch seinen Namen oder Index
        ext_grid_index = net['ext_grid'].index[net['ext_grid']['name'] == "RLT-Anlage"][0]

        # Ändern des Druckwerts
        net['source'].at[source_index, 'p_bar'] = maxr_druckverlust
        # Ändern des Druckwerts
        net['ext_grid'].at[ext_grid_index, 'p_bar'] = maxr_druckverlust

        # Erneute Berechnung
        pp.pipeflow(net)

        maxr_druckverlust = net.res_junction["p_bar"].min()

        # Identifizierung der Quelle durch ihren Namen oder Index
        source_index = net['source'].index[net['source']['name'] == "RLT-Anlage"][0]
        # Identifizieren des externen Grids durch seinen Namen oder Index
        ext_grid_index = net['ext_grid'].index[net['ext_grid']['name'] == "RLT-Anlage"][0]

        maxr_druckverlust -= 0.00100  # 30 Pa für Lüftungseinlass und 50 Pa für Schalldämpfer + 20 Reserve

        # Ändern des Druckwerts
        net['source'].at[source_index, 'p_bar'] -= maxr_druckverlust
        # Ändern des Druckwerts
        net['ext_grid'].at[ext_grid_index, 'p_bar'] -= maxr_druckverlust

        pp.pipeflow(net)

        # Ergebnisse werden in Tabellen mit dem Präfix res_... gespeichert. Auch diese Tabellen sind nach der Berechnung im
        # net-Container abgelegt.
        dataframe_pipes = pd.concat([net.pipe, net.res_pipe], axis=1)
        dataframe_junctions = pd.concat([net.junction, net.res_junction], axis=1)

        for kanal in dataframe_distribution_network_exhaust_air["edge"]:
            p_from_pa = int(dataframe_pipes.loc[dataframe_pipes["name"] == str(kanal), "p_from_bar"].iloc[0] * 100000)
            p_to_pa = int(dataframe_pipes.loc[dataframe_pipes["name"] == str(kanal), "p_to_bar"].iloc[0] * 100000)

            dataframe_distribution_network_exhaust_air.loc[
                dataframe_distribution_network_exhaust_air["edge"] == kanal, "p_from_pa"] = p_from_pa
            dataframe_distribution_network_exhaust_air.loc[
                dataframe_distribution_network_exhaust_air["edge"] == kanal, "p_to_pa"] = p_to_pa


        # Export
        # dataframe_distribution_network_exhaust_air.to_excel(
        #     self.paths.export / 'ventilation system' / 'exhaust air' / 'dataframe_exhaust_air.xlsx', index=False)

        # Pfad für Speichern
        pipes_excel_pfad = self.paths.export / 'ventilation system' / 'exhaust air' / "pressure_loss.xlsx"

        # dataframe_pipes.to_excel(pipes_excel_pfad)

        with pd.ExcelWriter(pipes_excel_pfad) as writer:
            dataframe_pipes.to_excel(writer, sheet_name="Pipes")
            dataframe_junctions.to_excel(writer, sheet_name="Junctions")

        if self.export_graphs:
            # # create additional junction collections for junctions with sink connections and junctions with valve connections
            junction_sink_collection = plot.create_junction_collection(net,
                                                                       junctions=liste_lueftungsauslaesse,
                                                                       patch_type="circle",
                                                                       size=0.1,
                                                                       color="blue")

            junction_source_collection = plot.create_junction_collection(net,
                                                                         junctions=[index_rlt],
                                                                         patch_type="circle",
                                                                         size=0.6,
                                                                         color="orange")

            # create additional pipe collection
            pipe_collection = plot.create_pipe_collection(net,
                                                          linewidths=2.,
                                                          color="grey")

            collections = [junction_sink_collection, junction_source_collection, pipe_collection]

            # Zeichnen Sie die Sammlungen
            fig, ax = plt.subplots(num=f"pressure loss", figsize=(20, 15))
            plot.draw_collections(collections=collections, ax=ax, axes_visible=(True, True))

            # Fügt die Text-Annotationen für die Drücke hinzu
            for idx, junction in enumerate(net.res_junction.index):
                pressure = net.res_junction.iloc[idx]['p_bar']  # Druck am Knoten
                # Koordinaten des Knotens
                if junction in net.junction_geodata.index:
                    coords = net.junction_geodata.loc[junction, ['x', 'y']]
                    ax.text(coords['x'], coords['y'], f'{pressure * 100000:.0f} [Pa]', fontsize=8,
                            horizontalalignment='left', verticalalignment='top', rotation=-45)

            # Setze den Pfad für den neuen Ordner
            folder_path = Path(self.paths.export / 'ventilation system' / 'exhaust air')

            # Erstelle den Ordner
            folder_path.mkdir(parents=True, exist_ok=True)

            # Speichern des Graphens
            gesamte_bezeichnung = "pressure_loss" + ".png"
            pfad_plus_name = self.paths.export / 'ventilation system' / 'exhaust air' / gesamte_bezeichnung
            plt.savefig(pfad_plus_name)

            # plt.show()

            plt.close()

        return maxr_druckverlust * 100000, dataframe_distribution_network_exhaust_air

    #
    def blechstaerke(self, pressure_loss, abmessung):
        """
        Berechnet die Blechstärke in Abhängigkeit vom Kanal
        :param pressure_loss: Durckverlust des Systems
        :param abmessung: Abmessung des Kanals (400x300 oder Ø60)
        :return: Blechstärke
        """

        if "Ø" in abmessung:
            durchmesser = self.finde_abmessung(abmessung).to(ureg.meter)

            if durchmesser <= 0.2 * ureg.meter:
                blechstaerke = (0.5 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.2 * ureg.meter < durchmesser <= 0.4 * ureg.meter:
                blechstaerke = (0.6 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.4 * ureg.meter < durchmesser <= 0.5 * ureg.meter:
                blechstaerke = (0.7 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.5 * ureg.meter < durchmesser <= 0.63 * ureg.meter:
                blechstaerke = (0.9 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.63 * ureg.meter < durchmesser <= 1.25 * ureg.meter:
                blechstaerke = (1.25 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782


        elif "x" in abmessung:
            breite, hoehe = self.finde_abmessung(abmessung)
            laengste_kante = max(breite.to(ureg.meter), hoehe.to(ureg.meter))

            if pressure_loss <= 1000:
                if laengste_kante <= 0.500 * ureg.meter:
                    blechstaerke = (0.6 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 0.500 * ureg.meter < laengste_kante <= 1.000 * ureg.meter:
                    blechstaerke = (0.8 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < laengste_kante <= 2.000 * ureg.meter:
                    blechstaerke = (1.0 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

            elif 1000 < pressure_loss <= 2000:
                if laengste_kante <= 0.500 * ureg.meter:
                    blechstaerke = (0.7 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 0.500 * ureg.meter < laengste_kante <= 1.000 * ureg.meter:
                    blechstaerke = (0.9 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < laengste_kante <= 2.000 * ureg.meter:
                    blechstaerke = (1.1 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

            elif 2000 < pressure_loss <= 3000:
                if laengste_kante <= 1.000 * ureg.meter:
                    blechstaerke = (0.95 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < laengste_kante <= 2.000 * ureg.meter:
                    blechstaerke = (1.15 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

        return blechstaerke

    def connect_rooms(self, cross_section_type, suspended_ceiling_space, dataframe_rooms):

        # Ermittlung des Kanalquerschnittes
        dataframe_rooms["duct cross section"] = \
            dataframe_rooms.apply(lambda row: self.dimensions_ventilation_duct(cross_section_type,
                                                                     self.necessary_cross_section(
                                                                         row["volume flow"]),
                                                                     suspended_ceiling_space),
                                  axis=1
                                  )

        # Ermittung der Abmessungen
        dataframe_rooms['duct length'] = 2*ureg.meter
        dataframe_rooms['diameter'] = None
        dataframe_rooms['width'] = None
        dataframe_rooms['height'] = None

        for index, kanalquerschnitt in enumerate(dataframe_rooms["duct cross section"]):
            if "Ø" in kanalquerschnitt:
                dataframe_rooms.at[index, 'diameter'] = self.finde_abmessung(kanalquerschnitt)

            elif "x" in kanalquerschnitt:
                dataframe_rooms.at[index, 'width'] = self.finde_abmessung(kanalquerschnitt)[0]
                dataframe_rooms.at[index, 'height'] = self.finde_abmessung(kanalquerschnitt)[1]

        dataframe_rooms["Surface area"] = dataframe_rooms.apply(
            lambda row: self.coat_area_ventilation_duct(
                cross_section_type,
                self.necessary_cross_section(row["volume flow"]),
                suspended_ceiling_space
            ) * row["duct length"], axis=1)

        dataframe_rooms["calculated diameter"] = dataframe_rooms.apply(
            lambda row: round(self.calculated_diameter(cross_section_type,
                                                       self.necessary_cross_section(row["volume flow"]),
                                                       suspended_ceiling_space),
                              2
                              ), axis=1)

        # Ermittlung der Blechstärke
        dataframe_rooms["sheet thickness"] = dataframe_rooms.apply(
            lambda row: self.blechstaerke(70, row["duct cross section"]), axis=1)

        # Überprüfung, ob ein Schalldämpfer erfordlerlich ist
        liste_raeume_schalldaempfer = ["Bed room",
                                       "Class room (school), group room (kindergarden)",
                                       "Classroom",
                                       "Examination- or treatment room",
                                       "Exhibition room and museum conservational demands",
                                       "Exhibition, congress",
                                       "Foyer (theater and event venues)",
                                       "Hotel room",
                                       "Laboratory",
                                       "Lecture hall, auditorium",
                                       "Library - magazine and depot",
                                       "Library - open stacks",
                                       "Library - reading room",
                                       "Living",
                                       "Main Hall, Reception",
                                       "Medical and therapeutic practices",
                                       "Meeting, Conference, seminar",
                                       "MultiUseComputerRoom",
                                       "Restaurant",
                                       "Sauna area",
                                       "Spectator area (theater and event venues)",
                                       "Stage (theater and event venues)",
                                       "Traffic area",
                                       "WC and sanitary rooms in non-residential buildings",
                                       "Group Office (between 2 and 6 employees)",
                                       "Open-plan Office (7 or more employees)",
                                       "Single office",
                                       "office_function"
                                       ]
        dataframe_rooms['silencer'] = dataframe_rooms['room type'].apply(
            lambda x: 1 if x in liste_raeume_schalldaempfer else 0)

        # Volumenstromregler
        dataframe_rooms["Volume_flow_controller"] = 1

        # Berechnung des Blechvolumens
        dataframe_rooms["Sheet volume"] = dataframe_rooms["sheet thickness"] * dataframe_rooms[
            "Surface area"]

        list_dataframe_rooms_blechgewicht = [v * (7850 * ureg.kilogram / ureg.meter ** 3) for v in
                                             dataframe_rooms["Sheet volume"]]
        # Dichte Stahl 7850 kg/m³

        # Berechnung des Blechgewichts
        dataframe_rooms["Blechgewicht"] = list_dataframe_rooms_blechgewicht

        return dataframe_rooms

    def calculate_material_quantities(self,
                                      pressure_loss,
                                      dataframe_rooms,
                                      dataframe_distribution_network_exhaust_air):

        def gwp(uuid: str):
            """
            Gibt das globale Erwärmungspotential nach Ökobaudat in Kathegorien zurücvk
            :param uuid: UUID nach Ökobaudat
            :return: Globales Erwärmungspotential nach ÖKOBAUDAT, ReferenceUnit
            """
            # A1-A3: Herstellung
            # C2: Transport
            # C3: Abfallbehandlung
            # D: Recxclingpotential

            OKOBAU_URL = "https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/c391de0f-2cfd-47ea-8883-c661d294e2ba"

            """Fetches the data of a specific EPD given its UUID"""
            response = requests.get(f"{OKOBAU_URL}/processes/{uuid}?format=json&view=extended")

            response.raise_for_status()
            data = response.json()

            # Extrahieren der Werte für die Module A1-A3, C2, C3, D
            results = {}
            # Loop durch alle 'LCIAResults' Einträge
            for entry in data['LCIAResults']['LCIAResult']:
                # Initialisieren eines leeren Dictionaries für jeden Eintrag
                results[entry['referenceToLCIAMethodDataSet']['shortDescription'][0]['value']] = {}
                # Loop durch alle 'other' Elemente
                for sub_entry in entry['other']['anies']:
                    # Prüfen, ob 'module' als Schlüssel in 'sub_entry' vorhanden ist
                    if 'module' in sub_entry:
                        # Hinzufügen des Wertes zum Dictionary
                        results[entry['referenceToLCIAMethodDataSet']['shortDescription'][0]['value']][
                            sub_entry['module']] = \
                            sub_entry['value']

            wp_reference_unit = data['exchanges']['exchange'][0]['flowProperties'][1]['referenceUnit']

            # Rückgabe der Ergebnisse
            return results['Global Warming Potential - total (GWP-total)'], wp_reference_unit

        """
        Berechnung des CO2 des Lüftungsverteilernetztes des Blechs der Zuluft des Verteilernetzes
        """
        # Ermittlung der Blechstärke
        dataframe_distribution_network_exhaust_air["sheet thickness"] = dataframe_distribution_network_exhaust_air.apply(
            lambda row: self.blechstaerke(pressure_loss, row["duct cross section"]), axis=1)

        # Berechnung des Blechvolumens
        dataframe_distribution_network_exhaust_air["Sheet volume"] = dataframe_distribution_network_exhaust_air[
                                                                        "sheet thickness"] * \
                                                                    dataframe_distribution_network_exhaust_air[
                                                                        "Surface area"]

        list_dataframe_distribution_network_exhaust_air_blechgewicht = [v * (7850 * ureg.kilogram / ureg.meter ** 3) for
                                                                       v
                                                                       in
                                                                       dataframe_distribution_network_exhaust_air[
                                                                           "Sheet volume"]]
        # Dichte Stahl 7850 kg/m³

        # Berechnung des Blechgewichts
        dataframe_distribution_network_exhaust_air[
            "Sheet weight"] = [x.magnitude for x in list_dataframe_distribution_network_exhaust_air_blechgewicht]

        # # Ermittlung des CO2-Kanal
        # dataframe_distribution_network_exhaust_air["CO2-Kanal"] = dataframe_distribution_network_exhaust_air[
        #                                                              "Blechgewicht"] * (
        #                                                                  float(
        #                                                                      gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[
        #                                                                          0]["A1-A3"]) + float(
        #                                                              gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0][
        #                                                                  "C2"]))

        def cross_sectional_area_duct_insulation(row):
            """
            Berechnet die Querschnittsfläche der Dämmung
            """
            cross_sectional_area = 0
            if 'Ø' in row['duct cross section']:
                try:
                    diameter = ureg(row['diameter'])
                except AttributeError:
                    diameter = row['diameter']
                cross_sectional_area = math.pi * ((diameter + 0.04 * ureg.meter) ** 2) / 4 - math.pi * (
                        diameter ** 2) / 4  # 20mm Dämmung des Lüftungskanals nach anerkannten
                # Regeln der Technik nach Missel Seite 42

            elif 'x' in row['duct cross section']:
                try:
                    width = ureg(row['width'])
                    height = ureg(row['height'])
                except AttributeError:
                    width = row['width']
                    height = row['height']
                cross_sectional_area = ((width + 0.04 * ureg.meter) * (height + 0.04 * ureg.meter)) - (
                        width * height)  # 20mm Dämmung des Lüftungskanals nach aneredges Regeln der Technik nach Missel Seite 42

            return cross_sectional_area.to(ureg.meter ** 2)

        # Calculation of the insulation
        dataframe_distribution_network_exhaust_air[
            'Cross-sectional area of insulation'] = dataframe_distribution_network_exhaust_air.apply(
            cross_sectional_area_duct_insulation, axis=1)

        list_dataframe_isolation_volume_distribution_network_exhaust_air = list(dataframe_distribution_network_exhaust_air[
                                                                            'Cross-sectional area of insulation'] * \
                                                                        dataframe_distribution_network_exhaust_air[
                                                                            'duct length'])

        dataframe_distribution_network_exhaust_air['Isolation volume'] = [x.magnitude for x in list_dataframe_isolation_volume_distribution_network_exhaust_air]
        # gwp_isulation = (
        #             121.8 * ureg.kilogram / ureg.meter ** 3 + 1.96 * ureg.kilogram / ureg.meter ** 3 + 10.21 * ureg.kilogram / ureg.meter ** 3)
        # https://www.oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?lang=de&uuid=eca9691f-06d7-48a7-94a9-ea808e2d67e8

        # list_dataframe_distribution_network_exhaust_air_CO2_duct_isolation = [v * gwp_isulation for v in
        #                                                                     dataframe_distribution_network_exhaust_air[
        #                                                                         "Isolation volume"]]
        #
        # dataframe_distribution_network_exhaust_air[
        #     "CO2 Duct Isolation"] = list_dataframe_distribution_network_exhaust_air_CO2_duct_isolation

        # Export to Excel
        export_path = Path(self.paths.export, 'ventilation system', 'exhaust air')
        dataframe_distribution_network_exhaust_air.to_excel(export_path / 'dataframe_exhaust_air.xlsx', index=False)

        """
        Berechnung des CO2 für die room_connection
        """
        # Ermittlung des CO2-Kanal
        # dataframe_rooms["CO2-Kanal"] = dataframe_rooms["Sheet weight"] * (
        #             float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0][
        #                       "A1-A3"]) + float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"]))

        # Vordefinierte Daten für Trox RN Volume_flow_controller
        # https://cdn.trox.de/4ab7c57caaf55be6/3450dc5eb9d7/TVR_PD_2022_08_03_DE_de.pdf
        trox_tvr_diameter_gewicht = {
            'diameter': [100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter, 200 * ureg.millimeter,
                            250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter],
            'Gewicht': [3.3 * ureg.kilogram, 3.6 * ureg.kilogram, 4.2 * ureg.kilogram, 5.1 * ureg.kilogram,
                        6.1 * ureg.kilogram, 7.2 * ureg.kilogram, 9.4 * ureg.kilogram]
        }
        df_trox_tvr_diameter_gewicht = pd.DataFrame(trox_tvr_diameter_gewicht)

        # Funktion, um das nächstgrößere Gewicht zu finden
        def gewicht_runde_volumenstromregler(row):
            if row['Volume_flow_controller'] == 1 and 'Ø' in row['duct cross section']:
                calculated_diameter = row['calculated diameter']
                next_diameter = df_trox_tvr_diameter_gewicht[
                    df_trox_tvr_diameter_gewicht['diameter'] >= calculated_diameter]['diameter'].min()
                return \
                    df_trox_tvr_diameter_gewicht[df_trox_tvr_diameter_gewicht['diameter'] == next_diameter][
                        'Gewicht'].values[0]
            return None

        # Tabelle mit width, Höhe und Gewicht für Trox TVJ Volume_flow_controller
        # https://cdn.trox.de/502e3cb43dff27e2/af9a822951e1/TVJ_PD_2021_07_19_DE_de.pdf
        df_trox_tvj_diameter_gewicht = pd.DataFrame({
            'width': [200 * ureg.millimeter, 300 * ureg.millimeter, 400 * ureg.millimeter, 500 * ureg.millimeter,
                       600 * ureg.millimeter,

                       200 * ureg.millimeter, 300 * ureg.millimeter, 400 * ureg.millimeter, 500 * ureg.millimeter,
                       600 * ureg.millimeter, 700 * ureg.millimeter, 800 * ureg.millimeter,

                       300 * ureg.millimeter, 400 * ureg.millimeter, 500 * ureg.millimeter, 600 * ureg.millimeter,
                       700 * ureg.millimeter, 800 * ureg.millimeter, 900 * ureg.millimeter, 1000 * ureg.millimeter,

                       400 * ureg.millimeter, 500 * ureg.millimeter, 600 * ureg.millimeter, 700 * ureg.millimeter,
                       800 * ureg.millimeter, 900 * ureg.millimeter, 1000 * ureg.millimeter
                       ],

            'height': [100 * ureg.millimeter, 100 * ureg.millimeter, 100 * ureg.millimeter, 100 * ureg.millimeter,
                     100 * ureg.millimeter,

                     200 * ureg.millimeter, 200 * ureg.millimeter, 200 * ureg.millimeter, 200 * ureg.millimeter,
                     200 * ureg.millimeter, 200 * ureg.millimeter, 200 * ureg.millimeter,

                     300 * ureg.millimeter, 300 * ureg.millimeter, 300 * ureg.millimeter, 300 * ureg.millimeter,
                     300 * ureg.millimeter, 300 * ureg.millimeter, 300 * ureg.millimeter, 300 * ureg.millimeter,

                     400 * ureg.millimeter, 400 * ureg.millimeter, 400 * ureg.millimeter, 400 * ureg.millimeter,
                     400 * ureg.millimeter, 400 * ureg.millimeter, 400 * ureg.millimeter
                     ],

            'Gewicht': [6 * ureg.kilogram, 7 * ureg.kilogram, 8 * ureg.kilogram, 9 * ureg.kilogram, 10 * ureg.kilogram,
                        9 * ureg.kilogram, 10 * ureg.kilogram, 11 * ureg.kilogram, 12 * ureg.kilogram,
                        13 * ureg.kilogram, 14 * ureg.kilogram, 15 * ureg.kilogram,
                        10 * ureg.kilogram, 11 * ureg.kilogram, 12 * ureg.kilogram, 13 * ureg.kilogram,
                        15 * ureg.kilogram, 16 * ureg.kilogram, 18 * ureg.kilogram, 19 * ureg.kilogram,
                        14 * ureg.kilogram, 15 * ureg.kilogram, 16 * ureg.kilogram, 17 * ureg.kilogram,
                        18 * ureg.kilogram, 21 * ureg.kilogram, 20 * ureg.kilogram]
        })

        # Funktion, um das entsprechende oder nächstgrößere Gewicht zu finden
        def gewicht_angulare_volumenstromregler(row):
            if row['Volume_flow_controller'] == 1 and 'x' in row['duct cross section']:
                width, height = row['width'], row['height']
                passende_zeilen = df_trox_tvj_diameter_gewicht[
                    (df_trox_tvj_diameter_gewicht['width'] >= width) & (
                            df_trox_tvj_diameter_gewicht['height'] >= height)]
                if not passende_zeilen.empty:
                    return passende_zeilen.sort_values(by=['width', 'height', 'Gewicht']).iloc[0]['Gewicht']
            return None

        # Kombinierte Funktion, die beide Funktionen ausführt
        def gewicht_volumenstromregler(row):
            gewicht_rn = gewicht_runde_volumenstromregler(row)
            if gewicht_rn is not None:
                return gewicht_rn
            return gewicht_angulare_volumenstromregler(row)

        # Anwenden der Funktion auf jede Zeile
        dataframe_rooms['Gewicht Volume_flow_controller'] = dataframe_rooms.apply(gewicht_volumenstromregler, axis=1)

        # dataframe_rooms["CO2-Volume_flow_controller"] = dataframe_rooms['Gewicht Volume_flow_controller'] * (
        #         19.08 + 0.01129 + 0.647) * 0.348432
        # Nach Ökobaudat https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=29e922f6-d872-4a67-b579-38bb8cd82abf&version=00.02.000&stock=OBD_2023_I&lang=de

        # CO2 für Schallfämpfer
        # Tabelle Daten für Berechnung nach Trox CA
        # https://cdn.trox.de/97af1ba558b3669e/e3aa6ed495df/CA_PD_2023_04_26_DE_de.pdf
        diameter_tabelle = pd.DataFrame({
            'diameter': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter,
                            200 * ureg.millimeter, 250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter,
                            450 * ureg.millimeter, 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                            710 * ureg.millimeter, 800 * ureg.millimeter],
            'Innendiameter': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter,
                                 160 * ureg.millimeter, 200 * ureg.millimeter, 250 * ureg.millimeter,
                                 315 * ureg.millimeter, 400 * ureg.millimeter, 450 * ureg.millimeter,
                                 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                                 710 * ureg.millimeter, 800 * ureg.millimeter],
            'Aussendiameter': [184 * ureg.millimeter, 204 * ureg.millimeter, 228 * ureg.millimeter,
                                  254 * ureg.millimeter, 304 * ureg.millimeter, 354 * ureg.millimeter,
                                  405 * ureg.millimeter, 505 * ureg.millimeter, 636 * ureg.millimeter,
                                  716 * ureg.millimeter, 806 * ureg.millimeter, 806 * ureg.millimeter,
                                  908 * ureg.millimeter, 1008 * ureg.millimeter]
        })

        # Funktion zur Berechnung der Fläche des Kreisrings
        def volumen_daemmung_schalldaempfer(row):
            calculated_diameter = row['calculated diameter']
            passende_zeilen = diameter_tabelle[diameter_tabelle['diameter'] >= calculated_diameter]
            if not passende_zeilen.empty:
                naechster_diameter = passende_zeilen.iloc[0]
                innen = naechster_diameter['Innendiameter']
                aussen = naechster_diameter['Aussendiameter']
                volumen = math.pi * (aussen ** 2 - innen ** 2) / 4 * 0.88 * ureg.meter  # Für einen Meter Länge des
                # Schalldämpfers, entspricht nach Datenblatt einer Länge des Dämmkerns von 0.88m,
                return volumen.to(ureg.meter ** 3)
            return None

        # Gewicht Dämmung Schalldämpfer
        dataframe_rooms['Isolation volume silencer'] = dataframe_rooms.apply(volumen_daemmung_schalldaempfer,
                                                                                 axis=1)

        # gwp_daemmung_schalldaempfer = (117.4 + 2.132 + 18.43) * (ureg.kilogram / (ureg.meter ** 3))
        # https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=89b4bfdf-8587-48ae-9178-33194f6d1314&version=00.02.000&stock=OBD_2023_I&lang=de

        # list_dataframe_distribution_network_exhaust_air_CO2_schalldaempferdaemmung = [v * gwp_daemmung_schalldaempfer for
        #                                                                              v in dataframe_rooms[
        #                                                                                  "Volumen Dämmung Schalldämpfer"]]

        # dataframe_rooms[
        #     "CO2-Dämmung Schalldämpfer"] = list_dataframe_distribution_network_exhaust_air_CO2_schalldaempferdaemmung

        # Gewicht des Metalls des Schalldämpfers für Trox CA für Packungsdicke 50 bis 400mm danach Packungsdicke 100
        # vordefinierte Daten für Trox CA Schalldämpfer
        trox_ca_durchmesser_gewicht = {
            'diameter': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter,
                            200 * ureg.millimeter, 250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter,
                            450 * ureg.millimeter, 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                            710 * ureg.millimeter, 800 * ureg.millimeter],
            'Gewicht': [6 * ureg.kilogram, 6 * ureg.kilogram, 7 * ureg.kilogram, 8 * ureg.kilogram, 10 * ureg.kilogram,
                        12 * ureg.kilogram, 14 * ureg.kilogram, 18 * ureg.kilogram, 24 * ureg.kilogram,
                        28 * ureg.kilogram, 45 * ureg.kilogram * 2 / 3, 47 * ureg.kilogram * 2 / 3,
                        54 * ureg.kilogram * 2 / 3, 62 * ureg.kilogram * 2 / 3]
        }
        df_trox_ca_diameter_gewicht = pd.DataFrame(trox_ca_durchmesser_gewicht)

        # Funktion, um das nächstgrößere Gewicht zu finden
        def gewicht_schalldaempfer_ohne_daemmung(row):
            if row['silencer'] == 1:
                calculated_diameter = row['calculated diameter']
                passende_zeilen = df_trox_ca_diameter_gewicht[
                    df_trox_ca_diameter_gewicht['diameter'] >= calculated_diameter]
                if not passende_zeilen.empty:
                    next_diameter = passende_zeilen['diameter'].min()
                    gewicht_schalldaempfer = \
                        df_trox_ca_diameter_gewicht[
                            df_trox_ca_diameter_gewicht['diameter'] == next_diameter][
                            'Gewicht'].values[0]
                    daemmung_gewicht = row[
                        "Gewicht Dämmung silencer"] if "Gewicht Dämmung silencer" in row and not pd.isnull(
                        row["Gewicht Dämmung silencer"]) else 0
                    return gewicht_schalldaempfer - daemmung_gewicht
            return None

        dataframe_rooms['Gewicht Blech silencer'] = dataframe_rooms.apply(gewicht_schalldaempfer_ohne_daemmung,
                                                                               axis=1)

        # dataframe_rooms["CO2-Blech Schalldämfer"] = dataframe_rooms["Gewicht Blech silencer"] * (
        #         float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["A1-A3"]) + float(
        #     gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"]))

        # Berechnung der Dämmung
        dataframe_rooms['Cross-sectional area of insulation'] = dataframe_rooms.apply(cross_sectional_area_duct_insulation,
                                                                              axis=1)

        dataframe_rooms['Isolation volume'] = dataframe_rooms['Cross-sectional area of insulation'] * dataframe_rooms[
            'duct length']

        # gwp_kanaldaemmung = (
        #             121.8 * (ureg.kilogram / ureg.meter ** 3) + 1.96 * (ureg.kilogram / ureg.meter ** 3) + 10.21 * (
        #                 ureg.kilogram / ureg.meter ** 3))
        # # https://www.oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?lang=de&uuid=eca9691f-06d7-48a7-94a9-ea808e2d67e8
        #
        # list_dataframe_rooms_CO2_kanaldaemmung = [v * gwp_kanaldaemmung for v in dataframe_rooms["Isolation volume"]]
        #
        # dataframe_rooms['CO2 Duct Isolation'] = list_dataframe_rooms_CO2_kanaldaemmung


        # Export to Excel
        dataframe_rooms.to_excel(self.paths.export / 'ventilation system' / 'exhaust air' / 'dataframe_rooms.xlsx', index=False)

        return pressure_loss, dataframe_rooms, dataframe_distribution_network_exhaust_air
