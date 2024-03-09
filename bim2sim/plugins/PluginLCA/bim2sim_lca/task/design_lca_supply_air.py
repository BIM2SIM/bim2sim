import PIL
from matplotlib import image as mpimg
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import bim2sim
import matplotlib.pyplot as plt
import networkx as nx
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
from bim2sim.utilities.common_functions import filter_instances
from decimal import Decimal, ROUND_HALF_UP
from networkx.utils import pairwise
from copy import deepcopy


class DesignSupplyLCA(ITask):
    """Design of the LCA

    Assumptions:
    Inputs: IFC Modell, Räume,

    Args:
        instances: bim2sim elements
    Returns:
        instances: bim2sim
    """
    reads = ('instances',)
    touches = ('dataframe_rooms',
               'building_shaft_supply_air',
               'graph_ventilation_duct_length_supply_air',
               'pressure_loss_supply_air',
               'dataframe_rooms_supply_air',
               'dataframe_distribution_network_supply_air',
               'dict_steiner_tree_with_air_volume_supply_air',
               'z_coordinate_list'
               )

    def run(self, instances):

        export = self.playground.sim_settings.ventilation_lca_export_supply
        building_shaft_supply_air = [41, 2.8, -2]  # building shaft supply air
        position_ahu = [25, building_shaft_supply_air[1], building_shaft_supply_air[2]]
        # y-axis of shaft and AHU must be identical
        cross_section_type = "optimal"  # Wähle zwischen round, angular und optimal
        suspended_ceiling_space = 200 * ureg.millimeter  # The available height (in [mmm]) in the suspended ceiling is
        # specified here! This corresponds to the available distance between UKRD (lower edge of raw ceiling) and OKFD
        # (upper edge of finished ceiling), see https://www.ctb.de/_wiki/swb/Massbezuege.php

        self.logger.info("Start design LCA")
        thermal_zones = filter_instances(instances, 'ThermalZone')
        thermal_zones = [tz for tz in thermal_zones if tz.ventilation_system == True]

        self.logger.info("Start calculating points of the ventilation outlet at the ceiling")
        # Here, the center points of the individual rooms are read from the IFC model and then shifted upwards by half
        # the height of the room. The point at the UKRD (lower edge of the bare ceiling) in the middle of the room is
        # therefore calculated. This is where the ventilation outlet is to be positioned later on

        (center,
         airflow_volume_per_storey,
         dict_coordinate_with_space_type,
         dataframe_rooms) = self.center(thermal_zones,
                                        building_shaft_supply_air)
        self.logger.info("Finished calculating points of the ventilation outlet at the ceiling")

        self.logger.info("Calculating the Coordinates of the ceiling hights")
        # Here the coordinates of the heights at the UKRD are calculated and summarized in a set, as these values are
        # frequently needed in the further course, so they do not have to be recalculated again and again:
        z_coordinate_list = self.calculate_z_coordinate(center)

        self.logger.info("Calculating intersection points")
        # The intersections of all points per storey are calculated here. A grid is created on the respective storey.
        # It is defined as the installation grid for the supply air. The individual points of the ventilation outlets
        # are not connected directly, but in practice and according to the standard, ventilation ducts are not laid
        # diagonally through a building
        intersection_points = self.intersection_points(center,
                                                       z_coordinate_list
                                                       )
        self.logger.info("Calculating intersection points successful")

        self.logger.info("Visualising points on the ceiling for the ventilation outlet:")
        self.visualization(center,
                            intersection_points
                            )

        self.logger.info("Visualising intersectionpoints")
        self.visualization_points_by_level(center,
                                           intersection_points,
                                           z_coordinate_list,
                                           building_shaft_supply_air,
                                           export)

        self.logger.info("Create graph for each floor")
        (dict_steiner_tree_with_duct_length,
         dict_steiner_tree_with_duct_cross_section,
         dict_steiner_tree_with_air_volume_supply_air,
         dict_steinertree_with_shell,
         dict_steiner_tree_with_calculated_cross_section) = self.create_graph(center,
                                                                              intersection_points,
                                                                              z_coordinate_list,
                                                                              building_shaft_supply_air,
                                                                              cross_section_type,
                                                                              suspended_ceiling_space,
                                                                              export
                                                                              )
        self.logger.info("Graph created for each floor")

        self.logger.info("Connect shaft and AHU")
        (dict_steiner_tree_with_duct_length,
         dict_steiner_tree_with_duct_cross_section,
         dict_steiner_tree_with_air_volume_supply_air,
         dict_steinertree_with_shell,
         dict_steiner_tree_with_calculated_cross_section) = self.rlt_shaft(z_coordinate_list,
                                                                             building_shaft_supply_air,
                                                                             airflow_volume_per_storey,
                                                                             position_ahu,
                                                                             dict_steiner_tree_with_duct_length,
                                                                             dict_steiner_tree_with_duct_cross_section,
                                                                             dict_steiner_tree_with_air_volume_supply_air,
                                                                             dict_steinertree_with_shell,
                                                                             dict_steiner_tree_with_calculated_cross_section,
                                                                             export
                                                                             )
        self.logger.info("shaft und RLT verbunden")

        self.logger.info("3D-Graph erstellen")
        (graph_ventilation_duct_length_supply_air,
         graph_luftmengen,
         graph_kanalquerschnitt,
         graph_mantelflaeche,
         graph_calculated_diameter,
         dataframe_distribution_network_supply_air) = self.drei_dimensionaler_graph(dict_steiner_tree_with_duct_length,
                                                                                    dict_steiner_tree_with_duct_cross_section,
                                                                                    dict_steiner_tree_with_air_volume_supply_air,
                                                                                    dict_steinertree_with_shell,
                                                                                    dict_steiner_tree_with_calculated_cross_section,
                                                                                    position_ahu,
                                                                                    export,
                                                                                    dict_coordinate_with_space_type)
        self.logger.info("3D-Graph erstellt")

        self.logger.info("Starte Druckverlustberechnung")
        druckverlust, dataframe_distribution_network_supply_air = self.druckverlust(dict_steiner_tree_with_duct_length,
                                                                                    z_coordinate_list,
                                                                                    position_ahu,
                                                                                    building_shaft_supply_air,
                                                                                    graph_ventilation_duct_length_supply_air,
                                                                                    graph_luftmengen,
                                                                                    graph_kanalquerschnitt,
                                                                                    graph_mantelflaeche,
                                                                                    graph_calculated_diameter,
                                                                                    export,
                                                                                    dataframe_distribution_network_supply_air
                                                                                    )
        self.logger.info("Druckverlustberechnung erfolgreich")

        self.logger.info("Starte Berechnung der Raumanbindung")
        dataframe_rooms = self.raumanbindung(cross_section_type, suspended_ceiling_space, dataframe_rooms)

        self.logger.info("Starte C02 Berechnung")
        (pressure_loss_supply_air,
         dataframe_rooms_supply_air,
         dataframe_distribution_network_supply_air) = self.co2(export,
                                                               druckverlust,
                                                               dataframe_rooms,
                                                               dataframe_distribution_network_supply_air)

        return (dataframe_rooms,
                building_shaft_supply_air,
                graph_ventilation_duct_length_supply_air,
                pressure_loss_supply_air,
                dataframe_rooms_supply_air,
                dataframe_distribution_network_supply_air,
                dict_steiner_tree_with_air_volume_supply_air,
                z_coordinate_list)

    def round_decimal(self, number, places):
        """
        Function defines how to round
        Args:
            number: Number to be rounded
            places: Number of decimal places
        Returns:
            Rounded number as float
        """

        number_decimal = Decimal(number)
        rounding_rule = Decimal('1').scaleb(-places)  # Specifies the number of decimal places
        return float(number_decimal.quantize(rounding_rule, rounding=ROUND_HALF_UP))

    def center(self, thermal_zones, building_shaft_supply_air):
        """Function calculates position of the outlet of the LVA

        Args:
            thermal_zones: thermal_zones bim2sim element
            building_shaft_supply_air: shaftkoordinate
        Returns:
            center of the room at the ceiling
        """
        # lists:
        room_ceiling_ventilation_outlet = []
        room_type = []

        for tz in thermal_zones:
            room_ceiling_ventilation_outlet.append([self.round_decimal(tz.space_center.X(), 1),
                                                    self.round_decimal(tz.space_center.Y(), 1),
                                                    self.round_decimal(tz.space_center.Z() + tz.height.magnitude / 2,
                                                                       2),
                                                    math.ceil(tz.air_flow.to(ureg.meter ** 3 / ureg.hour).magnitude) * (
                                                                ureg.meter ** 3 / ureg.hour)])
            room_type.append(tz.usage)

        # As the points are not exactly in line, although the rooms are actually next to each other, but some rooms are slightly different depths, the coordinates must be adjusted. In reality, a small shift of the ventilation outlet will not cause a major change, as the ventilation outlets are either connected with a flexible hose or directly from the main duct.
        # Z-axes
        z_axis = set()
        for i in range(len(room_ceiling_ventilation_outlet)):
            z_axis.add(room_ceiling_ventilation_outlet[i][2])

        # Creates a Dictonary sorted by Z-coordinates
        grouped_coordinates_x = {}
        for x, y, z, a in room_ceiling_ventilation_outlet:
            if z not in grouped_coordinates_x:
                grouped_coordinates_x[z] = []
            grouped_coordinates_x[z].append((x, y, z, a))

        # Adjust the coordinates in x-coordinate
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
                    adjusted_coords_x.append((self.round_decimal(x_avg, 1), y, z, a))
                    i += 1

        # Creates a Dictonary sorted by Z-coordinates
        grouped_coordinates_y = {}
        for x, y, z, a in adjusted_coords_x:
            if z not in grouped_coordinates_y:
                grouped_coordinates_y[z] = []
            grouped_coordinates_y[z].append((x, y, z, a))

        # Create new list for the moved coordinates
        adjusted_coords_y = []

        # Adjust the coordinates in y-coordinate
        for z_coord in z_axis:
            room_ceiling_ventilation_outlet = grouped_coordinates_y[z_coord]

            # Sort the coordinates by the y-coordinate
            room_ceiling_ventilation_outlet.sort(key=lambda coord: coord[1])

            # Loop through the sorted coordinates
            i = 0
            while i < len(room_ceiling_ventilation_outlet):
                current_coord = room_ceiling_ventilation_outlet[i]
                sum_y = current_coord[1]
                count = 1

                # Check whether the next coordinates are within 0.5 units of the current y-coordinate
                j = i + 1
                while j < len(room_ceiling_ventilation_outlet) and room_ceiling_ventilation_outlet[j][1] - \
                        current_coord[1] < 0.5:
                    sum_y += room_ceiling_ventilation_outlet[j][1]
                    count += 1
                    j += 1

                # Calculate the average of the y-coordinates
                average_y = sum_y / count

                # Add the coordinates with the average of the y-coordinates to the new list
                for k in range(i, j):
                    x, _, z, a = room_ceiling_ventilation_outlet[k]
                    adjusted_coords_y.append((x, self.round_decimal(average_y, 1), z, a))

                # Update the outer loop variable i to the next unprocessed index
                i = j

        room_ceiling_ventilation_outlet = adjusted_coords_y

        dict_coordinate_with_space_type = dict()
        for index, coordinate in enumerate(room_ceiling_ventilation_outlet):
            coordinate = (coordinate[0], coordinate[1], coordinate[2])
            dict_coordinate_with_space_type[coordinate] = room_type[index]

        dict_koordinate_mit_erf_luftvolumen = dict()
        for index, coordinate in enumerate(room_ceiling_ventilation_outlet):
            punkt = (coordinate[0], coordinate[1], coordinate[2])
            dict_koordinate_mit_erf_luftvolumen[punkt] = coordinate[3]

        # Here, the starting points (shaft outlets) are added for each level and the total air volume for the level is calculated. This is used for the graph

        airflow_volume_per_storey = {}

        for sublist in room_ceiling_ventilation_outlet:
            z = sublist[2]  # The third entry (index 2) is 'z'
            a = sublist[3]  # The fourth entry (index 3) is 'a'
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
        dataframe_rooms["Volume_flow"] = dataframe_rooms["coordinate"].map(dict_koordinate_mit_erf_luftvolumen)

        for z_coord in z_axis:
            room_ceiling_ventilation_outlet.append((building_shaft_supply_air[0], building_shaft_supply_air[1], z_coord,
                                                    airflow_volume_per_storey[z_coord]))

        return room_ceiling_ventilation_outlet, airflow_volume_per_storey, dict_coordinate_with_space_type, dataframe_rooms

    def calculate_z_coordinate(self, center):
        z_coordinate_list = set()
        for i in range(len(center)):
            z_coordinate_list.add(center[i][2])
        return sorted(z_coordinate_list)

    def intersection_points(self, ceiling_point, z_coordinate_list):
        # List of intersections
        intersection_points_list = []

        # intersections
        for z_value in z_coordinate_list:
            filtered_coordinates_list = [coord for coord in ceiling_point if coord[2] == z_value]

            for z_value in range(len(filtered_coordinates_list)):
                for j in range(z_value + 1, len(filtered_coordinates_list)):
                    p1 = filtered_coordinates_list[z_value]
                    p2 = filtered_coordinates_list[j]
                    # Sintersections along the X and Y axes
                    intersection_points_list.append((p2[0], p1[1], p1[2], 0))  # Intersection point on the line parallel to the
                    # X-axis of p1 and the Y-axis of p2
                    intersection_points_list.append((p1[0], p2[1], p2[2], 0))  # Intersection point on the line parallel to the
                    # Y-axis of p1 and the X-axis of p2

        intersection_points_list = list(set(intersection_points_list))  # Remove duplicate points

        # Create a new list to save the filtered items
        filtered_intersection_points = []

        # Check for each point in intersection_points whether it exists in ceiling_points
        for ip in intersection_points_list:
            if not any(cp[:3] == ip[:3] for cp in ceiling_point):
                filtered_intersection_points.append(ip)

        return filtered_intersection_points

    def visualization(self, room_ceiling_ventilation_outlet, intersection):
        """The function visualizes the points in a diagram

        Args:
            room_ceiling_ventilation_outlet: Point at the ceiling in the middle of the room
            air_flow_building:
        Returns:
            3D diagramm
        """

        # Create 3D diagram
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Customizing the layout for the legend
        plt.subplots_adjust(right=0.75)

        # add points
        coordinates1 = room_ceiling_ventilation_outlet  #Points for outlets
        coordinates2 = intersection  # intersection points

        # Extraction of the x, y and z coordinates from the two lists
        x1, y1, z1, a1 = zip(*coordinates1)
        x2, y2, z2, a2 = zip(*coordinates2)

        # Plotting the second list of coordinates in red
        ax.scatter(x2, y2, z2, c='red', marker='x', label='Intersectionpoints')

        # Plotting the first list of coordinates in blue
        ax.scatter(x1, y1, z1, c='blue', marker='D', label='Ventilation outlets')

        # Axis labels
        ax.set_xlabel('X-Achse [m]')
        ax.set_ylabel('Y-Achse [m]')
        ax.set_zlabel('Z-Achse [m]')

        # Add legend
        ax.legend(loc="center left", bbox_to_anchor=(1, 0))

        # show diagram
        # plt.show()
        plt.close()

    def visualization_points_by_level(self,
                                      center,
                                      intersection,
                                      z_coordinate_list,
                                      building_shaft_supply_air,
                                      export):
        """The function visualizes the points in a diagram
        Args:
            center: Center of the room on the ceiling
            intersection: Intersection points on the ceiling
            z_coordinate_list: Z-coordinates for each floor on the ceiling
            building_shaft_supply_air:
            export: True or False
        Returns:
           2D diagram for each storey on the ceiling
       """
        if export:
            for z_value in z_coordinate_list:
                xy_values = [(x, y) for x, y, z, a in intersection if z == z_value]
                xy_shaft = (building_shaft_supply_air[0], building_shaft_supply_air[1])
                xy_values_center = [(x, y) for x, y, z, a in center if z == z_value]

                # Remove xy_shaft from xy_values and xy_values_center
                xy_values = [xy for xy in xy_values if xy != xy_shaft]
                xy_values_center = [xy for xy in xy_values_center if xy != xy_shaft]

                plt.figure(num=f"Floor plan: {z_value}", figsize=(15, 8), dpi=200)
                plt.xlabel('X-axis in m')
                plt.ylabel('Y-axis in m')
                plt.grid(False)
                plt.subplots_adjust(left=0.1, bottom=0.1, right=0.96,
                                    top=0.96)

                # Plot for intersection points without the xy_shaft coordinate
                plt.scatter(*zip(*xy_values), color="r", marker='o', label="intersection points")

                # plot shaft
                plt.scatter(xy_shaft[0], xy_shaft[1], color="g", marker='s', label="shaft")

                # Plot for ventilation outlets without the xy_shaft coordinate
                plt.scatter(*zip(*xy_values_center), color="b", marker='D', label="ventilation outlet")

                plt.title(f'height: {z_value}')
                plt.legend(loc="best")

                # Set the path for the new folder
                folder_path = Path(self.paths.export / 'supply_air' / "floor_plan")

                # create folder
                folder_path.mkdir(parents=True, exist_ok=True)

                # save graph
                total_name = "Grundriss Z " + f"{z_value}" + ".png"
                path_and_name = self.paths.export / 'supply_air' / "floor_plan" / total_name
                plt.savefig(path_and_name)

                plt.close()

                # plt.show()

    def visualisierung_graph(self,
                             G,
                             steiner_baum,
                             z_value,
                             coordinates_without_airflow,
                             filtered_coords_ceiling_without_airflow,
                             filtered_coords_intersection_without_airflow,
                             name,
                             unit_edge,
                             total_coat_area,
                             building_shaft_supply_air
                             ):
        """
        :param G: Graph
        :param steiner_baum: Steinerbaum
        :param z_value: Z-Achse
        :param coordinates_without_airflow: Schnittpunkte
        :param filtered_coords_ceiling_without_airflow: Koordinaten ohne Volume_flow
        :param filtered_coords_intersection_without_airflow: Schnittpunkte ohne Volume_flow
        :param name: Diagrammbezeichnung
        :param unit_edge: Einheit der Kante für Legende Diagramm
        :param total_coat_area: gesamte Fläche des Kanalmantels
        """
        # visualization
        plt.figure(figsize=(15, 8), dpi=200)
        plt.xlabel('X-Achse [m]')
        plt.ylabel('Y-Achse [m]')
        plt.title(name + f", Z: {z_value}")
        plt.grid(False)
        plt.subplots_adjust(left=0.04, bottom=0.04, right=0.96,
                            top=0.96)  # Removes the border around the diagram, diagram quasi full screen
        # plt.axis('equal') # Ensures that the plot is true to scale

        # Define node positions
        pos = {node: (node[0], node[1]) for node in coordinates_without_airflow}

        # Entry to be deleted
        entry_to_remove = (building_shaft_supply_air[0], building_shaft_supply_air[1], z_value)

        # Filter the list to remove all entries that match entry_to_remove
        filtered_coords_ceiling_without_airflow = [entry for entry in filtered_coords_ceiling_without_airflow if
                                                   entry != entry_to_remove]

        # draw nodes
        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=filtered_coords_ceiling_without_airflow,
                               node_shape='D',
                               node_color='blue',
                               node_size=300)
        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=[(building_shaft_supply_air[0], building_shaft_supply_air[1], z_value)],
                               node_shape="s",
                               node_color="green",
                               node_size=400)

        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=filtered_coords_intersection_without_airflow,
                               node_shape='o',
                               node_color='red',
                               node_size=50)

        # draw edges
        nx.draw_networkx_edges(G, pos, width=1)
        nx.draw_networkx_edges(steiner_baum, pos, width=4, style="-", edge_color="blue")

        # edge weight
        edge_labels = nx.get_edge_attributes(steiner_baum, 'weight')
        try:
            edge_labels_without_unit = {key: float(value.magnitude) for key, value in edge_labels.items()}
        except AttributeError:
            edge_labels_without_unit = edge_labels
        for key, value in edge_labels_without_unit.items():
            try:
                if "Ø" in value:
                    # Remove the unit and retain the number after "Ø"
                    number = value.split("Ø")[1].split()[0]  # Takes the part after "Ø" and then the number before the unit
                    edge_labels_without_unit[key] = f"Ø{number}"
                elif "x" in value:
                    # Separating the dimensions and removing the units
                    zahlen = value.split(" x ")
                    width = zahlen[0].split()[0]
                    height = zahlen[1].split()[0]
                    edge_labels_without_unit[key] = f"{width} x {height}"
            except:
                None

        nx.draw_networkx_edge_labels(steiner_baum, pos, edge_labels=edge_labels_without_unit, font_size=8,
                                     font_weight=10,
                                     rotate=False)

        # show node weight
        node_labels = nx.get_node_attributes(G, 'weight')
        node_labels_without_unit = dict()
        for key, value in node_labels.items():
            try:
                node_labels_without_unit[key] = f"{value.magnitude}"
            except AttributeError:
                node_labels_without_unit[key] = ""
        nx.draw_networkx_labels(G, pos, labels=node_labels_without_unit, font_size=8, font_color="white")

        # Create legend
        legend_ceiling = plt.Line2D([0], [0], marker='D', color='w', label='Ceiling outlet in m³ per h',
                                    markerfacecolor='blue',
                                    markersize=10)
        legend_intersection = plt.Line2D([0], [0], marker='o', color='w', label='intersection point',
                                         markerfacecolor='red', markersize=6)
        legend_shaft = plt.Line2D([0], [0], marker='s', color='w', label='shaft',
                                  markerfacecolor='green', markersize=10)
        legend_steiner_edge = plt.Line2D([0], [0], color='blue', lw=4, linestyle='-.',
                                         label=f'steiner edge in {unit_edge}')

        # Check whether the lateral surface is available
        if total_coat_area is not False:
            legend_coat_area = plt.Line2D([0], [0], lw=0, label=f'surface area: {total_coat_area} [m²]')

            # Add legend to the diagram, including the lateral surface
            plt.legend(
                handles=[legend_ceiling, legend_intersection, legend_shaft, legend_steiner_edge, legend_coat_area],
                loc='best')
        else:
            # Add legend to the diagram without the lateral surface
            plt.legend(handles=[legend_ceiling, legend_intersection, legend_shaft, legend_steiner_edge],
                       loc='best')  # , bbox_to_anchor=(1.1, 0.5)

        # Set the path for the new folder
        folder_path = Path(self.paths.export / 'supply_air' / f"Z_{z_value}")

        # create folder
        folder_path.mkdir(parents=True, exist_ok=True)

        # save graph
        total_name = name + "_Zuluft_Z" + f"{z_value}" + ".png"
        path_and_name = self.paths.export / 'supply_air' / f"Z_{z_value}" / total_name
        plt.savefig(path_and_name)

        # how graph
        # plt.show()

        # close graph
        plt.close()

    def visualization_graph_new(self,
                                 steiner_baum,
                                 coordinates_without_airflow,
                                 z_value,
                                 name,
                                 unit_edge
                                 ):
        """
        creates a visualization of the graphimages with images
        :param steiner_baum: steiner_tree
        :param coordinates_without_airflow: coordinates without airflow
        :param z_value: z-coordinates
        :param name: name of the plot
        :param unit_edge: unit of the edge
        :return: plot
        """

        # Image URLs for graph nodes
        icons = {
            "Supply air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Supply air diffuser.png'),
            "Exhaust air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Exhaust air diffuser.png'),
            "gps_not_fixed": Path(
                bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/gps_not_fixed.png'),
            "north": Path(
                bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/north.png'),
            "bar_blue": Path(
                bim2sim.__file__).parent.parent / (
                            'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/bar_blue.png'),
            "rlt": Path(
                bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/rlt.png')
        }
        # Load images
        images = {k: PIL.Image.open(fname) for k, fname in icons.items()}

        # Plot settings
        fig, ax = plt.subplots(figsize=(18, 8), dpi=300)
        fig.subplots_adjust(left=0.03, bottom=0.03, right=0.97,
                            top=0.97)  # Removes the border around the diagram, diagram virtually full screen
        ax.set_xlabel('X-axis in m')
        ax.set_ylabel('Y-axis in m')
        ax.set_title(name + f", Z: {z_value}")

        # Node positions
        pos = {node: (node[0], node[1]) for node in coordinates_without_airflow}

        # Note: the min_source/target_margin kwargs only work with FancyArrowPatch objects.
        # Force the use of FancyArrowPatch for edge drawing by setting `arrows=True`,
        # but suppress arrowheads with `arrowstyle="-"`
        nx.draw_networkx_edges(
            steiner_baum,
            pos=pos,
            edge_color="blue",
            ax=ax,
            arrows=True,
            arrowstyle="-",
            min_source_margin=0,
            min_target_margin=0,
        )

        # edge weight
        edge_labels = nx.get_edge_attributes(steiner_baum, 'weight')
        try:
            edge_labels_without_unit = {key: float(value.magnitude) for key, value in edge_labels.items()}
        except AttributeError:
            edge_labels_without_unit = edge_labels
        for key, value in edge_labels_without_unit.items():
            try:
                if "Ø" in value:
                    # Remove the unit and retain the number after "Ø"
                    number = value.split("Ø")[1].split()[0]  # Takes the part after "Ø" and then the number before the unit
                    edge_labels_without_unit[key] = f"Ø{number}"
                elif "x" in value:
                    # Separating the dimensions and removing the units
                    zahlen = value.split(" x ")
                    width = zahlen[0].split()[0]
                    height = zahlen[1].split()[0]
                    edge_labels_without_unit[key] = f"{width} x {height}"
            except:
                None

        nx.draw_networkx_edge_labels(steiner_baum, pos, edge_labels=edge_labels_without_unit, font_size=8,
                                     font_weight=10,
                                     rotate=False)

        # Drawing the pictures first
        for n in steiner_baum.nodes:
            if steiner_baum.nodes[n]["image"] == images["gps_not_fixed"]:
                # Transform from data coordinates (scaled between xlim and ylim) to display coordinates
                tr_figure = ax.transData.transform
                # Transform from display to figure coordinates
                tr_axes = fig.transFigure.inverted().transform

                # Select the size of the image (relative to the X axis)
                icon_size = (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.0003
                icon_center = icon_size / 2.0
                xf, yf = tr_figure(pos[n])
                xa, ya = tr_axes((xf, yf))
                # Image positioning
                a = plt.axes([xa - icon_center, ya - icon_center, icon_size, icon_size], frameon=False)
                a.imshow(steiner_baum.nodes[n]["image"])
                a.axis("off")
            else:
                # Transform from data coordinates (scaled between xlim and ylim) to display coordinates
                tr_figure = ax.transData.transform
                # Transform from display to figure coordinates
                tr_axes = fig.transFigure.inverted().transform

                # Select the size of the image (relative to the X axis)
                icon_size = (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.0008
                icon_center = icon_size / 2.0
                xf, yf = tr_figure(pos[n])
                xa, ya = tr_axes((xf, yf))
                # Image positioning
                a = plt.axes([xa - icon_center, ya - icon_center, icon_size, icon_size], frameon=False)
                a.imshow(steiner_baum.nodes[n]["image"])
                a.axis("off")

        node_labels = nx.get_node_attributes(steiner_baum, 'weight')
        node_labels_without_unit = dict()
        for key, value in node_labels.items():
            try:
                node_labels_without_unit[key] = f"{value.magnitude} m³/h"
            except AttributeError:
                node_labels_without_unit[key] = ""

        # node weight
        for n in steiner_baum.nodes:
            xf, yf = tr_figure(pos[n])
            xa, ya = tr_axes((xf, yf))
            # Add some offset to make the labels visible
            ax.text(xa + 0.02, ya + 0.03, f"{node_labels_without_unit[n]}",
                    transform=fig.transFigure, ha='center', va='center',
                    fontsize=8, color="black",
                    bbox=dict(facecolor='white', alpha=0.5, edgecolor='black', boxstyle='round,pad=0.2'))

        path_bar = Path(
            bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/bar_blue.png')
        path_Supply_air_diffuser = Path(
            bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Supply air diffuser.png')
        path_Exhaust_air_diffuser = Path(
            bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Exhaust air diffuser.png')
        path_north = Path(
            bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/north.png')
        path_gps_not_fixed = Path(
            bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/gps_not_fixed.png')
        path_rlt = Path(
            bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/rlt.png')

        # legend images
        legend_ax0 = fig.add_axes(
            [0.85, 0.92, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax0.axis('off')  # No axes for the legend axis
        img0 = mpimg.imread(path_bar)
        legend_ax0.imshow(img0)
        legend_ax0.text(1.05, 0.5, f'Kante {unit_edge}', transform=legend_ax0.transAxes, ha='left', va='center')

        legend_ax1 = fig.add_axes(
            [0.85, 0.89, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax1.axis('off')  # No axes for the legend axis
        img1 = mpimg.imread(path_Supply_air_diffuser)
        legend_ax1.imshow(img1)
        legend_ax1.text(1.05, 0.5, 'Supply air outlet', transform=legend_ax1.transAxes, ha='left', va='center')

        legend_ax2 = fig.add_axes(
            [0.85, 0.86, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax2.axis('off')  # No axes for the legend axis
        img2 = mpimg.imread(path_Exhaust_air_diffuser)
        legend_ax2.imshow(img2)
        legend_ax2.text(1.05, 0.5, 'Exhaust air diffuser', transform=legend_ax2.transAxes, ha='left', va='center')

        legend_ax3 = fig.add_axes(
            [0.85, 0.83, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax3.axis('off')  # No axes for the legend axis
        img3 = mpimg.imread(path_north)
        legend_ax3.imshow(img3)
        legend_ax3.text(1.05, 0.5, 'shaft', transform=legend_ax3.transAxes, ha='left', va='center')

        legend_ax4 = fig.add_axes(
            [0.85, 0.8, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax4.axis('off')  # No axes for the legend axis
        img4 = mpimg.imread(path_gps_not_fixed)
        legend_ax4.imshow(img4)
        legend_ax4.text(1.05, 0.5, 'steiner node', transform=legend_ax4.transAxes, ha='left', va='center')

        # Set the path for the new folder
        folder_path = Path(self.paths.export / 'supply_air' / f"Z_{z_value}")

        # Create folder
        folder_path.mkdir(parents=True, exist_ok=True)

        # save graph
        total_name = name + "_Zuluft_Z " + f"{z_value}" + ".png"
        path_and_name = self.paths.export / 'supply_air' / f"Z_{z_value}" / total_name
        plt.savefig(path_and_name)

        # plt.show()

        plt.close()

    def required_ventilation_duct_cross_section(self, volume_flow):
        """
                The required channel cross-section is calculated here depending on the Volume_flow
                Args:
                    volume_flow: Volume flow
                Returns:
                    duct_cross_section: Duct cross section in m²
                """

        # The duct cross-section is determined here:
        # See example on page 10 "Guide to the design of ventilation systems" www.aerotechnik.de

        duct_cross_section = (volume_flow / (5 * (ureg.meter / ureg.second))).to('meter**2')
        return duct_cross_section

    # Dimensions according to EN 1505 table 1
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

    def dimensions_ventilation_duct(self, querschnitts_art, duct_cross_section, suspended_ceiling_space=2000 * ureg.millimeter):
        """
        Args:
            querschnitts_art: round oder angular
            duct_cross_section: erforderlicher duct_cross_section in m²
            suspended_ceiling_space:
        Returns:
             Durchmesser oder Kantenlängen a x b des Kanals
        """

        if querschnitts_art == "round":
            return self.dimensions_round_cross_section(duct_cross_section, suspended_ceiling_space)

        elif querschnitts_art == "angular":
            return self.dimensions_angular_cross_section(duct_cross_section)

        elif querschnitts_art == "optimal":
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

    def coat_area_ventilation_duct(self, querschnitts_art, duct_cross_section, suspended_ceiling_space=2000):
        """

        :param querschnitts_art: round, angular oder optimal
        :param duct_cross_section: Querschnittsfläche des Kanals im jeweiligen Abschnitt
        :param suspended_ceiling_space: Luftraum zwischen Abhangdecke und Rohdecke
        :return: Mantelfläche pro Meter des Kanals
        """

        if querschnitts_art == "round":
            return (math.pi * self.diameter_round_channel(duct_cross_section)).to(ureg.meter)

        elif querschnitts_art == "angular":
            return self.coat_area_angular_ventilation_duct(duct_cross_section)

        elif querschnitts_art == "optimal":
            if self.diameter_round_channel(duct_cross_section) <= suspended_ceiling_space:
                return (math.pi * self.diameter_round_channel(duct_cross_section)).to(ureg.meter)
            else:
                return self.coat_area_angular_ventilation_duct(duct_cross_section, suspended_ceiling_space)

    def calculated_diameter(self, querschnitts_art, duct_cross_section, suspended_ceiling_space=2000):
        """

        :param querschnitts_art: round, angular oder optimal
        :param duct_cross_section: Querschnittsfläche des Kanals im jeweiligen Abschnitt
        :param suspended_ceiling_space: Luftraum zwischen Abhangdecke und Rohdecke
        :return: rechnerischer Durchmesser des Kanals
        """

        if querschnitts_art == "round":
            return self.diameter_round_channel(duct_cross_section)

        elif querschnitts_art == "angular":
            return self.equivalent_diameter(duct_cross_section)

        elif querschnitts_art == "optimal":
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

    def plot_shaft(self, graph, name):

        # Plot
        plt.figure(dpi=450)
        plt.xlabel('X-Achse [m]')
        plt.ylabel('Z-Achse [m]')
        plt.title(name)
        plt.grid(False)
        plt.subplots_adjust(left=0.05, bottom=0.05, right=0.95,
                            top=0.95)  # Removes the border around the diagram, diagram virtually full screen
        plt.axis('equal')  # Ensures the plot is true to scale

        # Define positions of the nodes
        pos = {node: (node[0], node[2]) for node in graph.nodes()}

        # Draw nodes
        nx.draw_networkx_nodes(graph,
                               pos,
                               nodelist=graph.nodes(),
                               node_shape='D',
                               node_color='blue',
                               node_size=150)

        # draw edges
        nx.draw_networkx_edges(graph, pos, width=1)

        # show edge weight
        edge_labels = nx.get_edge_attributes(graph, 'weight')
        nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=4, font_weight=4,
                                     rotate=False)

        # show node weight
        node_labels = nx.get_node_attributes(graph, 'weight')
        nx.draw_networkx_labels(graph, pos, labels=node_labels, font_size=4, font_color="white")

        # legend node
        legend_knoten = plt.Line2D([0], [0], marker='D', color='w', label='Knoten',
                                   markerfacecolor='blue', markersize=8)

        # add legend to plot
        plt.legend(handles=[legend_knoten], loc='best')

        # Set the path for the new folder
        folder_path = Path(self.paths.export / 'supply_air' / "shaft")

        # Create folder
        folder_path.mkdir(parents=True, exist_ok=True)

        # save graph
        total_name = name + ".png"
        path_and_name = self.paths.export / 'supply_air' / "shaft" / total_name
        plt.savefig(path_and_name)

        # show graph
        # plt.show()

        # close plot
        plt.close()

    def plot_shaft_neu(self, steiner_baum,
                         name,
                         unit_edge
                         ):

        # Image URLs for graph nodes
        icons = {
            "Supply air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Supply air diffuser.png'),
            "Exhaust air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Exhaust air diffuser.png'),
            "gps_not_fixed": Path(
                bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/gps_not_fixed.png'),
            "north": Path(
                bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/north.png'),
            "bar_blue": Path(
                bim2sim.__file__).parent.parent / (
                            'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/bar_blue.png'),
            "rlt": Path(
                bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/rlt.png')
        }
        # Load images
        images = {k: PIL.Image.open(fname) for k, fname in icons.items()}

        # Plot settings
        fig, ax = plt.subplots(figsize=(12, 10), dpi=300)
        fig.subplots_adjust(left=0.03, bottom=0.03, right=0.97,
                            top=0.97)  # Entfernt den Rand um das Diagramm, Diagramm quasi Vollbild
        ax.set_xlabel('X-Achse [m]')
        ax.set_ylabel('Y-Achse [m]')
        ax.set_title(name)

        # Node positions
        pos = {node: (node[0], node[2]) for node in steiner_baum.nodes()}

        # Note: the min_source/target_margin kwargs only work with FancyArrowPatch objects.
        # Force the use of FancyArrowPatch for edge drawing by setting `arrows=True`,
        # but suppress arrowheads with `arrowstyle="-"`
        nx.draw_networkx_edges(
            steiner_baum,
            pos=pos,
            edge_color="blue",
            ax=ax,
            arrows=True,
            arrowstyle="-",
            min_source_margin=0,
            min_target_margin=0,
        )

        # edge weight
        edge_labels = nx.get_edge_attributes(steiner_baum, 'weight')
        try:
            edge_labels_without_unit = {key: float(value.magnitude) for key, value in edge_labels.items()}
        except AttributeError:
            edge_labels_without_unit = edge_labels
        nx.draw_networkx_edge_labels(steiner_baum, pos, edge_labels=edge_labels_without_unit, font_size=8,
                                     font_weight=10,
                                     rotate=False)

        # draw pictures
        for n in steiner_baum.nodes:
            if steiner_baum.nodes[n]["image"] == images["rlt"]:
                # Transform from data coordinates (scaled between xlim and ylim) to display coordinates
                tr_figure = ax.transData.transform
                # Transform from display to figure coordinates
                tr_axes = fig.transFigure.inverted().transform

                # Select the size of the image (relative to the X axis)
                icon_size = (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.003
                icon_center = icon_size / 2.0
                xf, yf = tr_figure(pos[n])
                xa, ya = tr_axes((xf, yf))

                # Image positioning
                a = plt.axes([xa - icon_center, ya - icon_center, 5 * icon_size, 5 * icon_size], frameon=False)
                a.imshow(steiner_baum.nodes[n]["image"])
                a.axis("off")
            else:
                # Transform from data coordinates (scaled between xlim and ylim) to display coordinates
                tr_figure = ax.transData.transform
                # Transform from display to figure coordinates
                tr_axes = fig.transFigure.inverted().transform

                # Select the size of the image (relative to the X axis)
                icon_size = (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.0008
                icon_center = icon_size / 2.0
                xf, yf = tr_figure(pos[n])
                xa, ya = tr_axes((xf, yf))
                # Image positioning
                a = plt.axes([xa - icon_center, ya - icon_center, icon_size, icon_size], frameon=False)
                a.imshow(steiner_baum.nodes[n]["image"])
                a.axis("off")

        node_labels = nx.get_node_attributes(steiner_baum, 'weight')
        node_labels_without_unit = dict()
        for key, value in node_labels.items():
            try:
                node_labels_without_unit[key] = f"{value.magnitude} m³"
            except AttributeError:
                node_labels_without_unit[key] = ""

        # node weight
        for n in steiner_baum.nodes:
            xf, yf = tr_figure(pos[n])
            xa, ya = tr_axes((xf, yf))
            # add offset
            ax.text(xa + 0.03, ya + 0.04, f"{node_labels_without_unit[n]}",
                    transform=fig.transFigure, ha='center', va='center',
                    fontsize=8, color="black",
                    bbox=dict(facecolor='white', alpha=0.5, edgecolor='black', boxstyle='round,pad=0.2'))

        path_bar = Path(
            bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/bar_blue.png')
        path_Supply_air_diffuser = Path(
            bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Zuluftdurchlass.png')
        path_Exhaust_air_diffuser = Path(
            bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Abluftdurchlass.png')
        path_north = Path(
            bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/north.png')
        path_gps_not_fixed = Path(
            bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/gps_not_fixed.png')
        path_rlt = Path(
            bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/rlt.png')

        # legend images
        legend_ax0 = fig.add_axes(
            [1 - 0.85, 0.92, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax0.axis('off')  # No axes for the legend axis
        img0 = mpimg.imread(path_bar)
        legend_ax0.imshow(img0)
        legend_ax0.text(1.05, 0.5, f'edge {unit_edge}', transform=legend_ax0.transAxes, ha='left', va='center')

        legend_ax1 = fig.add_axes(
            [1 - 0.85, 0.89, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax1.axis('off')  # No axes for the legend axis
        img1 = mpimg.imread(path_Supply_air_diffuser)
        legend_ax1.imshow(img1)
        legend_ax1.text(1.05, 0.5, 'Supply air diffuser', transform=legend_ax1.transAxes, ha='left', va='center')

        legend_ax2 = fig.add_axes(
            [1 - 0.85, 0.86, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax2.axis('off')  # No axes for the legend axis
        img2 = mpimg.imread(path_Exhaust_air_diffuser)
        legend_ax2.imshow(img2)
        legend_ax2.text(1.05, 0.5, 'Exhaust air diffuser', transform=legend_ax2.transAxes, ha='left', va='center')

        legend_ax3 = fig.add_axes(
            [1 - 0.85, 0.83, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax3.axis('off')  # No axes for the legend axis
        img3 = mpimg.imread(path_north)
        legend_ax3.imshow(img3)
        legend_ax3.text(1.05, 0.5, 'shaft', transform=legend_ax3.transAxes, ha='left', va='center')

        legend_ax4 = fig.add_axes(
            [1 - 0.85, 0.8, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax4.axis('off')  # No axes for the legend axis
        img4 = mpimg.imread(path_gps_not_fixed)
        legend_ax4.imshow(img4)
        legend_ax4.text(1.05, 0.5, 'steiner node', transform=legend_ax4.transAxes, ha='left', va='center')

        legend_ax5 = fig.add_axes(
            [1 - 0.85, 0.77, 0.02, 0.02])  # Position: [left, bottom, width, height] in figure coordinates
        legend_ax5.axis('off')  # No axes for the legend axis
        img5 = mpimg.imread(path_rlt)
        legend_ax5.imshow(img5)
        legend_ax5.text(1.05, 0.5, 'Air handling unit', transform=legend_ax5.transAxes, ha='left', va='center')

        # Set the path for the new folder
        folder_path = Path(self.paths.export / 'supply_air' / "shaft")

        # Create folder
        folder_path.mkdir(parents=True, exist_ok=True)

        # save graph
        total_name = name + ".png"
        path_and_name = self.paths.export / 'supply_air' / "shaft" / total_name
        plt.savefig(path_and_name)

        # plt.show()

        plt.close()

    def find_leaves(self, spanning_tree):
        leaves = []
        for node in spanning_tree:
            if len(spanning_tree[node]) == 1:  # A leaf has only one neighbor
                leaves.append(node)
        return leaves

    def create_graph(self, ceiling_point, intersection_points, z_coordinate_list, starting_point,
                     cross_section_type, suspended_ceiling_space, export_graphen):
        """The function creates a connected graph for each floor
        Args:
           ceiling_point: Point at the ceiling in the middle of the room
           intersection points: intersection points at the ceiling
           z_coordinate_list: z coordinates for each storey ceiling
           starting_point: Coordinate of the shaft
           cross_section_type: round, angular oder optimal
           suspended_ceiling_space: verfügbare Höhe (in [mmm]) in der Zwischendecke angegeben! Diese
            entspricht dem verfügbaren Abstand zwischen UKRD (Unterkante Rohdecke) und OKFD (Oberkante Fertigdecke),
            siehe https://www.ctb.de/_wiki/swb/Massbezuege.php
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

        # Image URLs for graph nodes
        icons = {
            "Supply air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Zuluftdurchlass.png'),
            "Exhaust air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Abluftdurchlass.png'),
            "gps_not_fixed": Path(
                bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/gps_not_fixed.png'),
            "north": Path(
                bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/north.png'),
            "bar_blue": Path(
                bim2sim.__file__).parent.parent / (
                            'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/bar_blue.png'),
            "rlt": Path(
                bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/rlt.png')
        }
        # Load images
        images = {k: PIL.Image.open(fname) for k, fname in icons.items()}

        # Empty dictonaries for the individual heights are created here:
        dict_steinerbaum_mit_leitungslaenge = {key: None for key in z_coordinate_list}
        dict_steinerbaum_mit_luftmengen = {key: None for key in z_coordinate_list}
        dict_steinerbaum_mit_kanalquerschnitt = {key: None for key in z_coordinate_list}
        dict_steinerbaum_mit_rechnerischem_querschnitt = {key: None for key in z_coordinate_list}
        dict_steinertree_with_shell = {key: None for key in z_coordinate_list}

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
                if x == starting_point[0] and y == starting_point[1]:
                    G.add_node((x, y, z), weight=a, image=images["north"])
                else:
                    G.add_node((x, y, z), weight=a, image=images["Supply air diffuser"])
                if a > 0:  # Bedingung, um Terminals zu bestimmen (z.B. Gewicht > 0)
                    terminals.append((x, y, z))

            for x, y, z, a in filtered_coords_intersection:
                G.add_node((x, y, z), weight=0, image=images["gps_not_fixed"])

            # Kanten entlang der X-Achse hinzufügen
            unique_coords = set(coord[0] for coord in coordinates_without_airflow)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in coordinates_without_airflow if coord[0] == u],
                                            key=lambda c: c[1 - 0])
                for i in range(len(nodes_on_same_axis) - 1):
                    gewicht_kante_y = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], weight=gewicht_kante_y)

            # Kanten entlang der Y-Achse hinzufügen
            unique_coords = set(coord[1] for coord in coordinates_without_airflow)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in coordinates_without_airflow if coord[1] == u],
                                            key=lambda c: c[1 - 1])
                for i in range(len(nodes_on_same_axis) - 1):
                    gewicht_kante_x = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], weight=gewicht_kante_x)

            # Erstellung des Steinerbaums
            steiner_baum = steiner_tree(G, terminals, weight="weight")

            if export_graphen == True:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum 0. Optimierung",
                                          unit_edge="m",
                                          total_coat_area=False,
                                          building_shaft_supply_air=starting_point
                                          )

            # if export_graphen == True:
            #     self.visualization_graph_new(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum 0. Optimierung",
            #                                   unit_edge="[m]"
            #                                   )

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
                tree.add_edge(kante[0], kante[1], weight=self.euclidean_distance(kante[0], kante[1]))

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
            steiner_baum = steiner_tree(G, terminals, weight="weight")

            if export_graphen == True:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum 1. Optimierung",
                                          unit_edge="m",
                                          total_coat_area=False,
                                          building_shaft_supply_air=starting_point
                                          )

            # if export_graphen == True:
            #     self.visualization_graph_new(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum 1. Optimierung",
            #                                   unit_edge="m"
            #                                   )

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

                    if kink_in_ventilation_duct(lueftungsauslass_zu_eins) == False and kink_in_ventilation_duct(
                            lueftungsauslass_zu_zwei) == False:
                        None
                    elif kink_in_ventilation_duct(lueftungsauslass_zu_eins) == True:
                        if lueftungsauslass_zu_eins != [] and lueftungsauslass_zu_zwei != []:
                            if lueftungsauslass[0] == lueftungsauslass_zu_zwei[0][1][0]:
                                terminals.append((lueftungsauslass[0], nachbarauslass_eins[1], z_value))
                            elif lueftungsauslass[1] == lueftungsauslass_zu_zwei[0][1][1]:
                                terminals.append((nachbarauslass_eins[0], lueftungsauslass[1], z_value))
                    elif kink_in_ventilation_duct(lueftungsauslass_zu_zwei) == True:
                        if lueftungsauslass_zu_eins != [] and lueftungsauslass_zu_zwei != []:
                            if lueftungsauslass[0] == lueftungsauslass_zu_eins[0][1][0]:
                                terminals.append((lueftungsauslass[0], nachbarauslass_zwei[1], z_value))
                            elif lueftungsauslass[1] == lueftungsauslass_zu_eins[0][1][1]:
                                terminals.append((nachbarauslass_zwei[0], lueftungsauslass[1], z_value))

            # Erstellung des neuen Steinerbaums
            steiner_baum = steiner_tree(G, terminals, weight="weight")

            if export_graphen == True:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum 2. Optimierung",
                                          unit_edge="m",
                                          total_coat_area=False,
                                          building_shaft_supply_air=starting_point
                                          )

            # if export_graphen == True:
            #     self.visualization_graph_new(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum 2. Optimierung",
            #                                   unit_edge="m"
            #                                   )

            """3. Optimierung"""
            # Hier werden die Blätter aus dem Graphen ausgelesen
            blaetter = self.find_leaves(steiner_baum)

            # Entfernen der Blätter die kein Lüftungsauslass sind
            for blatt in blaetter:
                if blatt not in filtered_coords_ceiling_without_airflow:
                    terminals.remove(blatt)

            # Erstellung des neuen Steinerbaums
            steiner_baum = steiner_tree(G, terminals, weight="weight")

            # Add unit
            for u, v, data in steiner_baum.edges(data=True):
                gewicht_ohne_einheit = data['weight']

                # Füge die Einheit meter hinzu
                gewicht_mit_einheit = gewicht_ohne_einheit * ureg.meter

                # Aktualisiere das Gewicht der Kante im Steinerbaum
                data['weight'] = gewicht_mit_einheit

            if export_graphen == True:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum 3. Optimierung",
                                          unit_edge="m",
                                          total_coat_area=False,
                                          building_shaft_supply_air=starting_point
                                          )

            # if export_graphen == True:
            #     self.visualization_graph_new(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum 3. Optimierung",
            #                                   unit_edge="[m]"
            #                                   )

            # Steinerbaum mit Leitungslängen
            dict_steinerbaum_mit_leitungslaenge[z_value] = deepcopy(steiner_baum)

            # Hier wird der Startpunt zu den Blättern gesetzt
            start_punkt = (starting_point[0], starting_point[1], z_value)

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
                tree.add_edge(kante[0], kante[1], weight=self.euclidean_distance(kante[0], kante[1]))

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
                steiner_baum[u][v]["weight"] = 0

            # Hier werden die Luftvolumina entlang des Strangs aufaddiert
            for ceiling_point_to_root in ceiling_point_to_root_list:
                for startpunkt, zielpunkt in ceiling_point_to_root:
                    # Suche die Lüftungsmenge zur coordinate:
                    wert = None
                    for x, y, z, a in coordinates:
                        if x == ceiling_point_to_root[0][0][0] and y == ceiling_point_to_root[0][0][1] and z == \
                                ceiling_point_to_root[0][0][2]:
                            wert = a
                    G[startpunkt][zielpunkt]["weight"] += wert

            # Hier wird der einzelne Steinerbaum mit Volume_flow der Liste hinzugefügt
            dict_steinerbaum_mit_luftmengen[z_value] = deepcopy(steiner_baum)

            if export_graphen == True:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum mit Luftmenge m³ pro h",
                                          unit_edge="m³/h",
                                          total_coat_area=False,
                                          building_shaft_supply_air=starting_point
                                          )
            #
            # if export_graphen == True:
            #     self.visualization_graph_new(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum mit Luftmenge m³ pro h",
            #                                   unit_edge="m³/h"
            #                                   )

            # Graph mit Leitungsgeometrie erstellen
            H_leitungsgeometrie = deepcopy(steiner_baum)

            for u, v in H_leitungsgeometrie.edges():
                H_leitungsgeometrie[u][v]["weight"] = self.dimensions_ventilation_duct(cross_section_type,
                                                                             self.required_ventilation_duct_cross_section(
                                                                                 H_leitungsgeometrie[u][v][
                                                                                     "weight"]),
                                                                             suspended_ceiling_space)

            # Hinzufügen des Graphens zum Dict
            dict_steinerbaum_mit_kanalquerschnitt[z_value] = deepcopy(H_leitungsgeometrie)

            if export_graphen == True:
                self.visualisierung_graph(H_leitungsgeometrie,
                                          H_leitungsgeometrie,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum mit duct_cross_section in mm",
                                          unit_edge="mm",
                                          total_coat_area=False,
                                          building_shaft_supply_air=starting_point
                                          )

            # if export_graphen == True:
            #     self.visualization_graph_new(H_leitungsgeometrie,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum mit duct_cross_section in mm",
            #                                   unit_edge="mm"
            #                                   )

            # für äquivalenten Durchmesser:
            H_aequivalenter_durchmesser = deepcopy(steiner_baum)

            # Hier wird der Leitung der äquivalente Durchmesser des Kanals zugeordnet
            for u, v in H_aequivalenter_durchmesser.edges():
                H_aequivalenter_durchmesser[u][v]["weight"] = self.calculated_diameter(cross_section_type,
                                                                                             self.required_ventilation_duct_cross_section(
                                                                                                 H_aequivalenter_durchmesser[
                                                                                                     u][v][
                                                                                                     "weight"]),
                                                                                             suspended_ceiling_space)

            # Zum Dict hinzufügen
            dict_steinerbaum_mit_rechnerischem_querschnitt[z_value] = deepcopy(H_aequivalenter_durchmesser)

            if export_graphen == True:
                self.visualisierung_graph(H_aequivalenter_durchmesser,
                                          H_aequivalenter_durchmesser,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum mit rechnerischem Durchmesser in mm",
                                          unit_edge="mm",
                                          total_coat_area=False,
                                          building_shaft_supply_air=starting_point
                                          )
            #
            # if export_graphen == True:
            #     self.visualization_graph_new(H_aequivalenter_durchmesser,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum mit rechnerischem Durchmesser in mm",
            #                                   unit_edge="mm"
            #                                   )

            # Um die gesamte Menge der Mantelfläche zu bestimmen, muss diese aufaddiert werden:
            gesamte_matnelflaeche_luftleitung = 0

            # Hier wird der Leitung die Mantelfläche des Kanals zugeordnet
            for u, v in steiner_baum.edges():
                steiner_baum[u][v]["weight"] = round(self.coat_area_ventilation_duct(cross_section_type,
                                                                              self.required_ventilation_duct_cross_section(
                                                                                  steiner_baum[u][v]["weight"]),
                                                                              suspended_ceiling_space), 2
                                                     )

                gesamte_matnelflaeche_luftleitung += round(steiner_baum[u][v]["weight"], 2)

            # Hinzufügen des Graphens zum Dict
            dict_steinertree_with_shell[z_value] = deepcopy(steiner_baum)

            if export_graphen == True:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum mit Mantelfläche",
                                          unit_edge="m²/m",
                                          total_coat_area="",
                                          building_shaft_supply_air=starting_point
                                          )

            # if export_graphen == True:
            #     self.visualization_graph_new(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum mit Mantelfläche",
            #                                   unit_edge="[m²/m]"
            #                                   )

        # except ValueError as e:
        #     if str(e) == "attempt to get argmin of an empty sequence":
        #         self.logger.info("suspended_ceiling_space too low gewählt!")
        #         exit()
        #         # TODO wie am besten?

        return (
            dict_steinerbaum_mit_leitungslaenge, dict_steinerbaum_mit_kanalquerschnitt, dict_steinerbaum_mit_luftmengen,
            dict_steinertree_with_shell, dict_steinerbaum_mit_rechnerischem_querschnitt)

    def rlt_shaft(self,
                    z_coordinate_list,
                    building_shaft_supply_air,
                    airflow_volume_per_storey,
                    position_ahu,
                    dict_steiner_tree_with_duct_length,
                    dict_steiner_tree_with_duct_cross_section,
                    dict_steiner_tree_with_air_volume_supply_air,
                    dict_steiner_tree_with_sheath_area,
                    dict_steiner_tree_with_calculated_cross_section,
                    export_graphen
                    ):

        # Image URLs for graph nodes
        icons = {
            "Supply air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Zuluftdurchlass.png'),
            "Exhaust air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/Abluftdurchlass.png'),
            "gps_not_fixed": Path(
                bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/gps_not_fixed.png'),
            "north": Path(
                bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/north.png'),
            "bar_blue": Path(
                bim2sim.__file__).parent.parent / (
                            'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/bar_blue.png'),
            "rlt": Path(
                bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginLCA/bim2sim_lca/examples/symbols_DIN_EN_12792/rlt.png')
        }
        # Load images
        images = {k: PIL.Image.open(fname) for k, fname in icons.items()}

        nodes_shaft = list()
        z_coordinate_list = list(z_coordinate_list)
        # Ab hier wird er Graph für das RLT-Gerät bis zum shaft erstellt.
        shaft = nx.Graph()

        for z_value in z_coordinate_list:
            # Hinzufügen der Knoten
            shaft.add_node((building_shaft_supply_air[0], building_shaft_supply_air[1], z_value),
                             weight=airflow_volume_per_storey[z_value], image=images["north"])
            nodes_shaft.append((building_shaft_supply_air[0], building_shaft_supply_air[1], z_value,
                                  airflow_volume_per_storey[z_value]))

        # Ab hier wird der Graph über die Geschosse hinweg erstellt:
        # Kanten für shaft hinzufügen:
        for i in range(len(z_coordinate_list) - 1):
            weight = self.euclidean_distance(
                [building_shaft_supply_air[0], building_shaft_supply_air[1], float(z_coordinate_list[i])],
                [building_shaft_supply_air[0], building_shaft_supply_air[1],
                 float(z_coordinate_list[i + 1])]) * ureg.meter
            shaft.add_edge((building_shaft_supply_air[0], building_shaft_supply_air[1], z_coordinate_list[i]),
                             (building_shaft_supply_air[0], building_shaft_supply_air[1], z_coordinate_list[i + 1]),
                             weight=weight)

        # Summe Airflow
        summe_airflow = sum(airflow_volume_per_storey.values())

        # Knoten der Air handling unit mit Gesamtluftmenge anreichern
        shaft.add_node((position_ahu[0], position_ahu[1], position_ahu[2]),
                         weight=summe_airflow, image=images["rlt"])

        shaft.add_node((building_shaft_supply_air[0], building_shaft_supply_air[1], position_ahu[2]),
                         weight=summe_airflow, image=images["north"])

        # Verbinden der RLT Anlage mit dem shaft
        rlt_shaft_weight = self.euclidean_distance([position_ahu[0], position_ahu[1], position_ahu[2]],
                                                      [building_shaft_supply_air[0], building_shaft_supply_air[1],
                                                       position_ahu[2]]
                                                      ) * ureg.meter

        shaft.add_edge((position_ahu[0], position_ahu[1], position_ahu[2]),
                         (building_shaft_supply_air[0], building_shaft_supply_air[1], position_ahu[2]),
                         weight=rlt_shaft_weight)

        # Wenn die RLT nicht in der Ebene einer Decke liegt, muss die Luftleitung noch mit dem shaft verbunden werden
        list_shaft_nodes = list(shaft.nodes())
        closest = None
        min_distance = float('inf')

        for coord in list_shaft_nodes:
            # Skip if it's the same coordinate
            if coord == (building_shaft_supply_air[0], building_shaft_supply_air[1], position_ahu[2]):
                continue
            # Check if the x and y coordinates are the same
            if coord[0] == building_shaft_supply_air[0] and coord[1] == building_shaft_supply_air[1]:
                distance = abs(coord[2] - position_ahu[2])
                if distance < min_distance:
                    min_distance = distance
                    closest = coord

        verbindung_weight = self.euclidean_distance(
            [building_shaft_supply_air[0], building_shaft_supply_air[1], position_ahu[2]],
            closest
            ) * ureg.meter
        shaft.add_edge((building_shaft_supply_air[0], building_shaft_supply_air[1], position_ahu[2]),
                         closest,
                         weight=verbindung_weight)

        # Zum Dict hinzufügen
        dict_steiner_tree_with_duct_length["shaft"] = deepcopy(shaft)

        # visualization shaft
        if export_graphen == True:
            self.plot_shaft_neu(shaft, name="shaft", unit_edge="[m]")

        position_ahu_ohne_airflow = (position_ahu[0], position_ahu[1], position_ahu[2])

        # Hier werden die Wege im Baum vom Lüftungsauslass zum Startpunkt ausgelesen
        shaft_to_rlt = list()
        for point in shaft.nodes():
            for path in nx.all_simple_edge_paths(shaft, point, position_ahu_ohne_airflow):
                shaft_to_rlt.append(path)

        # Hier werden die Gewichte der Kanten im Steinerbaum gelöscht, da sonst die Luftmenge auf den
        # Abstand addiert wird. Es darf aber auch anfangs nicht das Gewicht der Kante zu 0 gesetzt
        # werden, da sonst der Steinerbaum nicht korrekt berechnet wird
        for u, v in shaft.edges():
            shaft[u][v]["weight"] = 0

        # Hier werden die Luftvolumina entlang des Strangs aufaddiert
        for shaftpunkt_zu_rlt in shaft_to_rlt:
            for startpunkt, zielpunkt in shaftpunkt_zu_rlt:
                # Suche die Lüftungsmenge zur coordinate:
                wert = int()
                for x, y, z, a in nodes_shaft:
                    if x == shaftpunkt_zu_rlt[0][0][0] and y == shaftpunkt_zu_rlt[0][0][1] and z == \
                            shaftpunkt_zu_rlt[0][0][2]:
                        wert = a
                shaft[startpunkt][zielpunkt]["weight"] += wert

        # Zum Dict hinzufügen
        dict_steiner_tree_with_air_volume_supply_air["shaft"] = deepcopy(shaft)

        # visualization shaft
        if export_graphen == True:
            self.plot_shaft_neu(shaft, name="shaft mit Luftvolumina", unit_edge="[m3/h]")

        # Graph mit Leitungsgeometrie erstellen
        shaft_leitungsgeometrie = deepcopy(shaft)

        # duct_cross_section shaft und RLT zu shaft bestimmen
        for u, v in shaft.edges():
            shaft_leitungsgeometrie[u][v]["weight"] = self.dimensions_ventilation_duct("angular",
                                                                               self.required_ventilation_duct_cross_section(
                                                                                   shaft_leitungsgeometrie[u][v][
                                                                                       "weight"]),
                                                                               suspended_ceiling_space=2000
                                                                               )

        # Zum Dict hinzufügen
        dict_steiner_tree_with_duct_cross_section["shaft"] = deepcopy(shaft_leitungsgeometrie)

        # visualization shaft
        if export_graphen == True:
            self.plot_shaft_neu(shaft_leitungsgeometrie, name="shaft mit cross_section", unit_edge="")

        # Kopie vom Graphen
        shaft_calculated_diameter = deepcopy(shaft)

        # Hier wird der Leitung die Mantelfläche des Kanals zugeordnet
        for u, v in shaft.edges():
            shaft[u][v]["weight"] = round(self.coat_area_ventilation_duct("angular",
                                                                     self.required_ventilation_duct_cross_section(
                                                                         shaft[u][v]["weight"]),
                                                                     suspended_ceiling_space=2000
                                                                     ),
                                            2
                                            )

        # Zum Dict hinzufügen
        dict_steiner_tree_with_sheath_area["shaft"] = deepcopy(shaft)

        # visualization shaft
        if export_graphen == True:
            self.plot_shaft_neu(shaft, name="shaft mit Mantelfläche", unit_edge="[m2/m]")

        # Hier wird der Leitung der äquivalente Durchmesser des Kanals zugeordnet
        for u, v in shaft_calculated_diameter.edges():
            shaft_calculated_diameter[u][v]["weight"] = self.calculated_diameter("angular",
                                                                                               self.required_ventilation_duct_cross_section(
                                                                                                   shaft_calculated_diameter[
                                                                                                       u][v]["weight"]),
                                                                                               suspended_ceiling_space=2000
                                                                                               )

        # Zum Dict hinzufügen
        dict_steiner_tree_with_calculated_cross_section["shaft"] = deepcopy(shaft_calculated_diameter)

        # visualization shaft
        if export_graphen == True:
            self.plot_shaft_neu(shaft_calculated_diameter, name="shaft mit rechnerischem Durchmesser",
                                  unit_edge="[mm]")

        return (dict_steiner_tree_with_duct_length,
                dict_steiner_tree_with_duct_cross_section,
                dict_steiner_tree_with_air_volume_supply_air,
                dict_steiner_tree_with_sheath_area,
                dict_steiner_tree_with_calculated_cross_section)

    def finde_abmessung(self, text: str):
        if "Ø" in text:
            # Fall 1: "Ø" gefolgt von einer number
            number = ureg(text.split("Ø")[1])  # Teilt den String am "Ø" und nimmt den zweiten Teil
            return number
        else:
            # Fall 2: "250 x 200" Format
            zahlen = text.split(" x ")  # Teilt den String bei " x "
            width = ureg(zahlen[0])
            height = ureg(zahlen[1])
            return width, height

    def drei_dimensionaler_graph(self,
                                 dict_steiner_tree_with_duct_length,
                                 dict_steiner_tree_with_duct_cross_section,
                                 dict_steiner_tree_with_air_volume_supply_air,
                                 dict_steiner_tree_with_sheath_area,
                                 dict_steiner_tree_with_calculated_cross_section,
                                 position_ahu,
                                 export,
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
        graph_luftmengen = nx.Graph()
        graph_kanalquerschnitt = nx.Graph()
        graph_mantelflaeche = nx.Graph()
        graph_calculated_diameter = nx.Graph()

        position_ahu = (position_ahu[0], position_ahu[1], position_ahu[2])

        # für Leitungslänge
        for baum in dict_steiner_tree_with_duct_length.values():
            graph_leitungslaenge = nx.compose(graph_leitungslaenge, baum)

        # Graph für Leitungslänge in einen gerichteten Graphen umwandeln
        graph_leitungslaenge_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_leitungslaenge_gerichtet, position_ahu, graph_leitungslaenge)

        # für Luftmengen
        for baum in dict_steiner_tree_with_air_volume_supply_air.values():
            graph_luftmengen = nx.compose(graph_luftmengen, baum)

        # Graph für Luftmengen in einen gerichteten Graphen umwandeln
        graph_luftmengen_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_luftmengen_gerichtet, position_ahu, graph_luftmengen)

        # für duct_cross_section
        for baum in dict_steiner_tree_with_duct_cross_section.values():
            graph_kanalquerschnitt = nx.compose(graph_kanalquerschnitt, baum)

        # Graph für duct_cross_section in einen gerichteten Graphen umwandeln
        graph_kanalquerschnitt_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_kanalquerschnitt_gerichtet, position_ahu, graph_kanalquerschnitt)

        # für Mantelfläche
        for baum in dict_steiner_tree_with_sheath_area.values():
            graph_mantelflaeche = nx.compose(graph_mantelflaeche, baum)

        # Graph für Mantelfläche in einen gerichteten Graphen umwandeln
        graph_mantelflaeche_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_mantelflaeche_gerichtet, position_ahu, graph_mantelflaeche)

        # für rechnerischen cross_section
        for baum in dict_steiner_tree_with_calculated_cross_section.values():
            graph_calculated_diameter = nx.compose(graph_calculated_diameter, baum)

        # Graph für rechnerischen cross_section in einen gerichteten Graphen umwandeln
        graph_calculated_diameter_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_calculated_diameter_gerichtet, position_ahu, graph_calculated_diameter)

        datenbank_verteilernetz = pd.DataFrame(columns=[
            'Startknoten',
            'Zielknoten',
            'Kante',
            'room type Startknoten',
            'room type Zielknoten',
            'Leitungslänge',
            'Luftmenge',
            'duct_cross_section',
            'Mantelfläche',
            'rechnerischer Durchmesser'
        ])

        # Daten der Datenbank hinzufügen
        for u, v in graph_leitungslaenge_gerichtet.edges():
            temp_df = pd.DataFrame({
                'Startknoten': [u],
                'Zielknoten': [v],
                'Kante': [(u, v)],
                'room type Startknoten': [dict_coordinate_with_space_type.get(u, None)],
                'room type Zielknoten': [dict_coordinate_with_space_type.get(v, None)],
                'Leitungslänge': [graph_leitungslaenge_gerichtet.get_edge_data(u, v)["weight"]],
                'Luftmenge': [graph_luftmengen_gerichtet.get_edge_data(u, v)["weight"]],
                'duct_cross_section': [graph_kanalquerschnitt_gerichtet.get_edge_data(u, v)["weight"]],
                'Mantelfläche': [graph_mantelflaeche_gerichtet.get_edge_data(u, v)["weight"] *
                                 graph_leitungslaenge_gerichtet.get_edge_data(u, v)["weight"]],
                'rechnerischer Durchmesser': [graph_calculated_diameter_gerichtet.get_edge_data(u, v)["weight"]]
            })
            datenbank_verteilernetz = pd.concat([datenbank_verteilernetz, temp_df], ignore_index=True)

        for index, zeile in datenbank_verteilernetz.iterrows():
            duct_cross_section = zeile['duct_cross_section']

            if "Ø" in duct_cross_section:
                # Finde den Durchmesser und aktualisiere den entsprechenden Wert in der Datenbank
                datenbank_verteilernetz.at[index, 'Durchmesser'] = str(self.finde_abmessung(duct_cross_section))

            elif "x" in duct_cross_section:
                # Finde width und Höhe, zerlege den Querschnittswert und aktualisiere die entsprechenden Werte in der Datenbank
                width, height = self.finde_abmessung(duct_cross_section)
                datenbank_verteilernetz.at[index, 'width'] = str(width)
                datenbank_verteilernetz.at[index, 'Höhe'] = str(height)

        if export == True:
            # Darstellung des 3D-Graphens:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

            # Knotenpositionen in 3D
            pos = {coord: (coord[0], coord[1], coord[2]) for coord in list(graph_luftmengen.nodes())}

            # Knoten zeichnen
            for node, weight in nx.get_node_attributes(graph_luftmengen, 'weight').items():
                if weight > 0:  # Überprüfen, ob das Gewicht größer als 0 ist
                    color = 'red'
                else:
                    color = 'black'  # Andernfalls rot (oder eine andere Farbe für Gewicht = 0)

                # Zeichnen des Knotens mit der bestimmten Farbe
                ax.scatter(*node, color=color)

            # Kanten zeichnen
            for edge in graph_luftmengen.edges():
                start, end = edge
                x_start, y_start, z_start = pos[start]
                x_end, y_end, z_end = pos[end]
                ax.plot([x_start, x_end], [y_start, y_end], [z_start, z_end], "blue")

            # Achsenbeschriftungen und Titel
            ax.set_xlabel('X-Achse [m]')
            ax.set_ylabel('Y-Achse [m]')
            ax.set_zlabel('Z-Achse [m]')
            ax.set_title("3D Graph supply_air")

            # Füge eine Legende hinzu, falls gewünscht
            ax.legend()

            # Diagramm anzeigen
            plt.close()

        return (graph_leitungslaenge_gerichtet,
                graph_luftmengen_gerichtet,
                graph_kanalquerschnitt_gerichtet,
                graph_mantelflaeche_gerichtet,
                graph_calculated_diameter_gerichtet,
                datenbank_verteilernetz
                )

    def druckverlust(self,
                     dict_steiner_tree_with_duct_length,
                     z_coordinate_list,
                     building_shaft_supply_air,
                     position_shaft,
                     graph_ventilation_duct_length_supply_air,
                     graph_luftmengen,
                     graph_kanalquerschnitt,
                     graph_mantelflaeche,
                     graph_calculated_diameter,
                     export,
                     datenbank_verteilernetz):
        # Standardwerte für Berechnung
        rho = 1.204 * (ureg.kilogram / (ureg.meter ** 3))  # Dichte der Luft bei Standardbedingungen
        nu = 1.33 * 0.00001  # Dynamische Viskosität der Luft

        def darstellung_t_stueck(eingang, rohr, ausgang):
            """
            Erstelle eine 3D-Graphen des T-Stücks
            :param eingang: Lufteinleitung in T-Stück
            :param rohr: Rohr für Verluste
            :param ausgang: Abknickende Rohr
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
            zeichne_pfeil(eingang[0], eingang[1], 'red')  # Eingang in Rot
            zeichne_pfeil(rohr[0], rohr[1], 'red')  # Rohr in Rot
            zeichne_pfeil(ausgang[0], ausgang[1], 'blue',
                          'dashed')  # Abknickende Leitung gestrichelt in Blau

            # Setzen der Achsenbeschriftungen
            ax.set_xlabel('X Achse')
            ax.set_ylabel('Y Achse')
            ax.set_zlabel('Z Achse')

            # Titel des Plots
            ax.set_title('3D Darstellung der Leitungen')

            # Anpassen der Achsengrenzen basierend auf den Koordinaten
            alle_koordinaten = rohr + ausgang + eingang
            x_min, x_max = min(k[0] for k in alle_koordinaten), max(k[0] for k in alle_koordinaten)
            y_min, y_max = min(k[1] for k in alle_koordinaten), max(k[1] for k in alle_koordinaten)
            z_min, z_max = min(k[2] for k in alle_koordinaten), max(k[2] for k in alle_koordinaten)

            ax.set_xlim([x_min - 1, x_max + 1])
            ax.set_ylim([y_min - 1, y_max + 1])
            ax.set_zlim([z_min - 1, z_max + 1])

            # Anzeigen des Plots
            # plt.show()

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
            Berechnet den Widerstandsbeiwert fpr einen Bogen round A01 nach VDI 3803 Blatt 6
            :param winkel: Winkel in Grad
            :param mittlerer_radius: Mittlerer Radius des Bogens in Metern
            :param durchmesser: Durchmesser der Leitung in Metern
            :return: Widerstandsbeiwert Bogen round A01 nach VDI 3803 Blatt 6
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * winkel)

            b = None
            if 0.5 <= mittlerer_radius / durchmesser <= 1.0:
                b = 0.21 / ((mittlerer_radius / durchmesser) ** 2.5)
            elif 1 <= mittlerer_radius / durchmesser:
                b = (0.21 / (math.sqrt(mittlerer_radius / durchmesser)))

            c = 1

            return a * b * c

        def widerstandsbeiwert_bogen_angular(winkel, mittlerer_radius, height, width, calculated_diameter):
            """
            Berechnet den Widerstandsbeiwert für einen Bogen angular A02 nach VDI 3803 Blatt 6
            :param winkel: Winkel in Grad
            :param mittlerer_radius: mittlerer Radius des Bogens in Metern
            :param height: height der Leitung in Metern
            :param width: width der Leiutung in Metern
            :param calculated_diameter: Rechnerischer Durchmesser der Leitung
            :return: Widerstandsbeiwert Bogen angular
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * winkel)

            b = None
            if 0.5 <= mittlerer_radius / calculated_diameter <= 1.0:
                b = 0.21 / ((mittlerer_radius / calculated_diameter) ** 2.5)
            elif 1 <= mittlerer_radius / calculated_diameter:
                b = (0.21 / (math.sqrt(mittlerer_radius / calculated_diameter)))

            c = (- 1.03663 * 10 ** (-4) * (height / width) ** 5 + 0.00338 * (height / width) ** 4 - 0.04277 * (
                    height / width)
                 ** 3 + 0.25496 * (height / width) ** 2 - 0.66296 * (height / width) + 1.4499)

            return a * b * c

        def widerstandsbeiwert_querschnittserweiterung(d_1, d_2):
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

                # cross_section 1:
                A_1 = math.pi * d_1 ** 2 / 4

                # cross_section 2:
                A_2 = math.pi * d_2 ** 2 / 4

                zeta_1 = (1 - A_1 / A_2) ** 2 * (1 - eta_D)

                return zeta_1

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

                # cross_section 1:
                A_1 = math.pi * d_1 ** 2 / 4

                # cross_section 2:
                A_2 = math.pi * d_2 ** 2 / 4

                zeta_1 = - (k_1) * (A_2 / A_1) ** 2 + k_1

                if zeta_1 < 0:
                    zeta_1 = 0

                return zeta_1

        def widerstandsbeiwert_T_stueck_trennung_rund(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                      v_A: float,
                                                      richtung: str) -> float:
            """
            Berechnet den Widerstandbeiwert für eine T-Trennung A22 nach VDI 3803 Blatt 6
            :param d: Durchmesser des Eingang in Metern
            :param v: Volume_flow des Eingangs in m³/h
            :param d_D: Durchmesser des Durchgangs in Metern
            :param v_D: Volume_flow des Durchgangs in m³/h
            :param d_A: Durchmesser des Abgangs in Metern
            :param v_A: Volume_flow des Abgangs in m³/h
            :param richtung: "Durchgangsrichtung" oder "abzweigende Richtung"
            :return: Widerstandbeiwert für eine T-Trennung A22
            """

            # cross_section Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = (v / A).to(ureg.meter / ureg.second)

            # cross_section Durchgang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgang
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # cross_section Abzweigung:
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

        def widerstandsbeiwert_T_stueck_trennung_angular(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                       v_A: float, richtung: str) -> float:
            """
            Berechnet den Widerstandbeiwert für eine T-Trennung A24 nach VDI 3803 Blatt 6
            :param d: rechnerischer Durchmesser des Eingang in Metern
            :param v: Volume_flow des Eingangs in m³/h
            :param d_D: rechnerischer Durchmesser des Durchgangs in Metern
            :param v_D: Volume_flow des Durchgangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abgangs in Metern
            :param v_A: Volume_flow des Abgangs in m³/h
            :param richtung: "Durchgangsrichtung" oder "abzweigende Richtung"
            :return: Widerstandbeiwert für eine T-Trennung A24
            """

            # cross_section Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = (v / A).to(ureg.meter / ureg.second)

            # cross_section Durchgang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgang
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # cross_section Abzweigung:
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

        def widerstandsbeiwert_kruemmerendstueck_angular(a: float, b: float, d: float, v: float, d_A: float, v_A: float):
            """
            Berechnet den Widerstandsbeiwert für Krümmerabzweig A25 nach VDI 3803
            :param a: Höhe des Eingangs in Metern
            :param b: width des Eingangs in Metern
            :param d: rechnerischer Durchmesser des Eingangs in Metern
            :param v: Volume_flow des Eingangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abzweiges in Metern
            :param v_A: Volume_flow des Abzweiges in m³/h
            :return: Widerstandsbeiwert für Krümmerabzweig A25 nach VDI 3803
            """

            # cross_section Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = (v / A).to(ureg.meter / ureg.second)

            # cross_section Abzweigung:
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
            Berechnet den Widerstandsbeiwert für ein T-Stück round A27 nach VDI 3803
            :param d: rechnerischer Durchmesser des Eingangs in Metern
            :param v: Volume_flow des Eingangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abzweiges in Metern
            :param v_A: Volume_flow des Abzweiges in m³/h
            :return: Widerstandsbeiwert für ein T-Stück round A27 nach VDI 3803
            """

            # cross_section Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = (v / A).to(ureg.meter / ureg.second)

            # cross_section Abzweigung:
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

        building_shaft_supply_air = (
        building_shaft_supply_air[0], building_shaft_supply_air[1], building_shaft_supply_air[2])

        # Erstellung einer BFS-Reihenfolge ab dem Startpunkt
        bfs_edges = list(nx.edge_bfs(graph_ventilation_duct_length_supply_air, building_shaft_supply_air))

        graph_leitungslaenge_sortiert = nx.Graph()

        # Kanten in der BFS-Reihenfolge zum neuen Graphen hinzufügen
        for edge in bfs_edges:
            graph_leitungslaenge_sortiert.add_edge(*edge)

        # Druckverlustberechnung
        # Netz erstellen:
        net = pp.create_empty_network(fluid="air")

        # Auslesen des Fluides
        fluid = pp.get_fluid(net)

        # Auslesen der Dichte
        dichte = fluid.get_density(temperature=293.15) * ureg.kilogram / ureg.meter ** 3

        # Definition der Parameter für die Junctions
        name_junction = [coordinate for coordinate in list(graph_leitungslaenge_sortiert.nodes())]
        index_junction = [index for index, wert in enumerate(name_junction)]

        # Erstellen einer Liste für jede Koordinatenachse
        x_koordinaten = [coordinate[0] for coordinate in list(graph_leitungslaenge_sortiert.nodes())]
        y_koordinaten = [coordinate[1] for coordinate in list(graph_leitungslaenge_sortiert.nodes())]
        z_koordinaten = [coordinate[2] for coordinate in list(graph_leitungslaenge_sortiert.nodes())]

        """2D-Koordinaten erstellen"""
        # Da nur 3D Koordinaten vorhanden sind, jedoch 3D Koordinaten gebraucht werden wird ein Dict erszellt, welches
        # jeder 3D coordinate einen 2D-coordinate zuweist
        zwei_d_koodrinaten = dict()
        position_shaft_graph = (position_shaft[0], position_shaft[1], position_shaft[2])

        # Leitung von RLT zu shaft
        pfad_rlt_zu_shaft = list(
            nx.all_simple_paths(graph_ventilation_duct_length_supply_air, building_shaft_supply_air,
                                position_shaft_graph))[0]
        anzahl_punkte_pfad_rlt_zu_shaft = -len(pfad_rlt_zu_shaft)

        for punkt in pfad_rlt_zu_shaft:
            zwei_d_koodrinaten[punkt] = (anzahl_punkte_pfad_rlt_zu_shaft, 0)
            anzahl_punkte_pfad_rlt_zu_shaft += 1

        anzahl_knoten_mit_mindestens_drei_kanten = len(
            [node for node, degree in graph_ventilation_duct_length_supply_air.degree() if degree >= 3])

        # Versuch, alle Keys in Zahlen umzuwandeln und zu sortieren
        sorted_keys = sorted(
            (key for key in dict_steiner_tree_with_duct_length.keys() if key != "shaft"),
            key=lambda x: float(x)
        )

        y = 0  # Start y-coordinate

        for key in sorted_keys:
            graph_geschoss = dict_steiner_tree_with_duct_length[key]

            shaft_knoten = [node for node in graph_geschoss.nodes()
                              if node[0] == position_shaft[0] and node[1] == building_shaft_supply_air[1]][0]

            # Blattknoten identifizieren (Knoten mit Grad 1)
            blatt_knoten = [node for node in graph_geschoss.nodes()
                            if graph_geschoss.degree(node) == 1 and node != shaft_knoten]

            # Pfade vom Startknoten zu jedem Blattknoten berechnen
            pfade = [nx.shortest_path(graph_geschoss, source=shaft_knoten, target=blatt) for blatt in blatt_knoten]

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

                        if pfad_zaehler >= 1 and rest_laenge_pfad >= 1:
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

        # Definition der Parameter für die Pipes
        name_pipe = [pipe for pipe in
                     list(graph_leitungslaenge_sortiert.edges())]  # Bezeichung ist die Start- und Endkoordinate
        length_pipe = [graph_ventilation_duct_length_supply_air.get_edge_data(pipe[0], pipe[1])["weight"] for pipe in
                       name_pipe]  # Die Länge wird aus dem Graphen mit Leitungslängen ausgelesen

        from_junction = [pipe[0] for pipe in name_pipe]  # Start Junction des Rohres
        to_junction = [pipe[1] for pipe in name_pipe]  # Ziel Junction des Rohres
        diameter_pipe = [graph_calculated_diameter.get_edge_data(pipe[0], pipe[1])["weight"] for pipe in
                         name_pipe]

        # Hinzufügen der Rohre zum Netz
        for pipe in range(len(name_pipe)):
            pp.create_pipe_from_parameters(net,
                                           from_junction=int(name_junction.index(from_junction[pipe])),
                                           to_junction=int(name_junction.index(to_junction[pipe])),
                                           nr_junctions=pipe,
                                           length_km=length_pipe[pipe].to(ureg.kilometer).magnitude,
                                           diameter_m=diameter_pipe[pipe].to(ureg.meter).magnitude,
                                           k_mm=0.15,
                                           name=str(name_pipe[pipe]),
                                           loss_coefficient=0
                                           )

        """Ab hier werden die Verlustbeiwerte der Rohre angepasst"""
        for pipe in range(len(name_pipe)):

            # Nachbarn des Startknotens
            neighbors = list(nx.all_neighbors(graph_ventilation_duct_length_supply_air, from_junction[pipe]))

            """Bögen:"""
            if len(neighbors) == 2:  # Bögen finden
                eingehende_kante = list(graph_ventilation_duct_length_supply_air.in_edges(from_junction[pipe]))[0]
                ausgehende_kante = list(graph_ventilation_duct_length_supply_air.out_edges(from_junction[pipe]))[0]
                # Rechnerischer Durchmesser der Leitung
                calculated_diameter = \
                    graph_calculated_diameter.get_edge_data(from_junction[pipe], to_junction[pipe])[
                        "weight"].to(ureg.meter)

                # Abmessung des Rohres
                abmessung_kanal = graph_kanalquerschnitt.get_edge_data(from_junction[pipe], to_junction[pipe])[
                    "weight"]

                if not check_if_lines_are_aligned(eingehende_kante, ausgehende_kante):

                    zeta_bogen = None
                    if "Ø" in abmessung_kanal:
                        durchmesser = self.finde_abmessung(abmessung_kanal)
                        zeta_bogen = widerstandsbeiwert_bogen_rund(winkel=90,
                                                                   mittlerer_radius=0.75 * ureg.meter,
                                                                   durchmesser=durchmesser)
                        # print(f"Zeta-Bogen round: {zeta_bogen}")

                    elif "x" in abmessung_kanal:
                        width = self.finde_abmessung(abmessung_kanal)[0].to(ureg.meter)
                        height = self.finde_abmessung(abmessung_kanal)[1].to(ureg.meter)
                        zeta_bogen = widerstandsbeiwert_bogen_angular(winkel=90,
                                                                    mittlerer_radius=0.75 * ureg.meter,
                                                                    height=height,
                                                                    width=width,
                                                                    calculated_diameter=calculated_diameter
                                                                    )
                        # print(f"Zeta Bogen angular: {zeta_bogen}")

                    # Ändern des loss_coefficient-Werts
                    net['pipe'].at[pipe, 'loss_coefficient'] += zeta_bogen

                    datenbank_verteilernetz.loc[datenbank_verteilernetz[
                                                    'Zielknoten'] == to_junction[pipe], 'Zeta Bogen'] = zeta_bogen

            """Reduzierungen"""
            if len(neighbors) == 2:
                rohr = name_pipe[pipe]
                rohr_nachbar = to_junction[pipe]
                abmessung_rohr = graph_kanalquerschnitt.get_edge_data(from_junction[pipe], to_junction[pipe])[
                    "weight"]

                ausgehende_kanten = graph_ventilation_duct_length_supply_air.out_edges(from_junction[pipe])

                eingehende_kanten = list(graph_ventilation_duct_length_supply_air.in_edges(from_junction[pipe]))[0]
                eingehender_nachbar_knoten = eingehende_kanten[1]
                abmessung_eingehende_kante = \
                    graph_kanalquerschnitt.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])[
                        "weight"]

                """ Daten für Widerstandsbeiwerte"""
                # Durchmesser des Eingangs:
                d = graph_calculated_diameter.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])[
                    "weight"].to(ureg.meter)
                # Volume_flow des Eingangs:
                v = graph_luftmengen.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])["weight"]

                # Durchmesser des Durchgangs:
                d_D = graph_calculated_diameter.get_edge_data(rohr[0], rohr[1])["weight"].to(ureg.meter)
                # Volume_flow des Durchgangs:
                v_D = graph_luftmengen.get_edge_data(rohr[0], rohr[1])["weight"]

                if d > d_D:
                    zeta_reduzierung = widerstandsbeiwert_querschnittsverengung_stetig(d, d_D)

                    # print(f"Zeta T-Reduzierung: {zeta_reduzierung}")

                    net['pipe'].at[pipe, 'loss_coefficient'] += zeta_reduzierung

                    datenbank_verteilernetz.loc[datenbank_verteilernetz[
                                                    'Zielknoten'] == to_junction[
                                                    pipe], 'Zeta Reduzierung'] = zeta_reduzierung

            """T-Stücke"""
            if len(neighbors) == 3:  # T-Stücke finden
                rohr = name_pipe[pipe]
                rohr_nachbar = to_junction[pipe]
                abmessung_rohr = graph_kanalquerschnitt.get_edge_data(from_junction[pipe], to_junction[pipe])[
                    "weight"]

                ausgehende_kanten = graph_ventilation_duct_length_supply_air.out_edges(from_junction[pipe])

                abknickende_leitung = [p for p in ausgehende_kanten if p != rohr][0]
                abknickende_leitung_knoten = abknickende_leitung[1]
                abmessung_abknickende_leitung = \
                    graph_kanalquerschnitt.get_edge_data(abknickende_leitung[0], abknickende_leitung[1])[
                        "weight"]

                eingehende_kanten = list(graph_ventilation_duct_length_supply_air.in_edges(from_junction[pipe]))[0]
                eingehender_nachbar_knoten = eingehende_kanten[1]
                abmessung_eingehende_kante = \
                    graph_kanalquerschnitt.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])[
                        "weight"]

                """ Daten für Widerstandsbeiwerte"""
                # Durchmesser des Eingangs:
                d = graph_calculated_diameter.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])[
                    "weight"].to(ureg.meter)
                # Volume_flow des Eingangs:
                v = graph_luftmengen.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])["weight"]

                # Durchmesser des Durchgangs:
                d_D = graph_calculated_diameter.get_edge_data(rohr[0], rohr[1])["weight"].to(ureg.meter)
                # Volume_flow des Durchgangs:
                v_D = graph_luftmengen.get_edge_data(rohr[0], rohr[1])["weight"]

                # Durchmesser des Abgangs:
                d_A = \
                    graph_calculated_diameter.get_edge_data(abknickende_leitung[0], abknickende_leitung[1])[
                        "weight"].to(ureg.meter)
                # Volume_flow des Abgangs
                v_A = graph_luftmengen.get_edge_data(abknickende_leitung[0], abknickende_leitung[1])["weight"]

                zeta_t_stueck = 0
                zeta_querschnittsverengung = 0

                # 3D Darstellung des T-Stücks
                # darstellung_t_stueck(eingehende_kanten, rohr, abknickende_leitung)

                if check_if_lines_are_aligned(eingehende_kanten, rohr) == True:

                    #   Rohr für Verlust
                    #    |
                    #    |---- Ausgang
                    #    |
                    #  Eingang

                    # print("T-Stück geht durch ")

                    if "Ø" in abmessung_eingehende_kante:

                        zeta_t_stueck = widerstandsbeiwert_T_stueck_trennung_rund(d=d,
                                                                                  v=v,
                                                                                  d_D=d_D,
                                                                                  v_D=v_D,
                                                                                  d_A=d_A,
                                                                                  v_A=v_A,
                                                                                  richtung="Durchgangsrichtung")

                        # print(f"Zeta T-Stück: {zeta_t_stueck}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck

                    elif "x" in abmessung_eingehende_kante:
                        zeta_t_stueck = widerstandsbeiwert_T_stueck_trennung_angular(d=d,
                                                                                   v=v,
                                                                                   d_D=d_D,
                                                                                   v_D=v_D,
                                                                                   d_A=d_A,
                                                                                   v_A=v_A,
                                                                                   richtung="Durchgangsrichtung")

                        if "Ø" in abmessung_rohr and d > d_D:
                            zeta_querschnittsverengung = widerstandsbeiwert_querschnittsverengung_stetig(d, d_D)
                        else:
                            zeta_querschnittsverengung = 0

                        # print(f"Zeta T-Stück: {zeta_t_stueck + zeta_querschnittsverengung}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck + zeta_querschnittsverengung




                elif check_if_lines_are_aligned(eingehende_kanten, abknickende_leitung) == True:

                    #  Ausgang
                    #    |
                    #    |---- Rohr für Verlust
                    #    |
                    #  Eingang

                    # print("T-Stück knickt ab ")

                    if "Ø" in abmessung_eingehende_kante:

                        zeta_t_stueck = widerstandsbeiwert_T_stueck_trennung_rund(d=d,
                                                                                  v=v,
                                                                                  d_D=d_D,
                                                                                  v_D=v_D,
                                                                                  d_A=d_A,
                                                                                  v_A=v_A,
                                                                                  richtung="abzweigende Richtung")

                        # print(f"Zeta T-Stück: {zeta_t_stueck}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck


                    elif "x" in abmessung_eingehende_kante:
                        zeta_t_stueck = widerstandsbeiwert_T_stueck_trennung_angular(d=d,
                                                                                   v=v,
                                                                                   d_D=d_D,
                                                                                   v_D=v_D,
                                                                                   d_A=d_A,
                                                                                   v_A=v_A,
                                                                                   richtung="abzweigende Richtung")

                        # print(f"Zeta T-Stück: {zeta_t_stueck}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck



                elif check_if_lines_are_aligned(rohr, abknickende_leitung):
                    # Ausgang ---------- Rohr für Verlust
                    #              |
                    #           Eingang
                    # print("T-Stück ist Verteiler")

                    if "Ø" in abmessung_eingehende_kante:
                        zeta_t_stueck = widerstandsbeiwert_T_endstueck_rund(d=d,
                                                                            v=v,
                                                                            d_A=max(d_A, d_D),
                                                                            v_A=max(v_A, v_D)
                                                                            )
                        # Wenn der Durchmesser des Rohres kleiner ist als der des Abzweiges, muss noch eine
                        # Querschnittsverengung berücksichtigt werden
                        if d_D < d_A:
                            zeta_querschnittsverengung = widerstandsbeiwert_querschnittsverengung_stetig(d_A, d_D)
                        else:
                            zeta_querschnittsverengung = 0

                        # print(f"Zeta T-Stück: {zeta_t_stueck}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck + zeta_querschnittsverengung

                    elif "x" in abmessung_eingehende_kante:
                        width = self.finde_abmessung(abmessung_eingehende_kante)[0].to(ureg.meter)
                        height = self.finde_abmessung(abmessung_eingehende_kante)[1].to(ureg.meter)
                        zeta_t_stueck = widerstandsbeiwert_kruemmerendstueck_angular(a=height,
                                                                                   b=width,
                                                                                   d=d,
                                                                                   v=v,
                                                                                   d_A=d_D,
                                                                                   v_A=v_D
                                                                                   )

                        # print(f"Zeta T-Stück: {zeta_t_stueck}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck

                datenbank_verteilernetz.loc[datenbank_verteilernetz[
                                                'Zielknoten'] == to_junction[
                                                pipe], 'Zeta T-Stück'] = zeta_t_stueck + zeta_querschnittsverengung

        # Luftmengen aus Graphen
        luftmengen = nx.get_node_attributes(graph_luftmengen, 'weight')

        # Index der Air handling unit finden
        index_rlt = name_junction.index(tuple(building_shaft_supply_air))
        luftmenge_rlt = luftmengen[building_shaft_supply_air]
        mdot_kg_per_s_rlt = (luftmenge_rlt * dichte).to(ureg.kilogram / ureg.second)

        # Externes Grid erstellen, da dann die visualization besser ist
        pp.create_ext_grid(net, junction=index_rlt, p_bar=0, t_k=293.15, name="Air handling unit")

        # Hinzufügen der Air handling unit zum Netz
        pp.create_source(net,
                         mdot_kg_per_s=mdot_kg_per_s_rlt.magnitude,
                         junction=index_rlt,
                         p_bar=0,
                         t_k=293.15,
                         name="Air handling unit")

        liste_lueftungsauslaesse = list()

        # Hinzugen der Lüftungsauslässe
        for index, element in enumerate(luftmengen):
            if element == tuple(building_shaft_supply_air):
                continue  # Überspringt den aktuellen Durchlauf
            if element[0] == position_shaft[0] and element[1] == position_shaft[1]:
                continue
            if luftmengen[element] == 0:
                continue
            pp.create_sink(net,
                           junction=name_junction.index(element),
                           mdot_kg_per_s=(luftmengen[element] * dichte).to(ureg.kilogram / ureg.second).magnitude,
                           )
            liste_lueftungsauslaesse.append(name_junction.index(element))

        # Die eigentliche Berechnung wird mit dem pipeflow-Kommando gestartet:
        pp.pipeflow(net)

        # Bestimmung des Druckverlustes
        groesster_druckverlust = abs(net.res_junction["p_bar"].min())
        differenz = net.res_junction["p_bar"].min()

        # Identifizierung der Quelle durch ihren Namen oder Index
        source_index = net['source'].index[net['source']['name'] == "Air handling unit"][0]
        # Identifizieren des externen Grids durch seinen Namen oder Index
        ext_grid_index = net['ext_grid'].index[net['ext_grid']['name'] == "Air handling unit"][0]

        # Ändern des Druckwerts
        net['source'].at[source_index, 'p_bar'] = groesster_druckverlust
        # Ändern des Druckwerts
        net['ext_grid'].at[ext_grid_index, 'p_bar'] = groesster_druckverlust

        # Erneute Berechnung
        pp.pipeflow(net)

        groesster_druckverlust = net.res_junction["p_bar"].min()

        # Identifizierung der Quelle durch ihren Namen oder Index
        source_index = net['source'].index[net['source']['name'] == "Air handling unit"][0]
        # Identifizieren des externen Grids durch seinen Namen oder Index
        ext_grid_index = net['ext_grid'].index[net['ext_grid']['name'] == "Air handling unit"][0]

        groesster_druckverlust -= 0.00100  # 30 Pa für Lüftungsauslass und 50 Pa für Schalldämpfer + 20 Reserve

        # Ändern des Druckwerts
        net['source'].at[source_index, 'p_bar'] -= groesster_druckverlust
        # Ändern des Druckwerts
        net['ext_grid'].at[ext_grid_index, 'p_bar'] -= groesster_druckverlust

        pp.pipeflow(net)

        # Ergebnisse werden in Tabellen mit dem Präfix res_... gespeichert. Auch diese Tabellen sind nach der Berechnung im
        # net-Container abgelegt.
        dataframe_pipes = pd.concat([net.pipe, net.res_pipe], axis=1)
        dataframe_junctions = pd.concat([net.junction, net.res_junction], axis=1)

        for rohr in datenbank_verteilernetz["Kante"]:
            p_from_pa = int(dataframe_pipes.loc[dataframe_pipes["name"] == str(rohr), "p_from_bar"].iloc[0] * 100000)
            p_to_pa = int(dataframe_pipes.loc[dataframe_pipes["name"] == str(rohr), "p_to_bar"].iloc[0] * 100000)

            datenbank_verteilernetz.loc[datenbank_verteilernetz["Kante"] == rohr, "p_from_pa"] = p_from_pa
            datenbank_verteilernetz.loc[datenbank_verteilernetz["Kante"] == rohr, "p_to_pa"] = p_to_pa

        if export:
            datenbank_verteilernetz.to_excel(self.paths.export / 'supply_air' / 'Datenbank_Verteilernetz.xlsx', index=False)

        # Pfad für Speichern
        pipes_excel_pfad = self.paths.export / 'supply_air' / "Druckverlust.xlsx"

        if export == True:
            # Export
            dataframe_pipes.to_excel(pipes_excel_pfad)

            with pd.ExcelWriter(pipes_excel_pfad) as writer:
                dataframe_pipes.to_excel(writer, sheet_name="Pipes")
                dataframe_junctions.to_excel(writer, sheet_name="Junctions")

            # create additional junction collections for junctions with sink connections and junctions with valve connections
            junction_sink_collection = plot.create_junction_collection(net,
                                                                       junctions=liste_lueftungsauslaesse,
                                                                       patch_type="circle",
                                                                       size=0.12,
                                                                       color="blue")

            junction_source_collection = plot.create_junction_collection(net,
                                                                         junctions=[index_rlt],
                                                                         patch_type="circle",
                                                                         size=0.6,
                                                                         color="green")

            # create additional pipe collection
            pipe_collection = plot.create_pipe_collection(net,
                                                          linewidths=2.,
                                                          color="blue")

            collections = [junction_sink_collection, junction_source_collection, pipe_collection]

            # Zeichnen Sie die Sammlungen
            fig, ax = plt.subplots(num=f"Druckverlust", figsize=(18, 12), dpi=300)

            plot.draw_collections(collections=collections, ax=ax, axes_visible=(True, True))

            # Titel hinzufügen
            ax.set_title("Druckverlust supply_air", fontsize=14, fontweight='bold')

            # Fügt die Text-Annotationen für die Drücke hinzu
            for idx, junction in enumerate(net.res_junction.index):
                pressure = net.res_junction.iloc[idx]['p_bar']  # Druck am Knoten
                # Koordinaten des Knotens
                if junction in net.junction_geodata.index:
                    coords = net.junction_geodata.loc[junction, ['x', 'y']]
                    ax.text(coords['x'], coords['y'], f'{pressure * 100000:.0f} Pa', fontsize=10,
                            horizontalalignment='left', verticalalignment='top', rotation=-45)

            # Legenden-Einträge definieren
            legend_entries = [
                Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=10,
                       label='Lüftungsauslässe'),
                Line2D([0], [0], marker='o', color='w', markerfacecolor='green', markersize=10, label='Air handling unit'),
                Line2D([0], [0], color='blue', lw=2, label='Kanäle')
            ]

            # Legende zum Plot hinzufügen
            plt.legend(handles=legend_entries, loc="best")

            # Titel hinzufügen
            plt.title("Lüftungsschemata Druckverlust supply_air", fontsize=20)

            # Rand verkleinern
            plt.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.95)

            x_werte = []
            y_werte = []

            # Durchlaufen aller Knoten im Index von junction_geodata
            for junction in net.junction_geodata.index:
                # Direktes Auslesen der x- und y-Koordinaten für den aktuellen Knoten
                coords = net.junction_geodata.loc[junction, ['x', 'y']]
                x = coords['x']  # x-Wert direkt auslesen
                y = coords['y']  # y-Wert direkt auslesen

                # Hinzufügen der x- und y-Werte zu den jeweiligen Listen
                x_werte.append(x)
                y_werte.append(y)

            plt.xlim(min(x_werte) - 2, max(x_werte) + 2)
            plt.ylim(min(y_werte) - 2, max(y_werte) + 2)

            # Set the path for the new folder
            folder_path = Path(self.paths.export / 'supply_air')

            # Create folder
            folder_path.mkdir(parents=True, exist_ok=True)

            # save graph
            total_name = "Druckverlust supply_air" + ".png"
            path_and_name = self.paths.export / 'supply_air' / total_name
            plt.savefig(path_and_name)

            # plt.show()

            plt.close()

        return groesster_druckverlust * 100000, datenbank_verteilernetz

    def blechstaerke(self, druckverlust, abmessung):
        """
        Berechnet die Blechstärke in Abhängigkeit vom Kanal
        :param druckverlust: Durckverlust des Systems
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
            width, height = self.finde_abmessung(abmessung)
            laengste_kante = max(width.to(ureg.meter), height.to(ureg.meter))

            if druckverlust <= 1000:
                if laengste_kante <= 0.500 * ureg.meter:
                    blechstaerke = (0.6 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 0.500 * ureg.meter < laengste_kante <= 1.000 * ureg.meter:
                    blechstaerke = (0.8 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < laengste_kante <= 2.000 * ureg.meter:
                    blechstaerke = (1.0 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

            elif 1000 < druckverlust <= 2000:
                if laengste_kante <= 0.500 * ureg.meter:
                    blechstaerke = (0.7 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 0.500 * ureg.meter < laengste_kante <= 1.000 * ureg.meter:
                    blechstaerke = (0.9 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < laengste_kante <= 2.000 * ureg.meter:
                    blechstaerke = (1.1 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

            elif 2000 < druckverlust <= 3000:
                if laengste_kante <= 1.000 * ureg.meter:
                    blechstaerke = (0.95 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < laengste_kante <= 2.000 * ureg.meter:
                    blechstaerke = (1.15 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

        return blechstaerke

    def raumanbindung(self, cross_section_type, suspended_ceiling_space, dataframe_rooms):

        # Ermittlung des Kanalquerschnittes
        dataframe_rooms["duct_cross_section"] = \
            dataframe_rooms.apply(lambda row: self.dimensions_ventilation_duct(cross_section_type,
                                                                     self.required_ventilation_duct_cross_section(
                                                                         row["Volume_flow"]),
                                                                     suspended_ceiling_space),
                                  axis=1
                                  )

        # Ermittung der Abmessungen
        dataframe_rooms['Leitungslänge'] = 2 * ureg.meter
        dataframe_rooms['Durchmesser'] = None
        dataframe_rooms['width'] = None
        dataframe_rooms['Höhe'] = None

        for index, duct_cross_section in enumerate(dataframe_rooms["duct_cross_section"]):
            if "Ø" in duct_cross_section:
                dataframe_rooms.at[index, 'Durchmesser'] = self.finde_abmessung(duct_cross_section)

            elif "x" in duct_cross_section:
                dataframe_rooms.at[index, 'width'] = self.finde_abmessung(duct_cross_section)[0]
                dataframe_rooms.at[index, 'Höhe'] = self.finde_abmessung(duct_cross_section)[1]

        dataframe_rooms["Mantelfläche"] = dataframe_rooms.apply(
            lambda row: self.coat_area_ventilation_duct(
                cross_section_type,
                self.required_ventilation_duct_cross_section(row["Volume_flow"]),
                suspended_ceiling_space
            ) * row["Leitungslänge"], axis=1)

        dataframe_rooms["rechnerischer Durchmesser"] = dataframe_rooms.apply(
            lambda row: self.calculated_diameter(cross_section_type,
                                                       self.required_ventilation_duct_cross_section(row["Volume_flow"]),
                                                       suspended_ceiling_space), axis=1)

        # Ermittlung der Blechstärke
        dataframe_rooms["Blechstärke"] = dataframe_rooms.apply(
            lambda row: self.blechstaerke(70, row["duct_cross_section"]), axis=1)

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
        dataframe_rooms['Schalldämpfer'] = dataframe_rooms['room type'].apply(
            lambda x: 1 if x in liste_raeume_schalldaempfer else 0)

        # Volumenstromregler
        dataframe_rooms["Volumenstromregler"] = 1

        # Berechnung des Blechvolumens
        dataframe_rooms["Blechvolumen"] = dataframe_rooms["Blechstärke"] * dataframe_rooms["Mantelfläche"]

        list_dataframe_rooms_blechgewicht = [v * (7850 * ureg.kilogram / ureg.meter ** 3) for v in
                                             dataframe_rooms["Blechvolumen"]]
        # Dichte Stahl 7850 kg/m³

        # Berechnung des Blechgewichts
        dataframe_rooms["Blechgewicht"] = list_dataframe_rooms_blechgewicht

        return dataframe_rooms

    def co2(self,
            export,
            druckverlust,
            dataframe_rooms,
            dataframe_distribution_network_supply_air):

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
        Berechnung des CO2 des Lüftungsverteilernetztes des Blechs der supply_air des Verteilernetzes
        """
        # Ermittlung der Blechstärke
        dataframe_distribution_network_supply_air["Blechstärke"] = dataframe_distribution_network_supply_air.apply(
            lambda row: self.blechstaerke(druckverlust, row["duct_cross_section"]), axis=1)

        # Berechnung des Blechvolumens
        dataframe_distribution_network_supply_air["Blechvolumen"] = dataframe_distribution_network_supply_air[
                                                                        "Blechstärke"] * \
                                                                    dataframe_distribution_network_supply_air[
                                                                        "Mantelfläche"]

        list_dataframe_distribution_network_supply_air_blechgewicht = [v * (7850 * ureg.kilogram / ureg.meter ** 3) for
                                                                       v in
                                                                       dataframe_distribution_network_supply_air[
                                                                           "Blechvolumen"]]
        # Dichte Stahl 7850 kg/m³

        # Berechnung des Blechgewichts
        dataframe_distribution_network_supply_air[
            "Blechgewicht"] = list_dataframe_distribution_network_supply_air_blechgewicht

        # Ermittlung des CO2-Kanal
        dataframe_distribution_network_supply_air["CO2-Kanal"] = dataframe_distribution_network_supply_air[
                                                                     "Blechgewicht"] * (
                                                                         float(
                                                                             gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[
                                                                                 0]["A1-A3"]) + float(
                                                                     gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0][
                                                                         "C2"]))

        def querschnittsflaeche_kanaldaemmung(row):
            """
            Berechnet die Querschnittsfläche der Dämmung
            """
            querschnittsflaeche = 0
            if 'Ø' in row['duct_cross_section']:
                try:
                    durchmesser = ureg(row['Durchmesser'])
                except AttributeError:
                    durchmesser = row['Durchmesser']
                querschnittsflaeche = math.pi * ((durchmesser + 0.04 * ureg.meter) ** 2) / 4 - math.pi * (
                        durchmesser ** 2) / 4  # 20mm Dämmung des Lüftungskanals nach anerkanten
                # Regeln der Technik nach Missel Seite 42

            elif 'x' in row['duct_cross_section']:
                try:
                    width = ureg(row['width'])
                    height = ureg(row['Höhe'])
                except AttributeError:
                    width = row['width']
                    height = row['Höhe']
                querschnittsflaeche = ((width + 0.04 * ureg.meter) * (height + 0.04 * ureg.meter)) - (
                        width * height)  # 20mm Dämmung des Lüftungskanals nach anerkanten Regeln der Technik nach Missel Seite 42

            return querschnittsflaeche.to(ureg.meter ** 2)

        # Berechnung der Dämmung
        dataframe_distribution_network_supply_air[
            'Querschnittsfläche Dämmung'] = dataframe_distribution_network_supply_air.apply(
            querschnittsflaeche_kanaldaemmung, axis=1)

        dataframe_distribution_network_supply_air['Volumen Dämmung'] = dataframe_distribution_network_supply_air[
                                                                           'Querschnittsfläche Dämmung'] * \
                                                                       dataframe_distribution_network_supply_air[
                                                                           'Leitungslänge']

        gwp_daemmung = (
                    121.8 * ureg.kilogram / ureg.meter ** 3 + 1.96 * ureg.kilogram / ureg.meter ** 3 + 10.21 * ureg.kilogram / ureg.meter ** 3)
        # https://www.oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?lang=de&uuid=eca9691f-06d7-48a7-94a9-ea808e2d67e8

        list_dataframe_distribution_network_supply_air_CO2_kanaldaemmung = [v * gwp_daemmung for v in
                                                                            dataframe_distribution_network_supply_air[
                                                                                "Volumen Dämmung"]]

        dataframe_distribution_network_supply_air[
            "CO2-Kanaldämmung"] = list_dataframe_distribution_network_supply_air_CO2_kanaldaemmung

        if export:
            # Export to Excel
            dataframe_distribution_network_supply_air.to_excel(
                self.paths.export / 'supply_air' / 'Datenbank_Verteilernetz.xlsx', index=False)

        """
        Berechnung des CO2 für die Raumanbindung
        """
        # Ermittlung des CO2-Kanal
        dataframe_rooms["CO2-Kanal"] = dataframe_rooms["Blechgewicht"] * (
                    float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0][
                              "A1-A3"]) + float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"])
                    )

        # Vordefinierte Daten für Trox RN Volumenstromregler
        # https://cdn.trox.de/4ab7c57caaf55be6/3450dc5eb9d7/TVR_PD_2022_08_03_DE_de.pdf
        trox_tvr_durchmesser_gewicht = {
            'Durchmesser': [100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter, 200 * ureg.millimeter,
                            250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter],
            'Gewicht': [3.3 * ureg.kilogram, 3.6 * ureg.kilogram, 4.2 * ureg.kilogram, 5.1 * ureg.kilogram,
                        6.1 * ureg.kilogram, 7.2 * ureg.kilogram, 9.4 * ureg.kilogram]
        }
        df_trox_tvr_durchmesser_gewicht = pd.DataFrame(trox_tvr_durchmesser_gewicht)

        # Funktion, um das nächstgrößere Gewicht zu finden
        def gewicht_runde_volumenstromregler(row):
            if row['Volumenstromregler'] == 1 and 'Ø' in row['duct_cross_section']:
                calculated_diameter = row['rechnerischer Durchmesser']
                next_durchmesser = df_trox_tvr_durchmesser_gewicht[
                    df_trox_tvr_durchmesser_gewicht['Durchmesser'] >= calculated_diameter]['Durchmesser'].min()
                return \
                    df_trox_tvr_durchmesser_gewicht[df_trox_tvr_durchmesser_gewicht['Durchmesser'] == next_durchmesser][
                        'Gewicht'].values[0]
            return None

        # Tabelle mit width, Höhe und Gewicht für Trox TVJ Volumenstromregler
        # https://cdn.trox.de/502e3cb43dff27e2/af9a822951e1/TVJ_PD_2021_07_19_DE_de.pdf
        df_trox_tvj_durchmesser_gewicht = pd.DataFrame({
            'width': [200 * ureg.millimeter, 300 * ureg.millimeter, 400 * ureg.millimeter, 500 * ureg.millimeter,
                       600 * ureg.millimeter,

                       200 * ureg.millimeter, 300 * ureg.millimeter, 400 * ureg.millimeter, 500 * ureg.millimeter,
                       600 * ureg.millimeter, 700 * ureg.millimeter, 800 * ureg.millimeter,

                       300 * ureg.millimeter, 400 * ureg.millimeter, 500 * ureg.millimeter, 600 * ureg.millimeter,
                       700 * ureg.millimeter, 800 * ureg.millimeter, 900 * ureg.millimeter, 1000 * ureg.millimeter,

                       400 * ureg.millimeter, 500 * ureg.millimeter, 600 * ureg.millimeter, 700 * ureg.millimeter,
                       800 * ureg.millimeter, 900 * ureg.millimeter, 1000 * ureg.millimeter
                       ],

            'Höhe': [100 * ureg.millimeter, 100 * ureg.millimeter, 100 * ureg.millimeter, 100 * ureg.millimeter,
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
            if row['Volumenstromregler'] == 1 and 'x' in row['duct_cross_section']:
                width, height = row['width'], row['Höhe']
                passende_zeilen = df_trox_tvj_durchmesser_gewicht[
                    (df_trox_tvj_durchmesser_gewicht['width'] >= width) & (
                            df_trox_tvj_durchmesser_gewicht['Höhe'] >= height)]
                if not passende_zeilen.empty:
                    return passende_zeilen.sort_values(by=['width', 'Höhe', 'Gewicht']).iloc[0]['Gewicht']
            return None

        # Kombinierte Funktion, die beide Funktionen ausführt
        def gewicht_volumenstromregler(row):
            gewicht_rn = gewicht_runde_volumenstromregler(row)
            if gewicht_rn is not None:
                return gewicht_rn
            return gewicht_angulare_volumenstromregler(row)

        # Anwenden der Funktion auf jede Zeile
        dataframe_rooms['Gewicht Volumenstromregler'] = dataframe_rooms.apply(gewicht_volumenstromregler, axis=1)

        dataframe_rooms["CO2-Volumenstromregler"] = dataframe_rooms['Gewicht Volumenstromregler'] * (
                19.08 + 0.01129 + 0.647) * 0.348432
        # Nach Ökobaudat https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=29e922f6-d872-4a67-b579-38bb8cd82abf&version=00.02.000&stock=OBD_2023_I&lang=de

        # CO2 für Schallfämpfer
        # Tabelle Daten für Berechnung nach Trox CA
        # https://cdn.trox.de/97af1ba558b3669e/e3aa6ed495df/CA_PD_2023_04_26_DE_de.pdf
        durchmesser_tabelle = pd.DataFrame({
            'Durchmesser': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter,
                            200 * ureg.millimeter, 250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter,
                            450 * ureg.millimeter, 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                            710 * ureg.millimeter, 800 * ureg.millimeter],
            'Innendurchmesser': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter,
                                 160 * ureg.millimeter, 200 * ureg.millimeter, 250 * ureg.millimeter,
                                 315 * ureg.millimeter, 400 * ureg.millimeter, 450 * ureg.millimeter,
                                 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                                 710 * ureg.millimeter, 800 * ureg.millimeter],
            'Aussendurchmesser': [184 * ureg.millimeter, 204 * ureg.millimeter, 228 * ureg.millimeter,
                                  254 * ureg.millimeter, 304 * ureg.millimeter, 354 * ureg.millimeter,
                                  405 * ureg.millimeter, 505 * ureg.millimeter, 636 * ureg.millimeter,
                                  716 * ureg.millimeter, 806 * ureg.millimeter, 806 * ureg.millimeter,
                                  908 * ureg.millimeter, 1008 * ureg.millimeter]
        })

        # Funktion zur Berechnung der Fläche des Kreisrings
        def volumen_daemmung_schalldaempfer(row):
            calculated_diameter = row['rechnerischer Durchmesser']
            passende_zeilen = durchmesser_tabelle[durchmesser_tabelle['Durchmesser'] >= calculated_diameter]
            if not passende_zeilen.empty:
                naechster_durchmesser = passende_zeilen.iloc[0]
                innen = naechster_durchmesser['Innendurchmesser']
                aussen = naechster_durchmesser['Aussendurchmesser']
                volumen = math.pi * (aussen ** 2 - innen ** 2) / 4 * 0.88 * ureg.meter  # Für einen Meter Länge des
                # Schalldämpfers, entspricht nach Datenblatt einer Länge des Dämmkerns von 0.88m,
                return volumen.to(ureg.meter ** 3)
            return None

        # Gewicht Dämmung Schalldämpfer
        dataframe_rooms['Volumen Dämmung Schalldämpfer'] = dataframe_rooms.apply(volumen_daemmung_schalldaempfer,
                                                                                 axis=1)

        gwp_daemmung_schalldaempfer = (117.4 + 2.132 + 18.43) * (ureg.kilogram / (ureg.meter ** 3))
        # https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=89b4bfdf-8587-48ae-9178-33194f6d1314&version=00.02.000&stock=OBD_2023_I&lang=de

        list_dataframe_distribution_network_supply_air_CO2_schalldaempferdaemmung = [v * gwp_daemmung_schalldaempfer for
                                                                                     v in dataframe_rooms[
                                                                                         "Volumen Dämmung Schalldämpfer"]]

        dataframe_rooms[
            "CO2-Dämmung Schalldämpfer"] = list_dataframe_distribution_network_supply_air_CO2_schalldaempferdaemmung

        # Gewicht des Metalls des Schalldämpfers für Trox CA für Packungsdicke 50 bis 400mm danach Packungsdicke 100
        # vordefinierte Daten für Trox CA Schalldämpfer
        trox_ca_durchmesser_gewicht = {
            'Durchmesser': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter,
                            200 * ureg.millimeter, 250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter,
                            450 * ureg.millimeter, 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                            710 * ureg.millimeter, 800 * ureg.millimeter],
            'Gewicht': [6 * ureg.kilogram, 6 * ureg.kilogram, 7 * ureg.kilogram, 8 * ureg.kilogram, 10 * ureg.kilogram,
                        12 * ureg.kilogram, 14 * ureg.kilogram, 18 * ureg.kilogram, 24 * ureg.kilogram,
                        28 * ureg.kilogram, 45 * ureg.kilogram * 2 / 3, 47 * ureg.kilogram * 2 / 3,
                        54 * ureg.kilogram * 2 / 3, 62 * ureg.kilogram * 2 / 3]
        }
        df_trox_ca_durchmesser_gewicht = pd.DataFrame(trox_ca_durchmesser_gewicht)

        # Funktion, um das nächstgrößere Gewicht zu finden
        def gewicht_schalldaempfer_ohne_daemmung(row):
            if row['Schalldämpfer'] == 1:
                calculated_diameter = row['rechnerischer Durchmesser']
                passende_zeilen = df_trox_ca_durchmesser_gewicht[
                    df_trox_ca_durchmesser_gewicht['Durchmesser'] >= calculated_diameter]
                if not passende_zeilen.empty:
                    next_durchmesser = passende_zeilen['Durchmesser'].min()
                    gewicht_schalldaempfer = \
                        df_trox_ca_durchmesser_gewicht[
                            df_trox_ca_durchmesser_gewicht['Durchmesser'] == next_durchmesser][
                            'Gewicht'].values[0]
                    daemmung_gewicht = row[
                        "Gewicht Dämmung Schalldämpfer"] if "Gewicht Dämmung Schalldämpfer" in row and not pd.isnull(
                        row["Gewicht Dämmung Schalldämpfer"]) else 0
                    return gewicht_schalldaempfer - daemmung_gewicht
            return None

        dataframe_rooms['Gewicht Blech Schalldämpfer'] = dataframe_rooms.apply(gewicht_schalldaempfer_ohne_daemmung,
                                                                               axis=1)

        dataframe_rooms["CO2-Blech Schalldämfer"] = dataframe_rooms["Gewicht Blech Schalldämpfer"] * (
                float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["A1-A3"]) + float(
            gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"]))

        # Berechnung der Dämmung
        dataframe_rooms['Querschnittsfläche Dämmung'] = dataframe_rooms.apply(querschnittsflaeche_kanaldaemmung,
                                                                              axis=1)

        dataframe_rooms['Volumen Dämmung'] = dataframe_rooms['Querschnittsfläche Dämmung'] * dataframe_rooms[
            'Leitungslänge']

        gwp_kanaldaemmung = (
                    121.8 * (ureg.kilogram / ureg.meter ** 3) + 1.96 * (ureg.kilogram / ureg.meter ** 3) + 10.21 * (
                        ureg.kilogram / ureg.meter ** 3))
        # https://www.oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?lang=de&uuid=eca9691f-06d7-48a7-94a9-ea808e2d67e8

        list_dataframe_rooms_CO2_kanaldaemmung = [v * gwp_kanaldaemmung for v in dataframe_rooms["Volumen Dämmung"]]

        dataframe_rooms['CO2-Kanaldämmung'] = list_dataframe_rooms_CO2_kanaldaemmung

        if export:
            # Export to Excel
            dataframe_rooms.to_excel(self.paths.export / 'supply_air' / 'Datenbank_Raumanbindung.xlsx', index=False)

        return druckverlust, dataframe_rooms, dataframe_distribution_network_supply_air
