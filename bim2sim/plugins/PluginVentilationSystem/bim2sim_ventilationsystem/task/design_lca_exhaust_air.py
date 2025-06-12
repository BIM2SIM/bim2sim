import bim2sim
import matplotlib
#matplotlib.use('TkAgg')
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

class DesignExhaustLCA(ITask):
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
        # y-axis of shaft and ahu must be identical
        cross_section_type = 'optimal'  # choose between round, angular and optimal
        suspended_ceiling_space = 200 * ureg.millimeter  # The available height (in [mmm]) in the suspended ceiling is
        # specified here! This corresponds to the available distance between UKRD (lower edge of raw ceiling) and OKFD
        # (upper edge of finished ceiling), see https://www.ctb.de/_wiki/swb/Massbezuege.php


        self.logger.info('Start design LCA')
        thermal_zones = filter_elements(self.elements, 'ThermalZone')
        thermal_zones = [tz for tz in thermal_zones if tz.with_ahu == True]

        self.logger.info('Start calculating points of the ventilation outlet at the ceiling')
        # Here, the center points of the individual rooms are read from the IFC model and then shifted upwards by half
        # the height of the room. The point at the UKRD (lower edge of the bare ceiling) in the middle of the room is
        # therefore calculated. This is where the ventilation outlet is to be positioned later on

        (corner_points,
         airflow_volume_per_storey,
         dict_coordinate_with_space_type,
         dataframe_rooms,
         corners_building) = self.calculate_center_points(thermal_zones,
                                                          building_shaft_exhaust_air)
        self.logger.info('Finished calculating points of the ventilation outlet at the ceiling')

        self.logger.info('Calculating the Coordinates of the ceiling heights')
        # Here the coordinates of the heights at the UKRD are calculated and summarized in a set, as these values are
        # frequently needed in the further course, so they do not have to be recalculated again and again:
        z_coordinate_list = self.calculate_z_coordinate(corner_points)

        self.logger.info('Calculating intersection points')
        # The intersections of all points per storey are calculated here. A grid is created on the respective storey.
        # It is defined as the installation grid for the exhaust air. The individual points of the ventilation inlets
        # are not connected directly, but in practice and according to the standard, ventilation ducts are not laid
        # diagonally through a building
        intersection_points = self.intersection_points(corner_points,
                                                       z_coordinate_list)
        self.logger.info('Calculating intersection points successful')

        self.logger.info('Visualising points on the ceiling for the ventilation outlet:')
        self.visualization(corner_points,
                           intersection_points)

        self.logger.info('Visualising intersection points')
        self.visualization_points_by_level(corner_points,
                                           intersection_points,
                                           z_coordinate_list,
                                           building_shaft_exhaust_air)

        self.logger.info('Create graph for each storey')
        (dict_steiner_tree_with_duct_length,
         dict_steiner_tree_with_duct_cross_section,
         dict_steiner_tree_with_air_volume_exhaust_air,
         dict_steiner_tree_with_shell_surface_area,
         dict_steiner_tree_with_calculated_cross_section) = self.create_graph(corner_points,
                                                                             intersection_points,
                                                                             z_coordinate_list,
                                                                             building_shaft_exhaust_air,
                                                                             cross_section_type,
                                                                             suspended_ceiling_space)

        self.logger.info('Connect shaft and ahu')
        (dict_steiner_tree_with_duct_length,
         dict_steiner_tree_with_duct_cross_section,
         dict_steiner_tree_with_air_volume_exhaust_air,
         dict_steiner_tree_with_shell_surface_area,
         dict_steiner_tree_with_calculated_cross_section) = self.ahu_shaft(z_coordinate_list,
                                                                           building_shaft_exhaust_air,
                                                                           airflow_volume_per_storey,
                                                                           position_rlt,
                                                                           dict_steiner_tree_with_duct_length,
                                                                           dict_steiner_tree_with_duct_cross_section,
                                                                           dict_steiner_tree_with_air_volume_exhaust_air,
                                                                           dict_steiner_tree_with_shell_surface_area,
                                                                           dict_steiner_tree_with_calculated_cross_section)

        self.logger.info('Create 3D-Graph')
        (graph_ventilation_duct_length_exhaust_air,
         graph_air_volume_flow,
         graph_duct_cross_section,
         graph_shell_surface,
         graph_calculated_diameter,
         dataframe_distribution_network_exhaust_air) = self.three_dimensional_graph(dict_steiner_tree_with_duct_length,
                                                                                    dict_steiner_tree_with_duct_cross_section,
                                                                                    dict_steiner_tree_with_air_volume_exhaust_air,
                                                                                    dict_steiner_tree_with_shell_surface_area,
                                                                                    dict_steiner_tree_with_calculated_cross_section,
                                                                                    position_rlt,
                                                                                    dict_coordinate_with_space_type)

        self.logger.info('Start pressure loss calculation')
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

        self.logger.info('Connect rooms to graph')
        dataframe_rooms = self.connect_rooms(cross_section_type, suspended_ceiling_space, dataframe_rooms)

        self.logger.info('Calculate material quantities')
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
        dataframe_rooms['coordinate'] = list(dict_coordinate_with_space_type.keys())
        dataframe_rooms['X'] = [x for x, _, _ in dataframe_rooms['coordinate']]
        dataframe_rooms['Y'] = [y for _, y, _ in dataframe_rooms['coordinate']]
        dataframe_rooms['Z'] = [z for _, _, z in dataframe_rooms['coordinate']]
        dataframe_rooms['room type'] = dataframe_rooms['coordinate'].map(dict_coordinate_with_space_type)
        dataframe_rooms['volume_flow'] = dataframe_rooms['coordinate'].map(dict_coordinate_with_air_volume)

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

        self.logger.info(f'Read {filename} Graph from file {filepath}')
        data = json_graph.node_link_data(graph)
        with self.lock:
            with open(filepath / filename, 'w') as f:
                json.dump(data, f, indent=4)

    def visualization(self, room_ceiling_ventilation_outlet, intersection):
        """The function visualizes the points in a diagram

        Args:
            room_ceiling_ventilation_outlet: Point at the ceiling in the middle of the room
            air_flow_building:
        Returns:
            3D diagram
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

            ax.legend(loc='center left', bbox_to_anchor=(1, 0))

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
           2D diagram for each ceiling
       """
        if self.export_graphs:
            for z_value in z_coordinate_list:
                xy_values = [(x, y) for x, y, z, a in intersection if z == z_value]
                xy_shaft = (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1])
                xy_values_center = [(x, y) for x, y, z, a in corner_points if z == z_value]

                # Delete xy_shaft out of xy_values and xy_values_center
                xy_values = [xy for xy in xy_values if xy != xy_shaft]
                xy_values_center = [xy for xy in xy_values_center if xy != xy_shaft]

                plt.figure(num=f'Floor plan: {z_value}', figsize=(15, 8), dpi=200)
                plt.xlabel('X-Axis [m]')
                plt.ylabel('Y-Axis [m]')
                plt.grid(False)
                plt.subplots_adjust(left=0.1, bottom=0.1, right=0.96,
                                    top=0.96)

                # Plot for intersection points without shaft
                plt.scatter(*zip(*xy_values), color='r', marker='o', label='Intersection points')

                # Plot for shaft
                plt.scatter(xy_shaft[0], xy_shaft[1], color='g', marker='s', label='shaft')

                # Plot for air inlets without shaft
                plt.scatter(*zip(*xy_values_center), color='b', marker='D', label='Air inlet')

                plt.title(f'Height: {z_value}')
                plt.legend(loc='best')

                folder_path = Path(self.paths.export / 'ventilation system' / 'exhaust air' / 'plots' / 'blue prints')

                # Create folder
                folder_path.mkdir(parents=True, exist_ok=True)

                # Save graph
                plot_name = 'Flor plan Z ' + f'{z_value}' + '.png'
                path_and_name = folder_path / plot_name
                plt.savefig(path_and_name)

                # plt.show()
                plt.close()

    def visualization_graph(self,
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
        :param steiner_tree: Steiner tree
        :param z_value: Z-axis
        :param coordinates_without_airflow: coordinates without volume flow
        :param filtered_coords_ceiling_without_airflow: filtered coordinates without volume flow
        :param filtered_coords_intersection_without_airflow: filtered intersection points without volume flow
        :param name: name of plot
        :param edge_unit: unit of edge for legend
        :param total_shell_surface: sum of shell surface area
        """
        plt.figure(figsize=(8.3, 5.8) )
        plt.xlabel('X-Axis [m]')
        plt.ylabel('Y-Axis [m]')
        plt.title(name + f', Z: {z_value}')
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
                               node_shape='s',
                               node_color='green',
                               node_size=10)

        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=filtered_coords_intersection_without_airflow,
                               node_shape='o',
                               node_color='red',
                               node_size=50)

        nx.draw_networkx_edges(G, pos, width=1)
        nx.draw_networkx_edges(steiner_tree, pos, width=1, style='-', edge_color='blue')

        # edge labels
        edge_labels = nx.get_edge_attributes(steiner_tree, edge_label)
        try:
            edge_labels_without_unit = {key: float(value.magnitude) for key, value in edge_labels.items()}
        except AttributeError:
            edge_labels_without_unit = edge_labels
        for key, value in edge_labels_without_unit.items():
            try:
                if 'Ø' in value:
                    value = value.split('Ø')[1].split()[0]  
                    edge_labels_without_unit[key] = f'Ø{value}'
                elif 'x' in value:
                    values = value.split(' x ')
                    width = values[0].split()[0]
                    height = values[1].split()[0]
                    edge_labels_without_unit[key] = f'{width} x {height}'
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
            legend_coat_area = plt.Line2D([0], [0], lw=0, label=f'Shell surface: {total_shell_surface} [m²]')

            plt.legend(
                handles=[legend_ceiling, legend_intersection, legend_shaft, legend_steiner_edge, legend_coat_area],
                loc='best',
                fontsize=8)
        else:
            plt.legend(handles=[legend_ceiling, legend_intersection, legend_shaft, legend_steiner_edge],
                       loc='best')  # , bbox_to_anchor=(1.1, 0.5)

        folder_path = Path(self.paths.export / 'ventilation system' / 'exhaust air' / 'plots' / f'Z_{z_value}')

        folder_path.mkdir(parents=True, exist_ok=True)

        plot_name = name + ' Z ' + f'{z_value}' + '.png'
        path_and_name = folder_path / plot_name
        plt.gca().patch.set_alpha(0)
        plt.xlim(-5, 50)
        plt.ylim(-5, 30)
        plt.savefig(path_and_name, transparent=True)

        # plt.show()
        plt.close()


    def necessary_cross_section(self, volume_flow):
        """
        This function calculates the necessary cross-section of ducts according to the local air volume flow
        Args:
            volume_flow:
        Returns:
            cross_section [m²]
        """

        # Calculation of cross-section with air flow velocity of 5 m³/s according to
        # 'Leitfaden zur Auslegung von lufttechnischen Anlagen' page 10 (www.aerotechnik.de)

        cross_section = (volume_flow / (5 * (ureg.meter / ureg.second))).to('meter**2')
        return cross_section

    # air duct dimensions according to EN 1505 table 1
    df_EN_1505 = pd.DataFrame({
        'width': [200 * ureg.millimeter, 250 * ureg.millimeter, 300 * ureg.millimeter, 400 * ureg.millimeter,
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
        :param duct_cross_section: required duct cross-section
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
        cross_section = f'{best_width} x {best_height}'

        return cross_section

    def dimensions_round_cross_section(self, duct_cross_section, suspended_ceiling_space=2000):
        # ventilation_duct_round_diameter: Is a dict, which has the cross_section [m²] as input variable and the diameter [mm] as
        # output variable is the diameter [mm] according to EN 1506:2007 (D) 4. table 1

        ventilation_duct_round_diameter = {  
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
                return f'Ø{ventilation_duct_round_diameter[key]}'
            elif key > duct_cross_section and ventilation_duct_round_diameter[key] > suspended_ceiling_space:
                return f'suspended_ceiling_space too low'

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

        if cross_section_type == 'round':
            return self.dimensions_round_cross_section(duct_cross_section, suspended_ceiling_space)

        elif cross_section_type == 'angular':
            return self.dimensions_angular_cross_section(duct_cross_section, suspended_ceiling_space)

        elif cross_section_type == 'optimal':
            if self.dimensions_round_cross_section(duct_cross_section,
                                                   suspended_ceiling_space) == 'suspended_ceiling_space too low':
                return self.dimensions_angular_cross_section(duct_cross_section, suspended_ceiling_space)
            else:
                return self.dimensions_round_cross_section(duct_cross_section, suspended_ceiling_space)

    def diameter_round_channel(self, duct_cross_section):
        # # ventilation_duct_round_diameter: Is a dict, which has the cross_section [m²] as input variable and the diameter [mm] as
        # diameter [mm] according to EN 1506:2007 (D) 4. table 1

        ventilation_duct_round_diameter = { 
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
        if cross_section_type == 'round':
            return (math.pi * self.diameter_round_channel(duct_cross_section)).to(ureg.meter)

        elif cross_section_type == 'angular':
            return self.coat_area_angular_ventilation_duct(duct_cross_section)

        elif cross_section_type == 'optimal':
            if self.diameter_round_channel(duct_cross_section) <= suspended_ceiling_space:
                return (math.pi * self.diameter_round_channel(duct_cross_section)).to(ureg.meter)
            else:
                return self.coat_area_angular_ventilation_duct(duct_cross_section, suspended_ceiling_space)

    def calculated_diameter(self, cross_section_type, duct_cross_section, suspended_ceiling_space=2000):
        """
        :param cross_section_type: round, angular or optimal
        :param duct_cross_section: duct cross-section in m²
        :param suspended_ceiling_space: available height in the suspended ceiling
        :return: calculated diameter of the ventilation duct
        """

        if cross_section_type == 'round':
            return self.diameter_round_channel(duct_cross_section)

        elif cross_section_type == 'angular':
            return self.equivalent_diameter(duct_cross_section)

        elif cross_section_type == 'optimal':
            if self.diameter_round_channel(duct_cross_section) <= suspended_ceiling_space:
                return self.diameter_round_channel(duct_cross_section)
            else:
                return self.equivalent_diameter(duct_cross_section, suspended_ceiling_space)

    def euclidean_distance(self, point_1, point_2):
        """
        Calculating the distance between point1 and 2
        :param point_1:
        :param point_2:
        :return: Distance between point_1 and point_2
        """
        return round(
            math.sqrt((point_2[0] - point_1[0]) ** 2 + (point_2[1] - point_1[1]) ** 2 + (point_2[2] - point_1[2]) ** 2),
            2)


    def find_leaves(self, spanning_tree):
        leaves = []
        for node in spanning_tree:
            if len(spanning_tree[node]) == 1:
                leaves.append(node)
        return leaves

    def find_collisions(self, supply_graph, exhaust_graph):
        def orientation(p, q, r):
            """Get orientation of triples (p, q, r)
            Returns:
            0 -> p, q and r are co-linear
            1 -> Clockwise
            2 -> Anti-clockwise
            """
            val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
            if val == 0:
                return 0  # co-linear
            elif val > 0:
                return 1  # clockwise
            else:
                return 2  # anti-clockwise

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
                # Calculate the intersection point
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
                self.logger.info(f'Node {node} is not inside the building boundaries')
                if any(type in graph.nodes[node]['type'] for type in ['radiator_forward',
                                                                      'radiator_backward']):
                    assert KeyError(f'Delivery node {node} not in building boundaries')
                graph.remove_node(node)

        edges_floor = [edge for edge in graph.edges()]
        for edge in edges_floor:
            if not any(is_edge_inside_shape(shape, edge[0], edge[1]) for shape in storey_floor_shapes):
                self.logger.info(f'Edge {edge} does not intersect boundaries')
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
                    assert KeyError('Exhaust graph cannot be connected properly!')

        for components in list(nx.connected_components(exhaust_graph)):
            if all(element in components for element in terminal_nodes):
                exhaust_graph = exhaust_graph.subgraph(list(components))

        return exhaust_graph

    def create_graph(self, ceiling_point, intersection_points, z_coordinate_list, building_shaft_exhaust_air,
                     cross_section_type, suspended_ceiling_space):
        """The function creates a connected graph for each floor
        Args:
           ceiling_point: Point at the ceiling in the middle of the room
           intersection points: intersection points at the ceiling
           z_coordinate_list: z coordinates for each storey ceiling
           building_shaft_exhaust_air: Coordinate of the shaft
           cross_section_type: round, angular or optimal
           suspended_ceiling_space: available height in ceiling
        Returns:
           connected graph for each floor
       """

        def kink_in_ventilation_duct(ventilation_outlet_to_x):
            if ventilation_outlet_to_x != []:
                # Extract the X and Y coordinates
                x_coords = [x for x, _, _ in ventilation_outlet_to_x[0]]
                y_coords = [y for _, y, _ in ventilation_outlet_to_x[0]]

                # Check whether all X-coordinates are the same or all Y-coordinates are the same
                same_x = all(x == x_coords[0] for x in x_coords)
                same_y = all(y == y_coords[0] for y in y_coords)

                if same_x == True or same_y == True:
                    return False
                else:
                    return True
            else:
                None

        def metric_closure(G, weight='weight'):
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
                msg = 'G is not a connected graph. metric_closure is not defined.'
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

        def calculate_steiner_tree(G, terminal_nodes, weight='weight'):
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
            [1] Steiner_tree_problem on Wikipedia.
               https://en.wikipedia.org/wiki/Steiner_tree_problem
            """
            # H is the subgraph induced by terminal_nodes in the metric closure M of G.
            M = metric_closure(G, weight=weight)
            H = M.subgraph(terminal_nodes)
            # Use the 'distance' attribute of each edge provided by M.
            mst_edges = nx.minimum_spanning_edges(H, weight='distance', data=True)
            # Create an iterator over each edge in each shortest path; repeats are okay
            edges = chain.from_iterable(pairwise(d['path']) for u, v, d in mst_edges)
            # For multigraph we should add the minimal weight edge keys
            if G.is_multigraph():
                edges = (
                    (u, v, min(G[u][v], key=lambda k: G[u][v][k][weight])) for u, v in edges
                )
            T = G.edge_subgraph(edges)
            return T

        # Create a new dataframe from the combinations
        dict_steiner_tree_with_duct_length = {i: None for i in z_coordinate_list}
        dict_steiner_tree_with_air_volume_exhaust_air = {i: None for i in z_coordinate_list}
        dict_steiner_tree_with_duct_cross_section = {i: None for i in z_coordinate_list}
        dict_steiner_tree_with_calculated_cross_section = {i: None for i in z_coordinate_list}
        dict_steiner_tree_with_shell_surface_area = {i: None for i in z_coordinate_list}

        for z_value in z_coordinate_list:

            # Filter coords per storey
            filtered_coords_ceiling = [coord for coord in ceiling_point if coord[2] == z_value]
            filtered_coords_intersection = [coord for coord in intersection_points if coord[2] == z_value]
            coordinates = filtered_coords_intersection + filtered_coords_ceiling

            # Coords without air volume flows
            filtered_coords_ceiling_without_airflow = [(x, y, z) for x, y, z, a in filtered_coords_ceiling]
            filtered_coords_intersection_without_airflow = [(x, y, z) for x, y, z, a in
                                                            filtered_coords_intersection]
            coordinates_without_airflow = (filtered_coords_ceiling_without_airflow
                                           + filtered_coords_intersection_without_airflow)

            # Create graph
            G = nx.Graph()

            # Terminal nodes (must be connected via steiner tree)
            terminals = list()

            for x, y, z, a in filtered_coords_ceiling:
                if x == building_shaft_exhaust_air[0] and y == building_shaft_exhaust_air[1]:
                    G.add_node((x, y, z), weight=a, color='green')
                else:
                    G.add_node((x, y, z), weight=a, color='orange')
                if a > 0:  
                    terminals.append((x, y, z))

            for x, y, z, a in filtered_coords_intersection:
                G.add_node((x, y, z), weight=0, color='red')

            # Add edges via x-axis
            unique_coords = set(coord[0] for coord in coordinates_without_airflow)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in coordinates_without_airflow if coord[0] == u],
                                            key=lambda c: c[1 - 0])
                for i in range(len(nodes_on_same_axis) - 1):
                    weight_edge_y = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], length=weight_edge_y)

            # Add edges via y-axis
            unique_coords = set(coord[1] for coord in coordinates_without_airflow)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in coordinates_without_airflow if coord[1] == u],
                                            key=lambda c: c[1 - 1])
                for i in range(len(nodes_on_same_axis) - 1):
                    weight_edge_x = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], length=weight_edge_x)

     
            self.logger.info('Check if nodes and edges of exhaust graph are inside the boundaries of the building')
            G = self.check_if_graph_in_building_boundaries(G, z_value)
            self.logger.info('Check done')

            self.logger.info('Check and minimize collisions between supply and exhaust graphs')
            G = self.minimize_collisions_with_supply_graph(self.supply_graph, G, terminals)
            self.logger.info('Check done')

            # Create steiner tree
            graph_steiner_tree = calculate_steiner_tree(G, terminals, weight='length')

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_ceiling_without_airflow,
                                         filtered_coords_intersection_without_airflow,
                                         edge_label = 'length',
                                         name=f'Steiner tree - Initial optimization',
                                         edge_unit='m',
                                         total_shell_surface=False,
                                         building_shaft_exhaust_air=building_shaft_exhaust_air
                                         )

            nodes = list(graph_steiner_tree.nodes())
            edges = list(graph_steiner_tree.edges())

            tree = nx.Graph()

            for x, y, z in nodes:
                for point in coordinates:
                    if point[0] == x and point[1] == y and point[2] == z:
                        tree.add_node((x, y, z), weight=point[3])

            for edge in edges:
                tree.add_edge(edge[0], edge[1], length=self.euclidean_distance(edge[0], edge[1]))

            minimum_spanning_tree = nx.minimum_spanning_tree(tree)

            """Optimization step 1"""
            # This checks which points along a path lie on an axis. The aim is to find the Steiner points that lie
            # between two terminals so that the graph can be optimized.
            coordinates_on_same_axis = list()
            for starting_node in filtered_coords_ceiling_without_airflow:
                for target_node in filtered_coords_ceiling_without_airflow:
                    for path in nx.all_simple_paths(minimum_spanning_tree, starting_node, target_node):
                        # Extract the X and Y coordinates
                        x_coords = [x for x, _, _ in path]
                        y_coords = [y for _, y, _ in path]

                        # Check whether all X-coordinates are the same or all Y-coordinates are the same
                        same_x = all(x == x_coords[0] for x in x_coords)
                        same_y = all(y == y_coords[0] for y in y_coords)

                        if same_x == True or same_y == True:
                            for cord in path:
                                coordinates_on_same_axis.append(cord)

            # Remove duplicates:
            coordinates_on_same_axis = set(coordinates_on_same_axis)

            # If the coordinate is a ventilation outlet, it must be ignored
            coordinates_on_same_axis = [item for item in coordinates_on_same_axis if item not in
                                        filtered_coords_ceiling_without_airflow]

            # Adding the coordinates to the terminals
            for coord in coordinates_on_same_axis:
                terminals.append(coord)

            # Creation of the new Steiner tree
            graph_steiner_tree = calculate_steiner_tree(G, terminals, weight='length')

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_ceiling_without_airflow,
                                         filtered_coords_intersection_without_airflow,
                                         edge_label = 'length',
                                         name=f'Steiner tree - 1. optimization',
                                         edge_unit='m',
                                         total_shell_surface=False,
                                         building_shaft_exhaust_air=building_shaft_exhaust_air
                                         )

            """Optimization step 2"""
            # This checks whether there are any unnecessary kinks in the graph:
            for ventilation_outlet in filtered_coords_ceiling_without_airflow:
                if graph_steiner_tree.degree(ventilation_outlet) == 2:
                    neighbors = list(nx.all_neighbors(graph_steiner_tree, ventilation_outlet))

                    neighbor_outlet_one = neighbors[0]
                    temp = list()
                    i = 0
                    while neighbor_outlet_one not in filtered_coords_ceiling_without_airflow:
                        temp.append(neighbor_outlet_one)
                        new_neighbors = list(nx.all_neighbors(graph_steiner_tree, neighbor_outlet_one))
                        new_neighbors = [coord for coord in new_neighbors if coord != ventilation_outlet]
                        neighbor_outlet_one = [coord for coord in new_neighbors if coord != temp[i - 1]]
                        neighbor_outlet_one = neighbor_outlet_one[0]
                        i += 1
                        if neighbor_outlet_one in filtered_coords_ceiling_without_airflow:
                            break

                    neighbor_outlet_two = neighbors[1]
                    temp = list()
                    i = 0
                    while neighbor_outlet_two not in filtered_coords_ceiling_without_airflow:
                        temp.append(neighbor_outlet_two)
                        new_neighbors = list(nx.all_neighbors(graph_steiner_tree, neighbor_outlet_two))
                        new_neighbors = [coord for coord in new_neighbors if coord != ventilation_outlet]
                        neighbor_outlet_two = [coord for coord in new_neighbors if coord != temp[i - 1]]
                        neighbor_outlet_two = neighbor_outlet_two[0]
                        i += 1
                        if neighbor_outlet_two in filtered_coords_ceiling_without_airflow:
                            break

                    # Returns the path from neighboring outlet 1 to the ventilation outlet in the form of nodes
                    ventilation_outlet_to_one = list(nx.all_simple_paths(graph_steiner_tree, ventilation_outlet,
                                                                        neighbor_outlet_one))

                    # Returns the path from the ventilation outlet to the neighboring outlet 2 in the form of nodes
                    ventilation_outlet_to_two = list(nx.all_simple_paths(graph_steiner_tree, ventilation_outlet,
                                                                        neighbor_outlet_two))

                    if kink_in_ventilation_duct(ventilation_outlet_to_one) == False and kink_in_ventilation_duct(
                            ventilation_outlet_to_two) == False:
                        None
                    elif kink_in_ventilation_duct(ventilation_outlet_to_one) == True:
                        if ventilation_outlet_to_one != [] and ventilation_outlet_to_two != []:
                            if ventilation_outlet[0] == ventilation_outlet_to_two[0][1][0]:
                                terminals.append((ventilation_outlet[0], neighbor_outlet_one[1], z_value))
                            elif ventilation_outlet[1] == ventilation_outlet_to_two[0][1][1]:
                                terminals.append((neighbor_outlet_one[0], ventilation_outlet[1], z_value))
                    elif kink_in_ventilation_duct(ventilation_outlet_to_two) == True:
                        if ventilation_outlet_to_one != [] and ventilation_outlet_to_two != []:
                            if ventilation_outlet[0] == ventilation_outlet_to_one[0][1][0]:
                                terminals.append((ventilation_outlet[0], neighbor_outlet_two[1], z_value))
                            elif ventilation_outlet[1] == ventilation_outlet_to_one[0][1][1]:
                                terminals.append((neighbor_outlet_two[0], ventilation_outlet[1], z_value))

            # Creation of the new Steiner tree
            graph_steiner_tree = calculate_steiner_tree(G, terminals, weight='length')

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_ceiling_without_airflow,
                                         filtered_coords_intersection_without_airflow,
                                         edge_label = 'length',
                                         name=f'Steiner tree - 2. optimization',
                                         edge_unit='m',
                                         total_shell_surface=False,
                                         building_shaft_exhaust_air=building_shaft_exhaust_air
                                         )

            """3. optimization"""
            # Here the leaves are read from the graph
            leaves = self.find_leaves(graph_steiner_tree)

            for blatt in leaves:
                if blatt not in filtered_coords_ceiling_without_airflow:
                    terminals.remove(blatt)

            # Creation of the new Steiner tree
            graph_steiner_tree = calculate_steiner_tree(G, terminals, weight='length')

            # add unit of length of the edge in the Steiner tree
            for u, v, data in graph_steiner_tree.edges(data=True):
                weight_without_unit = data['length']
                weight_with_unit = weight_without_unit * ureg.meter

                data['length'] = weight_with_unit

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_ceiling_without_airflow,
                                         filtered_coords_intersection_without_airflow,
                                         edge_label = 'length',
                                         name=f'Steiner tree - 3. optimization',
                                         edge_unit='m',
                                         total_shell_surface=False,
                                         building_shaft_exhaust_air=building_shaft_exhaust_air
                                         )

            # Steiner tree with duct lengths
            dict_steiner_tree_with_duct_length[z_value] = deepcopy(graph_steiner_tree)

            starting_point = (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value)

            # Creation of the tree (this is where the new, first improved tree is created!) The points, which are all
            # between two ventilation outlets are used to route other ducts along the same axis

            nodes = list(graph_steiner_tree.nodes())
            edges = list(graph_steiner_tree.edges())

            tree = nx.Graph()

            # Add leaves to tree
            for x, y, z in nodes:
                for point in coordinates:
                    if point[0] == x and point[1] == y and point[2] == z:
                        tree.add_node((x, y, z), weight=point[3])

            for edge in edges:
                tree.add_edge(edge[0], edge[1], length=self.euclidean_distance(edge[0], edge[1]))

            # The minimum spanning tree of the Steiner tree is calculated here
            minimum_spanning_tree = nx.minimum_spanning_tree(tree)

            # The paths in the tree from the ventilation outlet to the starting point are read out here
            ceiling_point_to_root_list = list()
            for point in filtered_coords_ceiling_without_airflow:
                for path in nx.all_simple_edge_paths(minimum_spanning_tree, point, starting_point):
                    ceiling_point_to_root_list.append(path)

            # The weights of the edges in the Steiner tree are deleted here, as otherwise the air volume is added to the
            # distance. However, the weight of the edge must not be set to 0 at the beginning,
            # otherwise the Steiner tree will not be calculated correctly
            for u, v in graph_steiner_tree.edges():
                graph_steiner_tree[u][v]['volume_flow'] = 0

            # The air volumes along the ventilation duct are added up here
            for ceiling_point_to_root in ceiling_point_to_root_list:
                for startingpoint, targetpoint in ceiling_point_to_root:
                    value = None
                    for x, y, z, a in coordinates:
                        if x == ceiling_point_to_root[0][0][0] and y == ceiling_point_to_root[0][0][1] and z == \
                                ceiling_point_to_root[0][0][2]:
                            value = a
                    graph_steiner_tree[startingpoint][targetpoint]['volume_flow'] += value

            # Here the individual steiner tree is added to the list with volume flow
            dict_steiner_tree_with_air_volume_exhaust_air[z_value] = deepcopy(graph_steiner_tree)

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_ceiling_without_airflow,
                                         filtered_coords_intersection_without_airflow,
                                         edge_label='volume_flow',
                                         name=f'Steiner tree with air volume flow in m³ / h',
                                         edge_unit='m³/h',
                                         total_shell_surface=False,
                                         building_shaft_exhaust_air=building_shaft_exhaust_air
                                         )


            for u, v in graph_steiner_tree.edges():
                graph_steiner_tree[u][v]['cross_section'] = self.dimensions_ventilation_duct(cross_section_type,
                                                                             self.necessary_cross_section(
                                                                                 graph_steiner_tree[u][v][
                                                                                     'volume_flow']),
                                                                             suspended_ceiling_space)

            # Adding the graph to the dict
            dict_steiner_tree_with_duct_cross_section[z_value] = deepcopy(graph_steiner_tree)

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_ceiling_without_airflow,
                                         filtered_coords_intersection_without_airflow,
                                         edge_label='cross_section',
                                         name=f'Steiner tree with duct cross-section in mm',
                                         edge_unit='mm',
                                         total_shell_surface=False,
                                         building_shaft_exhaust_air=building_shaft_exhaust_air
                                         )

            # The equivalent diameter of the duct is assigned to the pipe here
            for u, v in graph_steiner_tree.edges():
                graph_steiner_tree[u][v]['equivalent_diameter'] = self.calculated_diameter(cross_section_type,
                                                                                     self.necessary_cross_section(
                                                                                                 graph_steiner_tree[
                                                                                                     u][v][
                                                                                                     'volume_flow']),
                                                                                     suspended_ceiling_space)

            # Add to dict
            dict_steiner_tree_with_calculated_cross_section[z_value] = deepcopy(graph_steiner_tree)

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_ceiling_without_airflow,
                                         filtered_coords_intersection_without_airflow,
                                         edge_label='equivalent_diameter',
                                         name=f'Steiner tree with calculated duct diameter in mm',
                                         edge_unit='mm',
                                         total_shell_surface=False,
                                         building_shaft_exhaust_air=building_shaft_exhaust_air
                                         )

            # In order to determine the total amount of shell surface area, this must be added up:
            total_shell_surface_area_duct = 0

            # Here the pipe is assigned the lateral surface of the duct
            for u, v in graph_steiner_tree.edges():
                graph_steiner_tree[u][v]['circumference'] = round(self.coat_area_ventilation_duct(cross_section_type,
                                                                                            self.necessary_cross_section(
                                                                                  graph_steiner_tree[u][v]['volume_flow']),
                                                                                            suspended_ceiling_space), 2)

                total_shell_surface_area_duct += round(graph_steiner_tree[u][v]['volume_flow'], 2)

            # Adding the graph to the dict
            dict_steiner_tree_with_shell_surface_area[z_value] = deepcopy(graph_steiner_tree)

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_ceiling_without_airflow,
                                         filtered_coords_intersection_without_airflow,
                                         edge_label='circumference',
                                         name=f'Steiner tree with shell surface area',
                                         edge_unit='m²/m',
                                         total_shell_surface="",
                                         building_shaft_exhaust_air=building_shaft_exhaust_air
                                         )

            self.write_json_graph(graph=graph_steiner_tree,
                                  filename=f'exhaust_air_floor_Z_{z_value}.json')

        return (dict_steiner_tree_with_duct_length,
                dict_steiner_tree_with_duct_cross_section,
                dict_steiner_tree_with_air_volume_exhaust_air,
                dict_steiner_tree_with_shell_surface_area,
                dict_steiner_tree_with_calculated_cross_section)

    def ahu_shaft(self,
                  z_coordinate_list,
                  building_shaft_exhaust_air,
                  airflow_volume_per_storey,
                  position_ahu,
                  dict_steiner_tree_with_duct_length,
                  dict_steiner_tree_with_duct_cross_section,
                  dict_steiner_tree_with_air_volume,
                  dict_steiner_tree_with_shell_surface_area,
                  dict_steiner_tree_with_calculated_cross_section):

        nodes_shaft = list()
        z_coordinate_list = list(z_coordinate_list)
        # From here, the graph for the AHU is created up to the shaft.
        shaft = nx.Graph()

        for z_value in z_coordinate_list:
            # Adding the nodes
            shaft.add_node((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value),
                             weight=airflow_volume_per_storey[z_value], color='green')
            nodes_shaft.append((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value,
                                  airflow_volume_per_storey[z_value]))

        # From here, the graph is created across the storeys:
        # Add edges for shaft:
        for i in range(len(z_coordinate_list) - 1):
            weight = self.euclidean_distance(
                [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], float(z_coordinate_list[i])],
                [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1],
                 float(z_coordinate_list[i + 1])]) * ureg.meter
            shaft.add_edge((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_coordinate_list[i]),
                             (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_coordinate_list[i + 1]),
                             length=weight)

        # Sum Airflow
        sum_airflow = sum(airflow_volume_per_storey.values())

        # Enrich nodes of the air handling unit with total air volume
        shaft.add_node((position_ahu[0], position_ahu[1], position_ahu[2]),
                         weight=sum_airflow, color='green')

        shaft.add_node((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_ahu[2]),
                         weight=sum_airflow, color='green')

        # Connecting the AHU to the shaft
        ahu_shaft_weight = self.euclidean_distance([position_ahu[0], position_ahu[1], position_ahu[2]],
                                                     [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1],
                                                      position_ahu[2]]
                                                     ) * ureg.meter

        shaft.add_edge((position_ahu[0], position_ahu[1], position_ahu[2]),
                         (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_ahu[2]),
                         length=ahu_shaft_weight)

        # If the AHU is not at ceiling level, the air duct must still be connected to the shaft
        list_shaft_nodes = list(shaft.nodes())
        closest = None
        min_distance = float('inf')

        for coord in list_shaft_nodes:
            # Skip if it's the same coordinate
            if coord == (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_ahu[2]):
                continue
            # Check if the x and y coordinates are the same
            if coord[0] == building_shaft_exhaust_air[0] and coord[1] == building_shaft_exhaust_air[1]:
                distance = abs(coord[2] - position_ahu[2])
                if distance < min_distance:
                    min_distance = distance
                    closest = coord

        connection_weight = self.euclidean_distance([building_shaft_exhaust_air[0], 
                                                        building_shaft_exhaust_air[1],
                                                        position_ahu[2]],
                                                    closest) * ureg.meter
        shaft.add_edge((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_ahu[2]),
                         closest,
                         length=connection_weight)

        # Add to dict
        dict_steiner_tree_with_duct_length['shaft'] = deepcopy(shaft)

        position_ahu_without_airflow = (position_ahu[0], position_ahu[1], position_ahu[2])

        # The paths in the tree from the ventilation outlet to the starting point are read out here
        shaft_to_ahu = list()
        for point in shaft.nodes():
            for path in nx.all_simple_edge_paths(shaft, point, position_ahu_without_airflow):
                shaft_to_ahu.append(path)

        # The weights of the edges in the steiner_tree are deleted here, as otherwise the amount
        # of air is added to the distance. However, the weight of the edge must not be set to 0
        # at the beginning either otherwise the steiner_tree will not be calculated correctly
        for u, v in shaft.edges():
            shaft[u][v]['volume_flow'] = 0

        # The air volumes along the line are added up here
        for shaftpoint_to_ahu in shaft_to_ahu:
            for startingpoint, targetpoint in shaftpoint_to_ahu:
                # Search for the ventilation volume to coordinate:
                value = int()
                for x, y, z, a in nodes_shaft:
                    if x == shaftpoint_to_ahu[0][0][0] and y == shaftpoint_to_ahu[0][0][1] and z == \
                            shaftpoint_to_ahu[0][0][2]:
                        value = a
                shaft[startingpoint][targetpoint]['volume_flow'] += value

        # Add to dict
        dict_steiner_tree_with_air_volume['shaft'] = deepcopy(shaft)

        # determine duct_cross_section shaft and ahu <-> shaft 
        for u, v in shaft.edges():
            shaft[u][v]['cross_section'] = self.dimensions_ventilation_duct('angular',
                                                                              self.necessary_cross_section(
                                                                                  shaft[u][v]['volume_flow']),
                                                                              suspended_ceiling_space=2000)

        # Add to dict
        dict_steiner_tree_with_duct_cross_section['shaft'] = deepcopy(shaft)

        # Here, the duct is assigned the lateral surface of the trunking
        for u, v in shaft.edges():
            shaft[u][v]['circumference'] = round(self.coat_area_ventilation_duct('angular',
                                                                                   self.necessary_cross_section(
                                                                                       shaft[u][v]['volume_flow']),
                                                                                   suspended_ceiling_space=2000) ,2)

        # Add to dict
        dict_steiner_tree_with_shell_surface_area['shaft'] = deepcopy(shaft)

        # The equivalent diameter of the duct is assigned to the pipe here
        for u, v in shaft.edges():
            shaft[u][v]['equivalent_diameter'] = self.calculated_diameter('angular',
                                                                            self.necessary_cross_section(
                                                                                shaft[u][v]['volume_flow']),
                                                                            suspended_ceiling_space=2000)

        # Add to dict
        dict_steiner_tree_with_calculated_cross_section['shaft'] = deepcopy(shaft)

        self.write_json_graph(graph=shaft,
                              filename=f'exhaust_air_shaft.json')

        return (dict_steiner_tree_with_duct_length,
                dict_steiner_tree_with_duct_cross_section,
                dict_steiner_tree_with_air_volume,
                dict_steiner_tree_with_shell_surface_area,
                dict_steiner_tree_with_calculated_cross_section)

    def find_dimension(self, text: str):
        if 'Ø' in text:
            # Case 1: 'Ø' followed by a number
            number = ureg(text.split('Ø')[1])  # Splits the string at the 'Ø' and takes the second part
            return number
        else:
            # Case 2: '250 x 200' format
            number = text.split(' x ')  # Splits the string at ' x '
            width = ureg(number[0])
            height = ureg(number[1])
            return width, height

    def three_dimensional_graph(self,
                                dict_steiner_tree_with_duct_length,
                                dict_steiner_tree_with_duct_cross_section,
                                dict_steiner_tree_with_air_volume_exhaust_air,
                                dict_steiner_tree_with_shell_surface_area,
                                dict_steiner_tree_with_calculated_cross_section,
                                position_ahu,
                                dict_coordinate_with_space_type):

        # A helper function to recursively traverse the graph, align the edges and apply the weights
        def add_edges_and_nodes(G, current_node, H, parent=None):
            # Copy the node attributes from H to G
            G.add_node(current_node, **H.nodes[current_node])
            for neighbor in H.neighbors(current_node):
                if neighbor != parent:
                    # Retrieve the weight and any other attributes for the edge
                    edge_data = H.get_edge_data(current_node, neighbor)
                    # Add a directed edge with the copied attributes
                    G.add_edge(current_node, neighbor, **edge_data)
                    # Recursive appeal for the neighbor
                    add_edges_and_nodes(G, neighbor, H, current_node)

        # Empty graphs are created here. These are then enriched with the graphs of the individual levels
        graph_duct_length = nx.Graph()
        graph_air_volume_flow = nx.Graph()
        graph_duct_cross_section = nx.Graph()
        graph_shell_surface = nx.Graph()
        graph_calculated_diameter = nx.Graph()

        position_ahu = (position_ahu[0], position_ahu[1], position_ahu[2])

        # for duct length
        for tree in dict_steiner_tree_with_duct_length.values():
            graph_duct_length = nx.compose(graph_duct_length, tree)

        # Convert graph for duct length into a directed graph
        graph_duct_length_directional = nx.DiGraph()
        add_edges_and_nodes(graph_duct_length_directional, position_ahu, graph_duct_length)

        # for air volumes
        for tree in dict_steiner_tree_with_air_volume_exhaust_air.values():
            graph_air_volume_flow = nx.compose(graph_air_volume_flow, tree)

        # Convert graph for air volumes into a directed graph
        graph_air_volume_directional= nx.DiGraph()
        add_edges_and_nodes(graph_air_volume_directional, position_ahu, graph_air_volume_flow)

        # for duct cross-section
        for tree in dict_steiner_tree_with_duct_cross_section.values():
            graph_duct_cross_section = nx.compose(graph_duct_cross_section, tree)

        # Convert graph for duct cross-section into a directed graph
        graph_duct_cross_section_directional = nx.DiGraph()
        add_edges_and_nodes(graph_duct_cross_section_directional, position_ahu, graph_duct_cross_section)

        # for shell surface
        for tree in dict_steiner_tree_with_shell_surface_area.values():
            graph_shell_surface = nx.compose(graph_shell_surface, tree)

        # Convert graph for shell surface into a directed graph
        graph_sheath_directional = nx.DiGraph()
        add_edges_and_nodes(graph_sheath_directional, position_ahu, graph_shell_surface)

        # for calculated cross-section
        for tree in dict_steiner_tree_with_calculated_cross_section.values():
            graph_calculated_diameter = nx.compose(graph_calculated_diameter, tree)

        # Convert graph for calculated cross-section into a directed graph
        graph_calculated_diameter_directional = nx.DiGraph()
        add_edges_and_nodes(graph_calculated_diameter_directional, position_ahu, graph_calculated_diameter)

        dataframe_distribution_network = pd.DataFrame(columns=[
            'starting_node',
            'target_node',
            'edge',
            'room_type_starting_node',
            'room_type_target_node',
            'duct_length',
            'volume_flow',
            'cross_section',
            'surface_area',
            'equivalent_diameter'
        ])

        # Add data to the database
        for u, v in graph_duct_length_directional.edges():
            temp_df = pd.DataFrame({
                'starting_node': [v],  # Reversed because exhaust air
                'target_node': [u],  # Reversed because exhaust air
                'edge': [(v, u)],  # Reversed because exhaust air
                'room_type_starting_node': [dict_coordinate_with_space_type.get(v, None)],
                'room_type_target_node': [dict_coordinate_with_space_type.get(u, None)],
                'duct_length': [graph_duct_length_directional.get_edge_data(u, v)['length']],
                'volume_flow': [graph_air_volume_directional.get_edge_data(u, v)['volume_flow']],
                'cross_section': [graph_duct_cross_section_directional.get_edge_data(u, v)['cross_section']],
                'surface_area': [graph_sheath_directional.get_edge_data(u, v)['circumference'] *
                                 graph_duct_length_directional.get_edge_data(u, v)['length']],
                'equivalent_diameter': [graph_calculated_diameter_directional.get_edge_data(u, v)['equivalent_diameter']]
            })
            dataframe_distribution_network = pd.concat([dataframe_distribution_network, temp_df],
                                                                  ignore_index=True)

        for index, row in dataframe_distribution_network.iterrows():
            duct_cross_section = row['cross_section']

            if 'Ø' in duct_cross_section:
                # Find the diameter and update the corresponding value in the database
                dataframe_distribution_network.at[index, 'diameter'] = str(
                    self.find_dimension(duct_cross_section))

            elif 'x' in duct_cross_section:
                # Find width and height, decompose the cross-section value, and update the corresponding values in the database
                width, height = self.find_dimension(duct_cross_section)
                dataframe_distribution_network.at[index, 'width'] = str(width)
                dataframe_distribution_network.at[index, 'height'] = str(height)

        if self.export_graphs:
            # Display of the 3D graph:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

            # Nodes positions in 3D
            pos = {coord: (coord[0], coord[1], coord[2]) for coord in list(graph_air_volume_flow.nodes())}

            # Draw nodes
            for node, weight in nx.get_node_attributes(graph_air_volume_flow, 'weight').items():
                if weight > 0:  # Check whether the weight is greater than 0
                    color = 'blue'
                else:
                    color = 'red'  # Otherwise, red (or another color for weight = 0)

                # Drawing the nodes with the specified color
                ax.scatter(*node, color=color)

            # Draw edges
            for edge in graph_air_volume_flow.edges():
                start, end = edge
                x_start, y_start, z_start = pos[start]
                x_end, y_end, z_end = pos[end]
                ax.plot([x_start, x_end], [y_start, y_end], [z_start, z_end], 'black')

            # Axis labels and titles
            ax.set_xlabel('X-axis [m]')
            ax.set_ylabel('Y-axis [m]')
            ax.set_zlabel('Z-axis [m]')
            ax.set_title('3D Graph exhaust air')

            # Add a legend
            ax.legend()

            # Show diagram
            plt.close()

        return (graph_duct_length_directional,
                graph_air_volume_directional,
                graph_duct_cross_section_directional,
                graph_sheath_directional,
                graph_calculated_diameter_directional,
                dataframe_distribution_network
                )

    def calculate_pressure_loss(self,
                                dict_steiner_tree_with_duct_length,
                                z_coordinate_list,
                                position_ahu,
                                position_shaft,
                                graph_duct_length,
                                graph_air_volume_flow,
                                graph_duct_cross_section,
                                graph_shell_surface,
                                graph_calculated_diameter,
                                dataframe_distribution_network):

        def check_if_lines_are_aligned(line1, line2):
            """
            Checks whether two straight lines in space are parallel
            :param line1: Linie 1 (x,y,z)
            :param line2: Linie 2 (x,y,z)
            :return: True or False
            """
            # Calculation of the direction vectors for both lines
            vector1 = np.array([line1[1][0] - line1[0][0], line1[1][1] - line1[0][1], line1[1][2] - line1[0][2]])
            vector2 = np.array([line2[1][0] - line2[0][0], line2[1][1] - line2[0][1], line2[1][2] - line2[0][2]])

            # Check if the vectors are multiples of each other
            # This is done by cross product, which should be zero if they are aligned
            cross_product = np.cross(vector1, vector2)

            return np.all(cross_product == 0)

        def loss_coefficient_arc_round(angle: int, mean_radius: float, diameter: float) -> float:
            """
            Calculates the loss coefficient for a round arc (A01 -VDI 3803-6)
            :param angle: angle in °
            :param mean_radius: average radius of the arc in m
            :param diameter: Diameter of the duct in m
            :return: loss coefficient for a round arc
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * angle)

            b = None
            if 0.5 <= mean_radius / diameter <= 1.0:
                b = 0.21 / ((mean_radius / diameter) ** 2.5)
            elif 1 <= mean_radius / diameter:
                b = (0.21 / (math.sqrt(mean_radius / diameter)))

            c = 1

            return a * b * c

        def loss_coefficient_arc_angular(angle: int, mean_radius: float,
                                         height: float, width: float, calculated_diameter: float):
            """
            Calculates the loss coefficient for an angular arc (A02 - VDI 3803-6)
            :param angle: angle in °
            :param mean_radius: average radius of the arc in m
            :param height: height of the duct in m
            :param width: width of the duct in m
            :param calculated_diameter: calculated diameter of the duct in m
            :return: loss coefficient for an angular arc
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * angle)

            b = 0
            if 0.5 <= (mean_radius / calculated_diameter) <= 1.0:
                b = 0.21 / ((mean_radius / calculated_diameter) ** 2.5)
            elif 1 <= mean_radius / calculated_diameter:
                b = (0.21 / (math.sqrt(mean_radius / calculated_diameter)))

            c = (- 1.03663 * 10 ** (-4) * (height / width) ** 5 + 0.00338 * (height / width) ** 4 - 0.04277 * (
                    height / width)
                 ** 3 + 0.25496 * (height / width) ** 2 - 0.66296 * (height / width) + 1.4499)

            return a * b * c

        def loss_coefficient_cross_sectional_narrowing_continuous(d_1, d_2):
            """
            Calculates the loss coefficient for a cross-section narrowing (A15 - VDI 3803-6)
            :param d_1: diameter Air inlet in meters
            :param d_2: diameter Air outlet in meters
            :return: loss coefficient for a cross-section narrowing
            """

            if d_1 <= d_2:
                self.logger.error("diameter 2 can't be larger than diameter 1!")

            else:
                l = 0.3 * ureg.meter  # The standard length is set at 0.5 meters

                # angle
                beta = math.degrees(math.atan((d_1 - d_2) / (2 * l)))

                # coefficient:
                k_1 = - 0.0125 + 0.00135 * beta

                # cross_section 1:
                A_1 = math.pi * d_1 ** 2 / 4

                # cross_section 2:
                A_2 = math.pi * d_2 ** 2 / 4

                zeta_1 = - (k_1) * (A_2 / A_1) ** 2 + k_1

                if zeta_1 < 0:
                    zeta_1 = 0

                return zeta_1

        def loss_coefficient_cross_sectional_extension_continuous(d_1, d_2):
            """
            Calculates the loss coefficient for a cross-section extension (A14 - VDI 3803-6)
            :param d_1: diameter Air inlet in meters
            :param d_2: diameter Air outlet in meters
            :return: loss coefficient for a cross-section extension
            """

            if d_1 >= d_2:
                self.logger.error("diameter 1 can't be larger than diameter 2!")

            else:
                l = 0.3 * ureg.meter  # The standard length is set at 0.5 meters

                # angle
                beta = math.degrees(math.atan((d_2 - d_1) / (2 * l)))

                # epsilon:
                eta_D = 1.01 / (1 + 10 ** (-0.05333 * (24.15 - beta)))

                # cross-section 1:
                A_1 = math.pi * d_1 ** 2 / 4

                # cross-section 2:
                A_2 = math.pi * d_2 ** 2 / 4

                zeta_1 = (1 - A_1 / A_2) ** 2 * (1 - eta_D)

                return zeta_1

        def loss_coefficient_T_separation_round(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                      v_A: float,
                                                      direction: str) -> float:
            """
            Calculates the loss coefficient for a T-separation (type A22 - VDI 3803-6)
            :param d: Diameter of the entrance in meters
            :param v: Volume flow of the input in m³/h
            :param d_D: Diameter of the passage in meters
            :param v_D: Volume flow of the passage in m³/h
            :param d_A: Diameter of the outlet in meters
            :param v_A: Volume flow of the outlet in m³/h
            :param direction: 'direction of passage' or 'branching direction'
            :return: loss coefficient for a T-separation
            """

            # cross_section entrance:
            A = math.pi * d ** 2 / 4
            # Inlet flow velocity
            w = (v / A).to(ureg.meter / ureg.second)

            # cross_section passageway:
            A_D = math.pi * d_D ** 2 / 4
            # Flow velocity Passage
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # cross_section Junction:
            A_A = math.pi * d_A ** 2 / 4
            # Flow velocity branch
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            # Coefficient
            K_D = 0.4

            if direction == 'direction of passage':
                zeta_D = (K_D * (1 - w_D / w) ** 2) / (w_D / w) ** 2
                return zeta_D
            elif direction == 'branching direction':
                # Type 'a' according to VDI 3803-6
                zeta_A = 0.26 + 55.29 * math.exp(-(w_A / w) / 0.1286) + 555.26 * math.exp(
                    -(w_A / w) / 0.041) + 5.73 * math.exp(-(w_A / w) / 0.431)
                return zeta_A
            else:
                self.logger.error('No or incorrect direction input')

        def loss_coefficient_T_separation_angular(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                        v_A: float, direction: str) -> float:
            """
            Calculates the loss coefficient for a T-separation (type A24 - VDI 3803-6)
            :param d: Diameter of the entrance in meters
            :param v: Volume flow of the input in m³/h
            :param d_D: Diameter of the passage in meters
            :param v_D: Volume flow of the passage in m³/h
            :param d_A: Diameter of the outlet in meters
            :param v_A: Volume flow of the outlet in m³/h
            :param direction: 'direction of passage' or 'branching direction'
            :return: loss coefficient for a T-separation
            """

            # cross_section entrance:
            A = math.pi * d ** 2 / 4
            # Inlet flow velocity
            w = (v / A).to(ureg.meter / ureg.second)

            # cross_section passageway:
            A_D = math.pi * d_D ** 2 / 4
            # Flow velocity Passage
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # cross_section Junction:
            A_A = math.pi * d_A ** 2 / 4
            # Flow velocity branch
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            if direction == 'direction of passage':
                K_1 = 183.3
                K_2 = 0.06
                K_3 = 0.17

                zeta_D = K_1 / (math.exp(w_D / w * 1 / K_2)) + K_3

                return zeta_D

            elif direction == 'branching direction':
                K_1 = 301.95
                K_2 = 0.06
                K_3 = 0.75

                zeta_D = K_1 / (math.exp(w_A / w * 1 / K_2)) + K_3

                return zeta_D
            else:
                self.logger.error('No or incorrect direction input')

        def loss_coefficient_bend_end_piece_angular(a: float, b: float, d: float, v: float, d_A: float, v_A: float):
            """
            Calculates the loss coefficient for a manifold branch (A25 - VDI 3803-6)
            :param a: Height of inlet in m
            :param b: width of inlet in m
            :param d: calculated diameter of inlet in m
            :param v: volume flow of inlet in m³/h
            :param d_A: calculated diameter of branch in m
            :param v_A: volume flow of branch in m³/h
            :return: loss coefficient for a manifold branch
            """

            # cross_section entrance:
            A = math.pi * d ** 2 / 4
            # Inlet flow velocity
            w = (v / A).to(ureg.meter / ureg.second)

            # cross_section Junction:
            A_A = math.pi * d_A ** 2 / 4
            # Flow velocity branch
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            K_1 = 0.0644
            K_2 = 0.0727
            K_3 = 0.3746
            K_4 = -3.4885

            zeta_A = (K_1 * a / b + K_2) * (w_A / w) ** (K_3 * math.log(a / b) + K_4)

            return zeta_A

        def loss_coefficient_T_separation_round(d: float, v: float, d_A: float, v_A: float):
            """
            Calculates the loss coefficient for a round T-piece (A27 - VDI 3803-6)
            :param d: calculated diameter of the inlet in meters
            :param v: volume flow of the inlet in m³/h
            :param d_A: calculated diameter of the branch in meters
            :param v_A: volume flow of the branch in m³/h
            :return: loss coefficient for a round T-piece
            """

            # cross_section entrance:
            A = math.pi * d ** 2 / 4
            # Inlet flow velocity
            w = (v / A).to(ureg.meter / ureg.second)

            # cross_section Junction:
            A_A = math.pi * d_A ** 2 / 4
            # Flow velocity branch
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            Y_0 = 0.662
            A_1 = 128.6
            t_1 = 0.0922
            A_2 = 15.13
            t_2 = 0.3138

            zeta_A = Y_0 + A_1 * math.exp(-(w_A / w) * 1 / t_1) + A_2 * math.exp(-(w_A / w) * 1 / t_2)

            return zeta_A

        def loss_coefficient_90_degree_T_merger_round(d_A: float, v_A: float, d: float, v: float):
            """
            Calculates the loss coefficient for a 90°-T-piece round (A30 - VDI 3803-6)
            :param d_A: calculated diameter of inlet in m
            :param v_A: volume flow of inlet in m³/h
            :param d: calculated diameter of main duct in m
            :param v: volume flow of main duct in m³/h
            :return: loss coefficient for a T-piece round
            """
            K_1 = 109.63
            K_2 = -35.79
            K_3 = 0.013
            K_4 = 0.144
            K_5 = 1.829
            K_6 = -0.38

            # cross-section duct:
            A = math.pi * d ** 2 / 4
            # flow velocity main duct
            w = (v / A).to(ureg.meter / ureg.second)

            # cross-section partial volume flow:
            A_A = math.pi * d_A ** 2 / 4
            # flow velocity partial volume flow
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            zeta = (K_1 / (A_A / A) + K_2) * math.exp((-w_A / w) / (K_3 / (A_A / A + K_4))) + (
                        K_5 * (1 / (A_A / A)) ** K_6)

            return zeta

        def loss_coefficient_bend_end_piece_merger_angular():
            """
            Calculates the loss coefficient for a bend end piece merger angular (A31 - VDI 3803-6)
            :return: safely estimated loss coefficient
            """
            return 0.28

        def loss_coefficient_T_merger_round(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                            v_A: float, direction: str, alpha: float = 90) -> float:
            """
            Calculates the loss coefficient for a T-merger round (A28 - VDI 3803-6)
            :param d: calculated diameter of duct in m
            :param v: volume flow of duct in m³/h
            :param d_D: calculated diameter of inlet of transit duct in m
            :param v_D: volume flow of inlet of transit duct in m³/h
            :param d_A: calculated diameter of outlet in m
            :param v_A: volume flow of outlet in m³/h
            :param direction: 'through direction' or 'inflowing direction'
            :param alpha: angle in °
            :return: loss coefficient for a T-merger round
            """

            # ToDo This function doesnt work if there is an additional air inlet/outlet at the junction, 
            #  which creates a 4 way junction instead of a t-fitting, since A_D + A_A might be smaller than A. 
            #  This case also isnt included in VDI 3803-6

            # cross-section ducts:
            A = math.pi * d ** 2 / 4
            # flow velocity ducts
            w = (v / A).to(ureg.meter / ureg.second)

            # cross-section through direction inlet:
            A_D = math.pi * d_D ** 2 / 4
            # flow velocity through direction inlet
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # cross-section junction:
            A_A = math.pi * d_A ** 2 / 4
            # flow velocity junction
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            if direction == 'through direction':
                if A_A + A_D > A or A_D == A:
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

            elif direction == 'inflowing direction':
                if A_A + A_D > A or A_D == A:
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
                    K1 = -232.1
                    K2 = -38.743
                    K3 = 0.171
                    K4 = -2.477
                    K5 = 0.597

                    zeta = (K1 * A_A / A + K2) * math.exp(-(w_A / w) / K3) + (K4 * A_A / A + K5)

                    return zeta

        def loss_coefficient_bend_merger_angular(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                                v_A: float, direction: str) -> float:
            """
            Calculates the loss coefficient for a bend merger angular (A29 - VDI 3803-6)
            :param d: calculated diameter of duct in m
            :param v: volume flow of duct in m³/h
            :param d_D: calculated diameter of inlet of transit duct in m
            :param v_D: volume flow of inlet of transit duct in m³/h
            :param d_A: calculated diameter of outlet in m
            :param v_A: volume flow of outlet in m³/h
            :param direction: 'through direction' or 'inflowing direction'
            :return: loss coefficient for a bend merger angular
            """
            # cross-section ducts:
            A = math.pi * d ** 2 / 4
            # flow velocity ducts
            w = (v / A).to(ureg.meter / ureg.second)

            # cross-section through direction inlet:
            A_D = math.pi * d_D ** 2 / 4
            # flow velocity through direction inlet
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # cross-section junction:
            A_A = math.pi * d_A ** 2 / 4
            # flow velocity junction
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            if direction == 'through direction':
                # Inputs
                input_points = np.array([
                    [1.0, 0.5],  # A_D/A, A_A/A for first row
                    [0.5, 0.5],  # A_D/A, A_A/A for second row
                    [1.0, 1.0]  # A_D/A, A_A/A for third row
                ])

                # a-values
                a2_values = np.array([-0.5604, -1.8281, -0.2756])
                a1_values = np.array([1.0706, 2.8312, 1.7256])
                a0_values = np.array([-0.2466, -0.6536, -1.8292])

                # two dimensional interpolation for a2, a1, a0
                def interpolate_2d_through_direction(A_D, A_A, A):
                    input_point = np.array([(A_D / A, A_A / A)])

                    # 'nearest' as workaround for extrapolation
                    a2 = griddata(input_points, a2_values, input_point, method='nearest')[0]
                    a1 = griddata(input_points, a1_values, input_point, method='nearest')[0]
                    a0 = griddata(input_points, a0_values, input_point, method='nearest')[0]

                    return a2, a1, a0

                a2, a1, a0 = interpolate_2d_through_direction(A_D, A_A, A)

                zeta = a2 * (1 / (w_D / w)) ** 2 + a1 * (1 / (w_D / w)) + a0

                return zeta

            elif direction == 'inflowing direction':
                input_points = np.array([
                    [1.0, 0.5],  # A_D/A, A_A/A for first row
                    [0.5, 0.5],  # A_D/A, A_A/A for second row
                    [1.0, 1.0]  # A_D/A, A_A/A for third row
                ])

                # b-values
                b2_values = np.array([-0.5769, -2.644, -0.8982])
                b1_values = np.array([0.5072, 2.7448, 2.8556])
                b0_values = np.array([0.4924, -0.1258, -1.5221])

                # two dimensional interpolation for b2, b1, b0
                def interpolate_2d_inflowing_direction(A_D, A_A, A):
                    input_point = np.array([(A_D / A, A_A / A)])

                    # 'nearest' as workaround for extrapolation
                    b2 = griddata(input_points, b2_values, input_point, method='nearest')[0]
                    b1 = griddata(input_points, b1_values, input_point, method='nearest')[0]
                    b0 = griddata(input_points, b0_values, input_point, method='nearest')[0]

                    return b2, b1, b0

                b2, b1, b0 = interpolate_2d_inflowing_direction(A_D, A_A, A)

                zeta = b2 * (1 / (w_A / w)) ** 2 + b1 * (1 / (w_A / w)) + b0

                return zeta

        position_ahu = (position_ahu[0], position_ahu[1], position_ahu[2])

        # Creation of a BFS sequence from the starting point
        bfs_edges = list(nx.edge_bfs(graph_duct_length, position_ahu))

        # For the exhaust air, the air must flow from the ceiling inlet to the AHU. Therefore, the direction of the coordinates
        # must be reversed
        ventilation_duct_exhaust = [(b, a) for a, b in bfs_edges]

        graph_duct_length_sorted = nx.DiGraph()

        # Add edges to the new graph in the BFS order
        for edge in ventilation_duct_exhaust:
            graph_duct_length_sorted.add_edge(*edge)

        ###################################
        # Pressure loss calculation
        net = pp.create_empty_network(fluid='air')

        fluid = pp.get_fluid(net)
        density = fluid.get_density(temperature=293.15) * ureg.kilogram / ureg.meter ** 3

        # Definition of the parameters for the junctions
        name_junction = [coordinate for coordinate in list(graph_duct_length_sorted.nodes())]
        index_junction = [index for index, value in enumerate(name_junction)]

        # Create a list for each coordinate axis
        x_coordinate = [coordinate[0] for coordinate in list(graph_duct_length_sorted.nodes())]
        y_coordinate = [coordinate[1] for coordinate in list(graph_duct_length_sorted.nodes())]
        z_coordinate = [coordinate[2] for coordinate in list(graph_duct_length_sorted.nodes())]

        """Create 2D coordinates"""
        # Since only 3D coordinates are available, but 3D coordinates are needed, a dict is created which
        # assigns a 2D coordinate to
        two_dim_coordinates = dict()
        position_shaft_graph = (position_shaft[0], position_shaft[1], position_shaft[2])

        # Duct from AHU to shaft
        path_ahu_to_shaft = list(nx.all_simple_paths(graph_duct_length, position_ahu, position_shaft_graph))[0]
        number_of_points_path_ahu_to_shaft = len(path_ahu_to_shaft)

        for point in path_ahu_to_shaft:
            two_dim_coordinates[point] = (-number_of_points_path_ahu_to_shaft, 0)
            number_of_points_path_ahu_to_shaft -= 1

        number_of_nodes_with_three_or_more_edges = len(
            [node for node, degree in graph_duct_length.degree() if degree >= 3])

        # Try to convert all keys into numbers and sort them
        sorted_keys = sorted(
            (key for key in dict_steiner_tree_with_duct_length.keys() if key != 'shaft'),
            key=lambda x: float(x)
        )

        y = 0  # Start y-coordinate

        for key in sorted_keys:
            graph_floor = dict_steiner_tree_with_duct_length[key]

            # TODO Pressure loss coefficient for collisions of exhaust and supply air distribution systems should be
            #  added here (
            #  - Check, if crossing point is an end node of the exhaust air distribution system -> Then do nothing
            #  - Else, calculate pressure loss coefficient
            #       - If sum of height of both systems at crossing point < height of suspended ceiling => 'Cable bridge'
            #       - Else rejuvenation and expansion of one or both

            shaft_nodes = [node for node in graph_floor.nodes()
                              if node[0] == position_shaft[0] and node[1] == position_ahu[1]][0]

            # Identify leaf nodes (nodes with degree 1)
            leaf_nodes = [node for node in graph_floor.nodes()
                            if graph_floor.degree(node) == 1 and node != shaft_nodes]

            # Calculate path from starting_node to each leaf node
            path = [nx.shortest_path(graph_floor, source=shaft_nodes, target=blatt) for blatt in leaf_nodes]

            sorted_pathes = sorted(path, key=len, reverse=True)

            x = 0

            for point in sorted_pathes[0]:
                if point not in two_dim_coordinates:
                    two_dim_coordinates[point] = (x, y)
                x += 2
            x = -2
            y += 2

            path_counter = 0
            run_again = 0

            for path in sorted_pathes[1:]:
                i = 0
                rest_length_path = len(path)
                counter_new_points = 0
                counter_points_present = 0
                for point in path:
                    if point not in two_dim_coordinates:
                        counter_new_points += 1
                        two_dim_coordinates[point] = (x, y)

                        if path_counter == 0:
                            x += 2

                        if path_counter >= 1:
                            if i >= path_counter:
                                x += 2
                            else:
                                y += 2
                                i += 2

                    elif point in two_dim_coordinates:
                        counter_points_present += 1
                        x += 2
                        rest_length_path -= 1

                y -= i
                x = -2
                path_counter += 1

            run_again = max(run_again, i) + 4
            y += run_again

        """2D-coordinates created"""

        # Create multiple junctions
        for junction in range(len(index_junction)):
            pp.create_junction(net,
                               name=str(name_junction[junction]),
                               index=index_junction[junction],
                               pn_bar=0,
                               tfluid_k=293.15,
                               geodata=two_dim_coordinates[name_junction[junction]],
                               x=x_coordinate[junction],
                               y=y_coordinate[junction],
                               height_m=z_coordinate[junction]
                               )

        # Definition of the parameters for the pipes
        name_pipe = dataframe_distribution_network['edge'].tolist()
        length_pipe = dataframe_distribution_network['duct_length'].tolist()
        from_junction = dataframe_distribution_network['starting_node'].tolist()
        to_junction = dataframe_distribution_network['target_node'].tolist()
        diameter_pipe = dataframe_distribution_network['equivalent_diameter'].tolist()

        # Adding the ducts to the network
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

        """From here, the loss coefficients of the pipes are adjusted"""
        for index, pipe in enumerate(name_pipe):

            # Neighbors of the start node
            neighbors = list(nx.all_neighbors(graph_duct_length_sorted, from_junction[index]))

            """Kinks:"""
            if len(neighbors) == 2:  # Find kinks
                incoming_edge = list(graph_duct_length_sorted.in_edges(from_junction[index]))[0]
                outgoing_edge = list(graph_duct_length_sorted.out_edges(from_junction[index]))[0]

                # calculated diameter of duct
                calculated_diameter = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == from_junction[index]) &
                    (dataframe_distribution_network['target_node'] == to_junction[index]),
                    'equivalent_diameter'
                ].iloc[0].to(ureg.meter)

                # Dimension of the duct
                dimensions_duct = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == from_junction[index]) &
                    (dataframe_distribution_network['target_node'] == to_junction[index]),
                    'cross_section'
                ].iloc[0]

                if not check_if_lines_are_aligned(incoming_edge, outgoing_edge):

                    zeta_kink = None
                    if 'Ø' in dimensions_duct:
                        duct_diameter = self.find_dimension(dimensions_duct)
                        zeta_kink = loss_coefficient_arc_round(angle=90,
                                                               mean_radius=0.75 * ureg.meter,
                                                               diameter=duct_diameter)
                        # self.logger.info(f'Zeta kink round: {zeta_kink}')

                    elif 'x' in dimensions_duct:
                        duct_width = self.find_dimension(dimensions_duct)[0].to(ureg.meter)
                        duct_height = self.find_dimension(dimensions_duct)[1].to(ureg.meter)
                        zeta_kink = loss_coefficient_arc_angular(angle=90,
                                                                 mean_radius=0.75 * ureg.meter,
                                                                 height=duct_height,
                                                                 width=duct_width,
                                                                 calculated_diameter=calculated_diameter)
                        # self.logger.info(f'Zeta kink angular: {zeta_kink}')

                    # Changing the loss_coefficient value
                    net['pipe'].at[index, 'loss_coefficient'] += zeta_kink

                    dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                      'target_node'] == to_junction[
                                                                      index], 'Zeta Kink'] = zeta_kink

            """Reductions"""
            if len(neighbors) == 2:
                duct = name_pipe[index]

                incoming_edge = list(graph_duct_length_sorted.in_edges(from_junction[index]))[0]
                outgoing_edge = list(graph_duct_length_sorted.out_edges(from_junction[index]))[0]

                """ Data for loss coefficients"""
                # diameter of inlet:
                d = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == incoming_edge[0]) &
                    (dataframe_distribution_network['target_node'] == incoming_edge[1]),
                    'equivalent_diameter'
                ].iloc[0].to(ureg.meter)

                # diameter of duct:
                d_D = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == outgoing_edge[0]) &
                    (dataframe_distribution_network['target_node'] == outgoing_edge[1]),
                    'equivalent_diameter'
                ].iloc[0].to(ureg.meter)

                if d > d_D:
                    zeta_reductions = loss_coefficient_cross_sectional_narrowing_continuous(d, d_D)

                    # self.logger.info(f'Zeta reduction: {zeta_reductions}')

                    net['pipe'].at[index, 'loss_coefficient'] += zeta_reductions

                    dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                      'target_node'] == to_junction[
                                                                      index], 'Zeta reduction'] = zeta_reductions

                elif d_D > d:
                    zeta_extension = loss_coefficient_cross_sectional_extension_continuous(d, d_D)

                    # self.logger.info(f'Zeta extension: {zeta_extension}')

                    net['pipe'].at[index, 'loss_coefficient'] += zeta_extension

                    dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                      'target_node'] == to_junction[
                                                                      index], 'Zeta extension'] = zeta_extension

            """T-Pieces"""
            if len(neighbors) == 3:  
                duct = name_pipe[index]

                # calculated diameter of duct
                d = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == from_junction[index]) &
                    (dataframe_distribution_network['target_node'] == to_junction[index]),
                    'equivalent_diameter'
                ].iloc[0].to(ureg.meter)

                # dimensions of duct
                dimensions_duct = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == from_junction[index]) &
                    (dataframe_distribution_network['target_node'] == to_junction[index]),
                    'cross_section'
                ].iloc[0]

                v = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == from_junction[index]) &
                    (dataframe_distribution_network['target_node'] == to_junction[index]),
                    'volume_flow'
                ].iloc[0]

                incoming_edge = list(graph_duct_length_sorted.in_edges(from_junction[index]))

                incoming_edge_1 = incoming_edge[0]
                incoming_edge_2 = incoming_edge[1]

                if check_if_lines_are_aligned(incoming_edge_2, duct):
                    incoming_edge_1 = incoming_edge[1]
                    incoming_edge_2 = incoming_edge[0]

                d_D = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == incoming_edge_1[0]) &
                    (dataframe_distribution_network['target_node'] == incoming_edge_1[1]),
                    'equivalent_diameter'
                ].iloc[0].to(ureg.meter)

                dimensions_incoming_edge = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == incoming_edge_1[0]) &
                    (dataframe_distribution_network['target_node'] == incoming_edge_1[1]),
                    'cross_section'
                ].iloc[0]

                v_D = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == incoming_edge_1[0]) &
                    (dataframe_distribution_network['target_node'] == incoming_edge_1[1]),
                    'volume_flow'
                ].iloc[0]

                d_A = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == incoming_edge_2[0]) &
                    (dataframe_distribution_network['target_node'] == incoming_edge_2[1]),
                    'equivalent_diameter'
                ].iloc[0].to(ureg.meter)

                dimensions_outgoing_edge = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == incoming_edge_2[0]) &
                    (dataframe_distribution_network['target_node'] == incoming_edge_2[1]),
                    'cross_section'
                ].iloc[0]

                v_A = dataframe_distribution_network.loc[
                    (dataframe_distribution_network['starting_node'] == incoming_edge_2[0]) &
                    (dataframe_distribution_network['target_node'] == incoming_edge_2[1]),
                    'volume_flow'
                ].iloc[0]

                """ Loss coefficients """
                if check_if_lines_are_aligned(incoming_edge_1, incoming_edge_2) == True:
                    # incoming edge 1 --→ ←-- incoming edge 2
                    #                       ↓
                    #                     duct

                    if 'Ø' in dimensions_duct:
                        if d_D > d_A:
                            zeta_incoming_edge_1 = loss_coefficient_90_degree_T_merger_round(
                                d_A=d_D,
                                v_A=v_D,
                                d=d,
                                v=v)

                            net['pipe'].at[
                                name_pipe.index(incoming_edge_1), 'loss_coefficient'] += zeta_incoming_edge_1
                            dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                              'edge'] == incoming_edge_1, 'Zeta T-piece'] = zeta_incoming_edge_1

                            zeta_incoming_edge_2 = loss_coefficient_90_degree_T_merger_round(
                                d_A=d_A,
                                v_A=v_A,
                                d=d,
                                v=v) + loss_coefficient_cross_sectional_extension_continuous(
                                d_A,
                                d_D)

                            net['pipe'].at[
                                name_pipe.index(incoming_edge_2), 'loss_coefficient'] += zeta_incoming_edge_2
                            dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                              'edge'] == incoming_edge_2, 'Zeta T-piece'] = zeta_incoming_edge_2

                        elif d_A > d_D:
                            zeta_incoming_edge_2 = loss_coefficient_90_degree_T_merger_round(
                                d_A=d_A,
                                v_A=v_A,
                                d=d,
                                v=v)

                            net['pipe'].at[
                                name_pipe.index(incoming_edge_2), 'loss_coefficient'] += zeta_incoming_edge_2
                            dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                              'edge'] == incoming_edge_2, 'Zeta T-piece'] = zeta_incoming_edge_2

                            zeta_incoming_edge_1 = loss_coefficient_90_degree_T_merger_round(
                                d_A=d_D,
                                v_A=v_D,
                                d=d,
                                v=v) + loss_coefficient_cross_sectional_extension_continuous(
                                d_D,
                                d_A)

                            net['pipe'].at[
                                name_pipe.index(incoming_edge_1), 'loss_coefficient'] += zeta_incoming_edge_1
                            dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                              'edge'] == incoming_edge_1, 'Zeta T-piece'] = zeta_incoming_edge_1
                    elif 'x' in dimensions_duct:
                        zeta_incoming_edge_1 = loss_coefficient_bend_end_piece_merger_angular()

                        net['pipe'].at[
                            name_pipe.index(incoming_edge_1), 'loss_coefficient'] += zeta_incoming_edge_1
                        dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                          'edge'] == incoming_edge_1, 'Zeta T-piece'] = zeta_incoming_edge_1

                        zeta_incoming_edge_2 = loss_coefficient_bend_end_piece_merger_angular()

                        net['pipe'].at[
                            name_pipe.index(incoming_edge_2), 'loss_coefficient'] += zeta_incoming_edge_2
                        dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                          'edge'] == incoming_edge_2, 'Zeta T-piece'] = zeta_incoming_edge_2

                if check_if_lines_are_aligned(incoming_edge_1, duct) == True:
                    # incoming edge 1 --→ --→ duct
                    #                       ↑
                    #               incoming edge 2
                    if 'Ø' in dimensions_duct:
                        zeta_incoming_edge_1 = loss_coefficient_T_merger_round(
                            d=d,
                            v=v,
                            d_D=d_D,
                            v_D=v_D,
                            d_A=d_A,
                            v_A=v_A,
                            direction='through direction')

                        net['pipe'].at[
                            name_pipe.index(incoming_edge_1), 'loss_coefficient'] += zeta_incoming_edge_1
                        dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                          'edge'] == incoming_edge_1, 'Zeta T-piece'] = zeta_incoming_edge_1

                        zeta_incoming_edge_2 = loss_coefficient_T_merger_round(
                            d=d,
                            v=v,
                            d_D=d_D,
                            v_D=v_D,
                            d_A=d_A,
                            v_A=v_A,
                            direction='inflowing direction')

                        net['pipe'].at[
                            name_pipe.index(incoming_edge_2), 'loss_coefficient'] += zeta_incoming_edge_2
                        dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                          'edge'] == incoming_edge_2, 'Zeta T-piece'] = zeta_incoming_edge_2

                    if 'x' in dimensions_duct:
                        zeta_incoming_edge_1 = loss_coefficient_bend_merger_angular(
                            d=d,
                            v=v,
                            d_D=d_D,
                            v_D=v_D,
                            d_A=d_A,
                            v_A=v_A,
                            direction='through direction')

                        net['pipe'].at[
                            name_pipe.index(incoming_edge_1), 'loss_coefficient'] += zeta_incoming_edge_1
                        dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                          'edge'] == incoming_edge_1, 'Zeta T-piece'] = zeta_incoming_edge_1

                        zeta_incoming_edge_2 = loss_coefficient_bend_merger_angular(
                            d=d,
                            v=v,
                            d_D=d_D,
                            v_D=v_D,
                            d_A=d_A,
                            v_A=v_A,
                            direction='inflowing direction')

                        net['pipe'].at[
                            name_pipe.index(incoming_edge_2), 'loss_coefficient'] += zeta_incoming_edge_2
                        dataframe_distribution_network.loc[dataframe_distribution_network[
                                                                          'edge'] == incoming_edge_2, 'Zeta T-piece'] = zeta_incoming_edge_2

        # Air volumes from graph
        air_volume = nx.get_node_attributes(graph_air_volume_flow, 'weight')

        # Find index of the air handling unit
        index_ahu = name_junction.index(tuple(position_ahu))
        air_volume_ahu = air_volume[position_ahu]
        mdot_kg_per_s_ahu = (air_volume_ahu * density).to(ureg.kilogram / ureg.second)

        # Create an external grid, as the visualization is then better
        pp.create_ext_grid(net, junction=index_ahu, p_bar=0, t_k=293.15, name='Air handling unit')

        # Add air handling unit to network
        pp.create_source(net,
                         mdot_kg_per_s=-mdot_kg_per_s_ahu.magnitude,
                         junction=index_ahu,
                         p_bar=0,
                         t_k=293.15,
                         name='Air handling unit')

        list_ventilation_inlets = list()

        # Adding the ventilation inlets
        for index, element in enumerate(air_volume):
            if element == tuple(position_ahu):
                continue  
            if element[0] == position_shaft[0] and element[1] == position_shaft[1]:
                continue
            if air_volume[element] == 0:
                continue
            pp.create_sink(net,
                           junction=name_junction.index(element),
                           mdot_kg_per_s=(-air_volume[element] * density).to(ureg.kilogram / ureg.second).magnitude,
                           )
            list_ventilation_inlets.append(name_junction.index(element))

        # The actual calculation is started with the pipeflow command:
        pp.pipeflow(net)

        # Determination of the pressure_loss
        greatest_pressure_loss = abs(net.res_junction['p_bar'].min())
        difference = net.res_junction['p_bar'].min()

        # Identification of the source by its name or index
        source_index = net['source'].index[net['source']['name'] == 'Air handling unit'][0]
        # Identify the external grid by its name or index
        ext_grid_index = net['ext_grid'].index[net['ext_grid']['name'] == 'Air handling unit'][0]

        # Changing the pressure value
        net['source'].at[source_index, 'p_bar'] = greatest_pressure_loss
        # Changing the pressure value
        net['ext_grid'].at[ext_grid_index, 'p_bar'] = greatest_pressure_loss

        # Recalculation
        pp.pipeflow(net)

        greatest_pressure_loss = net.res_junction['p_bar'].min()

        # Identification of the source by its name or index
        source_index = net['source'].index[net['source']['name'] == 'Air handling unit'][0]
        # Identify the external grid by its name or index
        ext_grid_index = net['ext_grid'].index[net['ext_grid']['name'] == 'Air handling unit'][0]

        greatest_pressure_loss -= 0.00100  # 30 Pa for ventilation outlet and 50 Pa for silencer + 20 reserve

        # Changing the pressure value
        net['source'].at[source_index, 'p_bar'] -= greatest_pressure_loss
        # Changing the pressure value
        net['ext_grid'].at[ext_grid_index, 'p_bar'] -= greatest_pressure_loss

        pp.pipeflow(net)

        # Results are saved in tables with the prefix res_... prefix. After the calculation, these tables are also
        #         # stored in the net container after the calculation.
        dataframe_pipes = pd.concat([net.pipe, net.res_pipe], axis=1)
        dataframe_junctions = pd.concat([net.junction, net.res_junction], axis=1)

        for duct in dataframe_distribution_network['edge']:
            p_from_pa = int(dataframe_pipes.loc[dataframe_pipes['name'] == str(duct), 'p_from_bar'].iloc[0] * 100000)
            p_to_pa = int(dataframe_pipes.loc[dataframe_pipes['name'] == str(duct), 'p_to_bar'].iloc[0] * 100000)

            dataframe_distribution_network.loc[
                dataframe_distribution_network['edge'] == duct, 'p_from_pa'] = p_from_pa
            dataframe_distribution_network.loc[
                dataframe_distribution_network['edge'] == duct, 'p_to_pa'] = p_to_pa

        pipes_excel_path = self.paths.export / 'ventilation system' / 'exhaust air' / 'pressure_loss.xlsx'

        # Export
        with pd.ExcelWriter(pipes_excel_path) as writer:
            dataframe_pipes.to_excel(writer, sheet_name='Pipes')
            dataframe_junctions.to_excel(writer, sheet_name='Junctions')

        if self.export_graphs:
            # create additional junction collections for junctions with sink connections and junctions with valve connections
            junction_sink_collection = plot.create_junction_collection(net,
                                                                       junctions=list_ventilation_inlets,
                                                                       patch_type='circle',
                                                                       size=0.1,
                                                                       color='blue')

            junction_source_collection = plot.create_junction_collection(net,
                                                                         junctions=[index_ahu],
                                                                         patch_type='circle',
                                                                         size=0.6,
                                                                         color='orange')

            # create additional pipe collection
            pipe_collection = plot.create_pipe_collection(net,
                                                          linewidths=2.,
                                                          color='grey')

            collections = [junction_sink_collection, junction_source_collection, pipe_collection]

            # Draw the collections
            fig, ax = plt.subplots(num=f'pressure loss', figsize=(20, 15))
            plot.draw_collections(collections=collections, ax=ax, axes_visible=(True, True))

            # Adds the text annotations for the pressures
            for idx, junction in enumerate(net.res_junction.index):
                pressure = net.res_junction.iloc[idx]['p_bar']  # Node pressure
                # coordinates of the nodes
                if junction in net.junction_geodata.index:
                    coords = net.junction_geodata.loc[junction, ['x', 'y']]
                    ax.text(coords['x'], coords['y'], f'{pressure * 100000:.0f} [Pa]', fontsize=8,
                            horizontalalignment='left', verticalalignment='top', rotation=-45)

            folder_path = Path(self.paths.export / 'ventilation system' / 'exhaust air')

            folder_path.mkdir(parents=True, exist_ok=True)

            total_name = 'pressure_loss' + '.png'
            path_and_name = self.paths.export / 'ventilation system' / 'exhaust air' / total_name
            plt.savefig(path_and_name)
            # plt.show()
            plt.close()

        return greatest_pressure_loss * 100000, dataframe_distribution_network

    def calculate_sheet_metal_thickness(self, pressure_loss, dimensions):
        """
        Calculates the sheet thickness depending on the channel
        :param pressure_loss: pressure loss of the system
        :param dimensions: dimensions of the duct (e.g. 400x300 or Ø60)
        :return: Sheet thickness
        """
        
        if 'Ø' in dimensions:
            diameter = self.find_dimension(dimensions).to(ureg.meter)

            # Following data according to MKK Shop Datenblatt Best. Nr. 10782 (Unit: m)
            if diameter <= 0.2 * ureg.meter:
                sheet_metal_thickness = (0.5 * ureg.millimeter).to(
                    ureg.meter)  
            elif 0.2 * ureg.meter < diameter <= 0.4 * ureg.meter:
                sheet_metal_thickness = (0.6 * ureg.millimeter).to(
                    ureg.meter)  
            elif 0.4 * ureg.meter < diameter <= 0.5 * ureg.meter:
                sheet_metal_thickness = (0.7 * ureg.millimeter).to(
                    ureg.meter)  
            elif 0.5 * ureg.meter < diameter <= 0.63 * ureg.meter:
                sheet_metal_thickness = (0.9 * ureg.millimeter).to(
                    ureg.meter)  
            elif 0.63 * ureg.meter < diameter <= 1.25 * ureg.meter:
                sheet_metal_thickness = (1.25 * ureg.millimeter).to(
                    ureg.meter)  


        elif 'x' in dimensions:
            width, height = self.find_dimension(dimensions)
            longest_edge = max(width.to(ureg.meter), height.to(ureg.meter))

            # Following data according to BerlinerLuft Gesamtkatalog Seite 53 (Unit: m)
            if pressure_loss <= 1000:
                if longest_edge <= 0.500 * ureg.meter:
                    sheet_metal_thickness = (0.6 * ureg.millimeter).to(
                        ureg.meter)  
                elif 0.500 * ureg.meter < longest_edge <= 1.000 * ureg.meter:
                    sheet_metal_thickness = (0.8 * ureg.millimeter).to(
                        ureg.meter)  
                elif 1.000 * ureg.meter < longest_edge <= 2.000 * ureg.meter:
                    sheet_metal_thickness = (1.0 * ureg.millimeter).to(
                        ureg.meter)  

            elif 1000 < pressure_loss <= 2000:
                if longest_edge <= 0.500 * ureg.meter:
                    sheet_metal_thickness = (0.7 * ureg.millimeter).to(
                        ureg.meter)  
                elif 0.500 * ureg.meter < longest_edge <= 1.000 * ureg.meter:
                    sheet_metal_thickness = (0.9 * ureg.millimeter).to(
                        ureg.meter)  
                elif 1.000 * ureg.meter < longest_edge <= 2.000 * ureg.meter:
                    sheet_metal_thickness = (1.1 * ureg.millimeter).to(
                        ureg.meter)  

            elif 2000 < pressure_loss <= 3000:
                if longest_edge <= 1.000 * ureg.meter:
                    sheet_metal_thickness = (0.95 * ureg.millimeter).to(
                        ureg.meter)  
                elif 1.000 * ureg.meter < longest_edge <= 2.000 * ureg.meter:
                    sheet_metal_thickness = (1.15 * ureg.millimeter).to(
                        ureg.meter)  

        return sheet_metal_thickness

    def connect_rooms(self, cross_section_type, suspended_ceiling_space, dataframe_rooms):

        # Determining the duct cross-section
        dataframe_rooms['duct_cross_section'] = \
            dataframe_rooms.apply(lambda row: self.dimensions_ventilation_duct(cross_section_type,
                                                                     self.necessary_cross_section(
                                                                         row['volume_flow']),
                                                                     suspended_ceiling_space),
                                  axis=1)

        # Determining the dimensions
        dataframe_rooms['duct_length'] = 2*ureg.meter
        dataframe_rooms['diameter'] = None
        dataframe_rooms['width'] = None
        dataframe_rooms['height'] = None

        for index, duct_cross_section in enumerate(dataframe_rooms['duct_cross_section']):
            if 'Ø' in duct_cross_section:
                dataframe_rooms.at[index, 'diameter'] = self.find_dimension(duct_cross_section)

            elif 'x' in duct_cross_section:
                dataframe_rooms.at[index, 'width'] = self.find_dimension(duct_cross_section)[0]
                dataframe_rooms.at[index, 'height'] = self.find_dimension(duct_cross_section)[1]

        dataframe_rooms['surface_area'] = dataframe_rooms.apply(
            lambda row: self.coat_area_ventilation_duct(
                cross_section_type,
                self.necessary_cross_section(row['volume_flow']),
                suspended_ceiling_space
            ) * row['duct_length'], axis=1)

        dataframe_rooms['equivalent_diameter'] = dataframe_rooms.apply(
            lambda row: round(self.calculated_diameter(cross_section_type,
                                                       self.necessary_cross_section(row['volume_flow']),
                                                       suspended_ceiling_space),
                              2
                              ), axis=1)

        # Determining the sheet thickness
        dataframe_rooms['sheet_thickness'] = dataframe_rooms.apply(
            lambda row: self.calculate_sheet_metal_thickness(70, row['duct_cross_section']), axis=1)

        # Check whether a silencer is required
        list_rooms_silencers = ['Bed room',
                               'Class room (school), group room (kindergarden)',
                               'Classroom',
                               'Examination- or treatment room',
                               'Exhibition room and museum conservational demands',
                               'Exhibition, congress',
                               'Foyer (theater and event venues)',
                               'Hotel room',
                               'Laboratory',
                               'Lecture hall, auditorium',
                               'Library - magazine and depot',
                               'Library - open stacks',
                               'Library - reading room',
                               'Living',
                               'Main Hall, Reception',
                               'Medical and therapeutic practices',
                               'Meeting, Conference, seminar',
                               'MultiUseComputerRoom',
                               'Restaurant',
                               'Sauna area',
                               'Spectator area (theater and event venues)',
                               'Stage (theater and event venues)',
                               'Traffic area',
                               'WC and sanitary rooms in non-residential buildings',
                               'Group Office (between 2 and 6 employees)',
                               'Open-plan Office (7 or more employees)',
                               'Single office',
                               'office_function'
                               ]
        
        dataframe_rooms['silencer'] = dataframe_rooms['room type'].apply(
            lambda x: 1 if x in list_rooms_silencers else 0)

        # volume flow controller
        dataframe_rooms['volume_flow_controller'] = 1

        # Calculation of the sheet volume
        dataframe_rooms['sheet_volume'] = dataframe_rooms['sheet_thickness'] * dataframe_rooms[
            'surface_area']

        list_dataframe_rooms_sheet_weight = [v * (7850 * ureg.kilogram / ureg.meter ** 3) for v in
                                             dataframe_rooms['sheet_volume']]
        # density steel 7850 kg/m³

        # Calculation of the sheet weight
        dataframe_rooms['sheet_weight'] = list_dataframe_rooms_sheet_weight

        return dataframe_rooms

    def calculate_material_quantities(self,
                                      pressure_loss,
                                      dataframe_rooms,
                                      dataframe_distribution_network_exhaust_air):
        """
        Calculation of necessary sheet metal of the exhaust air distribution system
        """
        dataframe_distribution_network_exhaust_air['sheet_thickness'] = dataframe_distribution_network_exhaust_air.apply(
            lambda row: self.calculate_sheet_metal_thickness(pressure_loss, row['duct_cross_section']), axis=1)

        # Determining the sheet thickness
        dataframe_distribution_network_exhaust_air['sheet_volume'] = dataframe_distribution_network_exhaust_air[
                                                                        'sheet_thickness'] * \
                                                                    dataframe_distribution_network_exhaust_air[
                                                                        'surface_area']

        list_dataframe_distribution_network_exhaust_air_sheet_weight = [v * (7850 * ureg.kilogram / ureg.meter ** 3) for
                                                                       v
                                                                       in
                                                                       dataframe_distribution_network_exhaust_air[
                                                                           'sheet_volume']]
        # density steel 7850 kg/m³

        # Calculation of the sheet weight
        dataframe_distribution_network_exhaust_air[
            'sheet_weight'] = [x.magnitude for x in list_dataframe_distribution_network_exhaust_air_sheet_weight]

        
        def cross_sectional_area_duct_insulation(row):
            """
            Calculates cross-section of insulation
            """
            # 20mm of insulation according to state of the art (Missel S. 42)
            cross_sectional_area = 0
            if 'Ø' in row['cross_section']:
                try:
                    diameter = ureg(row['diameter'])
                except AttributeError:
                    diameter = row['diameter']
                cross_sectional_area = math.pi * ((diameter + 0.04 * ureg.meter) ** 2) / 4 - math.pi * (
                        diameter ** 2) / 4
                
            elif 'x' in row['cross_section']:
                try:
                    width = ureg(row['width'])
                    height = ureg(row['height'])
                except AttributeError:
                    width = row['width']
                    height = row['height']
                cross_sectional_area = ((width + 0.04 * ureg.meter) * (height + 0.04 * ureg.meter)) - (
                        width * height) 

            return cross_sectional_area.to(ureg.meter ** 2)

        # Calculation of the insulation
        dataframe_distribution_network_exhaust_air[
            'cross_section_insulation'] = dataframe_distribution_network_exhaust_air.apply(
            cross_sectional_area_duct_insulation, axis=1)

        list_dataframe_isolation_volume_distribution_network_exhaust_air = list(dataframe_distribution_network_exhaust_air[
                                                                            'cross_section_insulation'] * \
                                                                        dataframe_distribution_network_exhaust_air[
                                                                            'duct_length'])

        dataframe_distribution_network_exhaust_air['insulation_volume'] = [x.magnitude for x in list_dataframe_isolation_volume_distribution_network_exhaust_air]

        # Export to Excel
        export_path = Path(self.paths.export, 'ventilation system', 'exhaust air')
        dataframe_distribution_network_exhaust_air.to_excel(export_path / 'dataframe_exhaust_air.xlsx', index=False)

        """
        Volume flow controllers
        """

        # Data for Trox RN Volume_flow_controller
        # https://cdn.trox.de/4ab7c57caaf55be6/3450dc5eb9d7/TVR_PD_2022_08_03_DE_de.pdf
        trox_tvr_diameter_weight = {
            'diameter': [100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter, 200 * ureg.millimeter,
                            250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter],
            'weight': [3.3 * ureg.kilogram, 3.6 * ureg.kilogram, 4.2 * ureg.kilogram, 5.1 * ureg.kilogram,
                        6.1 * ureg.kilogram, 7.2 * ureg.kilogram, 9.4 * ureg.kilogram]
        }
        df_trox_tvr_diameter_weight = pd.DataFrame(trox_tvr_diameter_weight)
       
        # Data for Trox TVJ volume flow controller
        # https://cdn.trox.de/502e3cb43dff27e2/af9a822951e1/TVJ_PD_2021_07_19_DE_de.pdf
        df_trox_tvj_diameter_weight = pd.DataFrame({
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

            'weight': [6 * ureg.kilogram, 7 * ureg.kilogram, 8 * ureg.kilogram, 9 * ureg.kilogram,
                       10 * ureg.kilogram,
                       9 * ureg.kilogram, 10 * ureg.kilogram, 11 * ureg.kilogram, 12 * ureg.kilogram,
                       13 * ureg.kilogram, 14 * ureg.kilogram, 15 * ureg.kilogram,
                       10 * ureg.kilogram, 11 * ureg.kilogram, 12 * ureg.kilogram, 13 * ureg.kilogram,
                       15 * ureg.kilogram, 16 * ureg.kilogram, 18 * ureg.kilogram, 19 * ureg.kilogram,
                       14 * ureg.kilogram, 15 * ureg.kilogram, 16 * ureg.kilogram, 17 * ureg.kilogram,
                       18 * ureg.kilogram, 21 * ureg.kilogram, 20 * ureg.kilogram]
        })

        # functions to find the weight of the necessary volume flow controller
        def weight_round_volume_flow_controller(row):
            if row['volume_flow_controller'] == 1 and 'Ø' in row['cross_section']:
                calculated_diameter = row['equivalent_diameter']
                next_diameter = df_trox_tvr_diameter_weight[
                    df_trox_tvr_diameter_weight['diameter'] >= calculated_diameter]['diameter'].min()
                return \
                    df_trox_tvr_diameter_weight[df_trox_tvr_diameter_weight['diameter'] == next_diameter][
                        'weight'].values[0]
            return None

        def weight_angular_volume_flow_controller(row):
            if row['volume_flow_controller'] == 1 and 'x' in row['cross_section']:
                width, height = row['width'], row['height']
                matching_volume_flow_controllers = df_trox_tvj_diameter_weight[
                    (df_trox_tvj_diameter_weight['width'] >= width) & (
                            df_trox_tvj_diameter_weight['height'] >= height)]
                if not matching_volume_flow_controllers.empty:
                    return matching_volume_flow_controllers.sort_values(by=['width', 'height', 'weight']).iloc[0]['weight']
            return None

        def weight_volume_flow_controller(row):
            weight_rn = weight_round_volume_flow_controller(row)
            if weight_rn is not None:
                return weight_rn
            return weight_angular_volume_flow_controller(row)

        # call function above
        dataframe_rooms['weight_volume_flow_controller'] = dataframe_rooms.apply(weight_volume_flow_controller, axis=1)


        """
        Silencer
        """

        # Data for Trox CA silencer
        # https://cdn.trox.de/97af1ba558b3669e/e3aa6ed495df/CA_PD_2023_04_26_DE_de.pdf
        trox_ca_angular_silencer_data = pd.DataFrame({
            'diameter': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter,
                            200 * ureg.millimeter, 250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter,
                            450 * ureg.millimeter, 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                            710 * ureg.millimeter, 800 * ureg.millimeter],
            'inner_diameter': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter,
                                 160 * ureg.millimeter, 200 * ureg.millimeter, 250 * ureg.millimeter,
                                 315 * ureg.millimeter, 400 * ureg.millimeter, 450 * ureg.millimeter,
                                 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                                 710 * ureg.millimeter, 800 * ureg.millimeter],
            'outer_diameter': [184 * ureg.millimeter, 204 * ureg.millimeter, 228 * ureg.millimeter,
                                  254 * ureg.millimeter, 304 * ureg.millimeter, 354 * ureg.millimeter,
                                  405 * ureg.millimeter, 505 * ureg.millimeter, 636 * ureg.millimeter,
                                  716 * ureg.millimeter, 806 * ureg.millimeter, 806 * ureg.millimeter,
                                  908 * ureg.millimeter, 1008 * ureg.millimeter]
        })

        # Calculate shell surface
        def insulation_volume_silcencer(row):
            calculated_diameter = row['equivalent_diameter']
            matching_silencers = trox_ca_angular_silencer_data[trox_ca_angular_silencer_data['diameter'] >= calculated_diameter]
            if not matching_silencers.empty:
                next_diameter = matching_silencers.iloc[0]
                inner = next_diameter['inner_diameter']
                outer = next_diameter['outer_diameter']
                # 1m of silencer corresponds to 0.88m of inner core insulation
                volume = math.pi * (outer ** 2 - inner ** 2) / 4 * 0.88 * ureg.meter
                return volume.to(ureg.meter ** 3)
            return None

        dataframe_rooms['insulation_volume_silencer'] = dataframe_rooms.apply(insulation_volume_silcencer,
                                                                                 axis=1)
        trox_ca_round_silencer_data = pd.DataFrame({
            'diameter': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter,
                            200 * ureg.millimeter, 250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter,
                            450 * ureg.millimeter, 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                            710 * ureg.millimeter, 800 * ureg.millimeter],
            'weight': [6 * ureg.kilogram, 6 * ureg.kilogram, 7 * ureg.kilogram, 8 * ureg.kilogram, 10 * ureg.kilogram,
                        12 * ureg.kilogram, 14 * ureg.kilogram, 18 * ureg.kilogram, 24 * ureg.kilogram,
                        28 * ureg.kilogram, 45 * ureg.kilogram * 2 / 3, 47 * ureg.kilogram * 2 / 3,
                        54 * ureg.kilogram * 2 / 3, 62 * ureg.kilogram * 2 / 3]
        })
        

        def weight_silencer_without_insulation(row):
            if row['silencer'] == 1:
                calculated_diameter = row['equivalent_diameter']
                matching_silencers = trox_ca_round_silencer_data[
                    trox_ca_round_silencer_data['diameter'] >= calculated_diameter]
                if not matching_silencers.empty:
                    next_diameter = matching_silencers['diameter'].min()
                    weight_silencer = \
                        trox_ca_round_silencer_data[
                            trox_ca_round_silencer_data['diameter'] == next_diameter][
                            'weight'].values[0]
                    weight_insulation_silencer = row[
                        'weight_insulation_silencer'] if 'weight_insulation_silencer' in row and not pd.isnull(
                        row['weight_insulation_silencer']) else 0
                    return weight_silencer - weight_insulation_silencer
            return None

        dataframe_rooms['weight_metal_silencer'] = dataframe_rooms.apply(weight_silencer_without_insulation,
                                                                               axis=1)

        # Calculation of insulation
        dataframe_rooms['cross_section_insulation'] = dataframe_rooms.apply(cross_sectional_area_duct_insulation,
                                                                              axis=1)

        dataframe_rooms['insulation_volume'] = dataframe_rooms['cross_section_insulation'] * dataframe_rooms[
            'duct_length']


        # Export to Excel
        dataframe_rooms.to_excel(self.paths.export / 'ventilation system' / 'exhaust air' / 'dataframe_rooms.xlsx', index=False)

        return pressure_loss, dataframe_rooms, dataframe_distribution_network_exhaust_air
