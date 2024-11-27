from matplotlib.lines import Line2D
import bim2sim
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
from pint import Quantity
import ifcopenshell.geom
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.gp import gp_Pnt
from OCC.Core.TopAbs import TopAbs_IN, TopAbs_ON


class DesignSupplyLCA(ITask):
    """Design of the LCA

    Assumptions:
    Inputs: IFC Modell, Räume,

    Args:
        elements: bim2sim elements
    Returns:
        elements: bim2sim
    """
    reads = ('elements',)
    touches = ('dataframe_rooms',
               'building_shaft_supply_air',
               'graph_ventilation_duct_length_supply_air',
               'pressure_loss_supply_air',
               'dataframe_rooms_supply_air',
               'dataframe_distribution_network_supply_air',
               'dict_steiner_tree_with_air_volume_supply_air',
               'z_coordinate_list',
               'dict_steiner_tree_with_duct_cross_section'
               )

    def run(self, elements):

        self.elements = elements
        main_line = [(1.6, 8, -0.3), (41, 8, -0.3), (41, 2.8, -0.3),
                     (1.6, 8, 2.7), (41, 8, 2.7), (41, 2.8, 2.7),
                     (1.6, 8, 5.7), (41, 8, 5.7), (41, 2.8, 5.7),
                     (1.6, 8, 8.7), (41, 8, 8.7), (41, 2.8, 8.7)]

        self.export_graphs = self.playground.sim_settings.export_graphs

        building_shaft_supply_air = [41, 2.8, -2]  # building shaft supply air
        position_ahu = [25, building_shaft_supply_air[1], building_shaft_supply_air[2]]
        # y-axis of shaft and AHU must be identical
        cross_section_type = "optimal"  # Wähle zwischen round, angular und optimal
        suspended_ceiling_space = 200 * ureg.millimeter  # The available height (in [mmm]) in the suspended ceiling is
        # specified here! This corresponds to the available distance between UKRD (lower edge of raw ceiling) and OKFD
        # (upper edge of finished ceiling), see https://www.ctb.de/_wiki/swb/Massbezuege.php

        self.logger.info("Start design LCA")
        thermal_zones = filter_elements(self.elements, 'ThermalZone')
        thermal_zones = [tz for tz in thermal_zones if tz.ventilation_system == True]

        self.logger.info("Checking ceiling height for each room")
        self.check_ceiling_height(thermal_zones, suspended_ceiling_space)

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

        self.logger.info("Calculating the Coordinates of the ceiling heights")
        # Here the coordinates of the heights at the UKRD are calculated and summarized in a set, as these values are
        # frequently needed in the further course, so they do not have to be recalculated again and again:
        z_coordinate_list = self.calculate_z_coordinate(center)

        self.logger.info("Sort ventilation outlets at ceiling by space type")
        #center_points_traffic_area, center_points_non_traffic_area = self.sort_center_points_by_space(
        #    dataframe_rooms, center, z_coordinate_list, building_shaft_supply_air)

        self.logger.info("Calculating intersection points")
        # The intersections of all points per storey are calculated here. A grid is created on the respective storey.
        # It is defined as the installation grid for the supply air. The individual points of the ventilation outlets
        # are not connected directly, but in practice and according to the standard, ventilation ducts are not laid
        # diagonally through a building
        intersection_points = self.intersection_points(center,
                                                       z_coordinate_list
                                                       )
        self.logger.info("Calculating intersection points successful")

        intersection_points_main_line = self.intersection_points(main_line,
                                                                 z_coordinate_list
                                                                 )
        self.logger.info("Create main graph in traffic areas for each floor")

        main_line_graph = self.create_main_graph(main_line,
                                                 intersection_points_main_line,
                                                 z_coordinate_list,
                                                 building_shaft_supply_air)

        self.logger.info("Graph created for each floor")

        (dict_steiner_tree_with_duct_length,
         dict_steiner_tree_with_duct_cross_section,
         dict_steiner_tree_with_air_volume_supply_air,
         dict_steinertree_with_shell,
         dict_steiner_tree_with_calculated_cross_section) = self.create_graph(main_line_graph,
                                                                              center,
                                                                              z_coordinate_list,
                                                                              building_shaft_supply_air,
                                                                              cross_section_type,
                                                                              suspended_ceiling_space,)

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
                                                                           dict_steiner_tree_with_calculated_cross_section)

        self.logger.info("3D-Graph erstellen")
        (graph_ventilation_duct_length_supply_air,
         graph_luftmengen,
         graph_kanalquerschnitt,
         graph_mantelflaeche,
         graph_calculated_diameter,
         dataframe_distribution_network_supply_air) = self.three_dimensional_graph(dict_steiner_tree_with_duct_length,
                                                                                    dict_steiner_tree_with_duct_cross_section,
                                                                                    dict_steiner_tree_with_air_volume_supply_air,
                                                                                    dict_steinertree_with_shell,
                                                                                    dict_steiner_tree_with_calculated_cross_section,
                                                                                    position_ahu,
                                                                                    dict_coordinate_with_space_type)
        self.logger.info("3D-Graph erstellt")

        self.logger.info("Starte pressure_lossberechnung")
        pressure_loss, dataframe_distribution_network_supply_air = self.pressure_loss(dict_steiner_tree_with_duct_length,
                                                                                    z_coordinate_list,
                                                                                    position_ahu,
                                                                                    building_shaft_supply_air,
                                                                                    graph_ventilation_duct_length_supply_air,
                                                                                    graph_luftmengen,
                                                                                    graph_kanalquerschnitt,
                                                                                    graph_mantelflaeche,
                                                                                    graph_calculated_diameter,
                                                                                    dataframe_distribution_network_supply_air
                                                                                    )
        self.logger.info("pressure_lossberechnung erfolgreich")

        self.logger.info("Starte Berechnung der room_connection")
        dataframe_rooms = self.room_connection(cross_section_type, suspended_ceiling_space, dataframe_rooms)

        self.logger.info("Starte C02 Berechnung")
        (pressure_loss_supply_air,
         dataframe_rooms_supply_air,
         dataframe_distribution_network_supply_air) = self.co2(pressure_loss,
                                                               dataframe_rooms,
                                                               dataframe_distribution_network_supply_air)

        return (dataframe_rooms,
                building_shaft_supply_air,
                graph_ventilation_duct_length_supply_air,
                pressure_loss_supply_air,
                dataframe_rooms_supply_air,
                dataframe_distribution_network_supply_air,
                dict_steiner_tree_with_air_volume_supply_air,
                z_coordinate_list,
                dict_steiner_tree_with_duct_cross_section)

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

    def check_ceiling_height(self, thermal_zones, suspended_ceiling_space):
        min_ceiling_height = 3 * ureg.meter
        for tz in thermal_zones:
            if tz.height - suspended_ceiling_space < min_ceiling_height:
                self.logger.warning(f"Room {tz.name} (GUID: {tz.guid}) short of minimum ceiling height!")

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
            if tz.with_ahu:
                room_ceiling_ventilation_outlet.append([self.round_decimal(tz.space_center.X(), 1),
                                                        self.round_decimal(tz.space_center.Y(), 1),
                                                        self.round_decimal(tz.space_center.Z() + tz.height.magnitude / 2,
                                                                           2),
                                                        math.ceil(tz.air_flow.to(ureg.meter ** 3 / ureg.hour).magnitude) * (
                                                                    ureg.meter ** 3 / ureg.hour),
                                                       tz.usage])
                room_type.append(tz.usage)

        # As the points are not exactly in line, although the rooms are actually next to each other, but some rooms are slightly different depths, the coordinates must be adjusted. In reality, a small shift of the ventilation outlet will not cause a major change, as the ventilation outlets are either connected with a flexible hose or directly from the main duct.
        # Z-axes
        z_axis = set()
        for i in range(len(room_ceiling_ventilation_outlet)):
            z_axis.add(room_ceiling_ventilation_outlet[i][2])

        # Creates a Dictonary sorted by Z-coordinates
        grouped_coordinates_x = {}
        for x, y, z, a, u in room_ceiling_ventilation_outlet:
            if z not in grouped_coordinates_x:
                grouped_coordinates_x[z] = []
            grouped_coordinates_x[z].append((x, y, z, a, u))

        # Adjust the coordinates in x-coordinate
        adjusted_coords_x = []
        for z_coord in z_axis:
            sort = sorted(grouped_coordinates_x[z_coord], key=lambda coord: (coord[0], coord[1]))

            i = 0
            while i < len(sort):
                x1, y1, z1, a1, u1 = sort[i]
                total_x = x1
                count = 1

                j = i + 1
                while j < len(sort) and sort[j][0] - x1 <= 0.75:
                    total_x += sort[j][0]
                    count += 1
                    j += 1

                x_avg = total_x / count
                for _ in range(i, j):
                    _, y, z, a, u = sort[i]
                    adjusted_coords_x.append((self.round_decimal(x_avg, 1), y, z, a, u))
                    i += 1

        # Creates a Dictonary sorted by Z-coordinates
        grouped_coordinates_y = {}
        for x, y, z, a, u in adjusted_coords_x:
            if z not in grouped_coordinates_y:
                grouped_coordinates_y[z] = []
            grouped_coordinates_y[z].append((x, y, z, a, u))

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
                    x, _, z, a, u = room_ceiling_ventilation_outlet[k]
                    adjusted_coords_y.append((x, self.round_decimal(average_y, 1), z, a, u))

                # Update the outer loop variable i to the next unprocessed index
                i = j

        room_ceiling_ventilation_outlet = adjusted_coords_y

        dict_coordinate_with_space_type = dict()
        for index, coordinate in enumerate(room_ceiling_ventilation_outlet):
            usage = coordinate[4]
            coordinate = (coordinate[0], coordinate[1], coordinate[2])
            dict_coordinate_with_space_type[coordinate] = usage

        dict_koordinate_mit_erf_luftvolumen = dict()
        for index, coordinate in enumerate(room_ceiling_ventilation_outlet):
            airflow_room = coordinate[3]
            coordinate = (coordinate[0], coordinate[1], coordinate[2])
            dict_koordinate_mit_erf_luftvolumen[coordinate] = airflow_room

        room_ceiling_ventilation_outlet = [t[:-1] for t in room_ceiling_ventilation_outlet]

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

    def sort_center_points_by_space(self, dataframe_rooms, ceiling_points, z_coordinate_list, building_shaft_supply_air):
        ceiling_points_in_traffic_area = []
        ceiling_points_not_in_traffic_area = []
        for i in range(0, len(dataframe_rooms)):
            if dataframe_rooms["room type"][i] == "Traffic area":
                ceiling_points_in_traffic_area.append(ceiling_points[i])
            else:
                ceiling_points_not_in_traffic_area.append(ceiling_points[i])

        ceiling_points_in_traffic_area.extend(ceiling_points[-len(z_coordinate_list):])

        return ceiling_points_in_traffic_area, ceiling_points_not_in_traffic_area

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


    def write_json_graph(self, graph, filename):

        for edge in graph.edges(data=True):
            for attr, value in edge[2].items():
                if isinstance(value, Quantity):
                    graph.edges[(edge[0],edge[1])][attr] = value.magnitude
        for node in graph.nodes(data=True):
            for attr, value in node[1].items():
                if isinstance(value, Quantity):
                    graph.nodes[node[0]][attr] = value.magnitude

        filepath = self.paths.export / 'ventilation system' / 'supply air'
        filepath.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Read {filename} Graph from file {filepath}")
        data = json_graph.node_link_data(graph)
        with open(filepath / filename, 'w') as f:
            json.dump(data, f, indent=4)

    def visualization_graph(self,
                             G,
                             graph_steiner_tree,
                             z_value,
                             coordinates_without_airflow,
                             filtered_coords_ceiling_without_airflow,
                             filtered_coords_intersection_without_airflow,
                             edge_label,
                             name,
                             unit_edge,
                             total_coat_area,
                             building_shaft_supply_air
                             ):
        """
        :param G: Graph
        :param graph_steiner_tree: Steinerbaum
        :param z_value: Z-Achse
        :param coordinates_without_airflow: Schnittpunkte
        :param filtered_coords_ceiling_without_airflow: Koordinaten ohne Volume_flow
        :param filtered_coords_intersection_without_airflow: Schnittpunkte ohne Volume_flow
        :param name: Diagrammbezeichnung
        :param unit_edge: Einheit der Kante für Legende Diagramm
        :param total_coat_area: gesamte Fläche des Kanalmantels
        """
        # visualization
        plt.figure(figsize=(8.3, 5.8) )
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
                               node_shape='s',
                               node_color='blue',
                               node_size=10)
        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=[(building_shaft_supply_air[0], building_shaft_supply_air[1], z_value)],
                               node_shape="s",
                               node_color="green",
                               node_size=10)
        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=filtered_coords_intersection_without_airflow,
                               node_shape='o',
                               node_color='red',
                               node_size=10)


        # draw edges
        nx.draw_networkx_edges(G, pos, width=1)
        nx.draw_networkx_edges(graph_steiner_tree, pos, width=1, style="-", edge_color="blue")

        # edge weight
        edge_labels = nx.get_edge_attributes(graph_steiner_tree, edge_label)
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
        """
        nx.draw_networkx_edge_labels(graph_steiner_tree,
                                     pos,
                                     edge_labels=edge_labels_without_unit,
                                     # label_pos=0.5,  # Positioniere die Beschriftung in der Mitte der Kante
                                     verticalalignment='bottom',  # Ausrichtung der Beschriftung unterhalb der Kante
                                     # horizontalalignment='center',
                                     font_size=8,
                                     font_weight=10,
                                     rotate=90,
                                     clip_on=False
                                     )

        # show node weight
        node_labels = nx.get_node_attributes(G, 'weight')
        node_labels_without_unit = dict()
        for key, value in node_labels.items():
            try:
                node_labels_without_unit[key] = f"{value.magnitude}"
            except AttributeError:
                node_labels_without_unit[key] = ""
        nx.draw_networkx_labels(G, pos, labels=node_labels_without_unit, font_size=8, font_color="white")
        """
        # Create legend
        legend_ceiling = plt.Line2D([0], [0], marker='s', color='w', label='Lüftungsauslass  in m³ pro h',
                                    markerfacecolor='blue',
                                    markersize=10)
        # legend_intersection = plt.Line2D([0], [0], marker='o', color='w', label='Schnittpunkt',
        #                                  markerfacecolor='red', markersize=6)
        legend_shaft = plt.Line2D([0], [0], marker='s', color='w', label='Schacht',
                                  markerfacecolor='green', markersize=10)
        legend_steiner_edge = plt.Line2D([0], [0], color='blue', lw=1, linestyle='-',
                                         label=f'Steinerkante in {unit_edge}')

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
        #plt.legend(handles=[legend_ceiling, legend_intersection, legend_shaft, legend_steiner_edge],
        #           loc='best',
        #           fontsize=8)  # , bbox_to_anchor=(1.1, 0.5)

        # Set the path for the new folder
        folder_path = Path(self.paths.export / 'ventilation system' / 'supply air' / 'plots' / f"Z_{z_value}")

        # create folder
        folder_path.mkdir(parents=True, exist_ok=True)

        # save graph
        total_name = name + "_Zuluft_Z" + f"{z_value}" + ".png"
        path_and_name = folder_path / total_name
        plt.gca().patch.set_alpha(0)
        plt.xlim(-5,50)
        plt.ylim(-5,30)
        plt.savefig(path_and_name, format='png', transparent=True)

        # how graph
        # plt.show()

        # close graph
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

    def dimensions_ventilation_duct(self, cross_section_type, duct_cross_section, suspended_ceiling_space=2000 * ureg.millimeter):
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

    def euclidean_distance(self, point1, point2):
        """
        Calculating the distance between point1 and 2
        :param point1: starting point
        :param point2: target point
        :return: Distance between point1 and point2
        """
        return round(
            math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2),
            2)


    def find_leaves(self, spanning_tree):
        """
        Find leaves in the steiner tree. Leaves have only one connected edge
        :param spanning_tree: NetworkX Graph
        :return: Leaves as list
        """
        leaves = []
        for node in spanning_tree:
            if len(spanning_tree[node]) == 1:  # A leaf has only one neighbor
                leaves.append(node)
        return leaves

    def create_main_graph(self, main_line_points, main_line_intersection_points, z_coordinate_list, starting_point):

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

        main_line_graph = {}

        for z_value in z_coordinate_list:

            # Here the coordinates are filtered by level
            filtered_coords_main_line = [coord for coord in main_line_points if coord[2] == z_value]
            filtered_coords_intersection = [coord[:-1] for coord in main_line_intersection_points if coord[2] ==
            z_value]
            coordinates = filtered_coords_intersection + filtered_coords_main_line

            coordinates_without_airflow = (filtered_coords_main_line
                                           + filtered_coords_intersection)

            # Creates the graphs
            G = nx.Graph()

            # Terminals:
            # Terminals are the predefined nodes in a graph that must be connected in the solution of the Steiner tree problem
            terminals = list()

            # Add the nodes for ventilation outlets to terminals
            for x, y, z in filtered_coords_main_line:
                if x == starting_point[0] and y == starting_point[1]:
                    G.add_node((x, y, z), pos=(x, y, z), weight=0, color="green")
                else:
                    G.add_node((x, y, z), pos=(x, y, z), weight=0, color="blue")
                terminals.append((x, y, z))

            for x, y, z in filtered_coords_intersection:
                G.add_node((x, y, z), pos=(x, y, z), weight=0, color="red")

            # Add edges along the X-axis
            unique_coords = set(coord[0] for coord in coordinates_without_airflow)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in coordinates_without_airflow if coord[0] == u],
                                            key=lambda c: c[1 - 0])
                for i in range(len(nodes_on_same_axis) - 1):
                    if not G.has_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1]):
                        weight_edge_y = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                        G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], length=weight_edge_y)

            # Add edges along the Y-axis
            unique_coords = set(coord[1] for coord in coordinates_without_airflow)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in coordinates_without_airflow if coord[1] == u],
                                            key=lambda c: c[1 - 1])
                for i in range(len(nodes_on_same_axis) - 1):
                    if not G.has_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1]):
                        weight_edge_x = self.euclidean_distance(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                        G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], length=weight_edge_x)

            # Create Steiner tree
            graph_steiner_tree = steiner_tree(G, terminals, weight="length")

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_main_line,
                                         filtered_coords_intersection,
                                         edge_label="length",
                                         name=f"Steinerbaum 0. Optimierung",
                                         unit_edge="m",
                                         total_coat_area=False,
                                         building_shaft_supply_air=starting_point
                                         )

            # Extraction of the nodes and edges from the Steiner tree
            nodes = list(graph_steiner_tree.nodes())
            edges = list(graph_steiner_tree.edges())

            # Create Tree
            tree = nx.Graph()

            # Add nodes to the tree
            for x, y, z in nodes:
                for point in coordinates:
                    if point[0] == x and point[1] == y and point[2] == z:
                        tree.add_node((x, y, z), pos=(x, y, z), weight=0)

            # Add edges to the tree
            for kante in edges:
                tree.add_edge(kante[0], kante[1], length=self.euclidean_distance(kante[0], kante[1]))

            # The minimum spanning tree of the Steiner tree is calculated here
            minimum_spanning_tree = nx.minimum_spanning_tree(tree)

            """Optimization step 1"""
            # This checks which points along a path lie on an axis. The aim is to find the Steiner points that lie
            # between two terminals so that the graph can be optimized.
            coordinates_on_same_axis = list()
            for starting_node in filtered_coords_main_line:
                for target_node in filtered_coords_main_line:
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
                                        filtered_coords_main_line]

            # Adding the coordinates to the terminals
            for coord in coordinates_on_same_axis:
                terminals.append(coord)

            # Creation of the new Steiner tree
            graph_steiner_tree = steiner_tree(G, terminals, weight="length")

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_main_line,
                                         filtered_coords_intersection,
                                         edge_label="length",
                                         name=f"Steinerbaum 1. Optimierung",
                                         unit_edge="m",
                                         total_coat_area=False,
                                         building_shaft_supply_air=starting_point
                                         )

            """Optimization step 2"""
            # This checks whether there are any unnecessary kinks in the graph:
            for ventilation_outlet in filtered_coords_main_line:
                if graph_steiner_tree.degree(ventilation_outlet) == 2:
                    neighbors = list(nx.all_neighbors(graph_steiner_tree, ventilation_outlet))

                    neighbor_outlet_one = neighbors[0]
                    temp = list()
                    i = 0
                    while neighbor_outlet_one not in filtered_coords_main_line:
                        temp.append(neighbor_outlet_one)
                        new_neighbors = list(nx.all_neighbors(graph_steiner_tree, neighbor_outlet_one))
                        new_neighbors = [koord for koord in new_neighbors if koord != ventilation_outlet]
                        neighbor_outlet_one = [koord for koord in new_neighbors if koord != temp[i - 1]]
                        neighbor_outlet_one = neighbor_outlet_one[0]
                        i += 1
                        if neighbor_outlet_one in filtered_coords_main_line:
                            break

                    neighbor_outlet_two = neighbors[1]
                    temp = list()
                    i = 0
                    while neighbor_outlet_two not in filtered_coords_main_line:
                        temp.append(neighbor_outlet_two)
                        new_neighbors = list(nx.all_neighbors(graph_steiner_tree, neighbor_outlet_two))
                        new_neighbors = [koord for koord in new_neighbors if koord != ventilation_outlet]
                        neighbor_outlet_two = [koord for koord in new_neighbors if koord != temp[i - 1]]
                        neighbor_outlet_two = neighbor_outlet_two[0]
                        i += 1
                        if neighbor_outlet_two in filtered_coords_main_line:
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
            graph_steiner_tree = steiner_tree(G, terminals, weight="length")

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_main_line,
                                         filtered_coords_intersection,
                                         edge_label="length",
                                         name=f"Steinerbaum 2. Optimierung",
                                         unit_edge="m",
                                         total_coat_area=False,
                                         building_shaft_supply_air=starting_point
                                         )

            """Optimization step 3"""
            # Here the leaves are read from the graph
            leaves = self.find_leaves(graph_steiner_tree)

            # Entfernen der Blätter die kein Lüftungsauslass sind
            for blatt in leaves:
                if blatt not in filtered_coords_main_line:
                    terminals.remove(blatt)

            # Creation of the new Steiner tree
            graph_steiner_tree = steiner_tree(G, terminals, weight="length")

            # Add unit
            for u, v, data in graph_steiner_tree.edges(data=True):
                weight_without_unit = data['length']

                # Add the unit meter
                weight_with_unit = weight_without_unit * ureg.meter

                # Update the length of the edge in the Steiner tree
                data['length'] = weight_with_unit

            if self.export_graphs:
                self.visualization_graph(graph_steiner_tree,
                                         graph_steiner_tree,
                                         z_value,
                                         coordinates_without_airflow,
                                         filtered_coords_main_line,
                                         filtered_coords_intersection,
                                         edge_label="length",
                                         name=f"Steinerbaum 3. Optimierung",
                                         unit_edge="m",
                                         total_coat_area=False,
                                         building_shaft_supply_air=starting_point
                                         )

            main_line_graph[z_value] = graph_steiner_tree

        return main_line_graph

    def create_graph(self, main_graph, ceiling_point, z_coordinate_list, starting_point,
                     cross_section_type, suspended_ceiling_space):

        def is_point_on_node_in_graph(G, point):
            """
            Check if a point lies on any node in the graph.

            G: networkx graph
            point: tuple (x, y, z)

            Returns: (True, edge) if point lies on a node, otherwise False
            """
            for node in G.nodes():
                if point[0:3] == node[0:3]:
                    return True
            return False

        def is_point_on_edge_in_graph(G, point):
            """
            Check if a point lies on any edge in the graph in 3D space.

            G: networkx graph
            point: tuple (x, y, z)

            Returns: (True, edge) if point lies on an edge, otherwise (False, None)
            """
            for edge in G.edges():
                if is_point_on_edge(point, edge):
                    return True, edge
            return False, None

        def is_point_on_edge(point, edge):
            """
            Check if a point lies on a given edge in 3D space.

            point: tuple (x, y, z)
            edge: tuple of two tuples ((x1, y1, z1), (x2, y2, z2)) representing the edge
            """
            (x, y, z) = point
            (x1, y1, z1), (x2, y2, z2) = edge

            # Vector from point 1 to point 2
            v1 = np.array([x2 - x1, y2 - y1, z2 - z1])
            # Vector from point 1 to the given point
            v2 = np.array([x - x1, y - y1, z - z1])

            # Compute the cross product of v1 and v2
            cross_product = np.cross(v1, v2)

            # Check if the cross product is zero (collinearity check)
            if np.allclose(cross_product, np.zeros(3)):
                # Bounding box check
                if (min(x1, x2) <= x <= max(x1, x2) and
                        min(y1, y2) <= y <= max(y1, y2) and
                        min(z1, z2) <= z <= max(z1, z2)):
                    return True

            return False

        def project_point_on_segment(p, v, w):
            """Projects point p onto the line segment vw."""
            # Vector from v to w
            vw = w - v
            # Vector from v to p
            vp = p - v
            # Projection of point p onto the line defined by segment vw
            t = np.dot(vp, vw) / np.dot(vw, vw)
            t = max(0, min(1, t))  # Clamp t to the segment [v, w]
            projection = v + t * vw
            return projection

        def find_closest_edge(G, point):
            """Connects a new point to the closest edge in the graph with a rectangular connection."""

            weight = point[3]
            point = (point[0], point[1], point[2])
            closest_distance = float('inf')
            closest_projection = None
            closest_edge = None

            point = np.array(point)

            for edge in G.edges():
                v = np.array(np.array(edge[0]))
                w = np.array(np.array(edge[1]))
                projection = project_point_on_segment(point, v, w)
                distance = np.linalg.norm(projection - point)

                if distance < closest_distance:
                    closest_distance = distance
                    closest_projection = projection
                    closest_edge = edge

            if closest_projection is not None:
                new_node_data = {}
                # Create a new node at the closest projection
                projection_node = []
                for i in range(3):
                    projection_node.append(round(closest_projection[i], 1))
                new_node_data["projection_node"] = tuple(projection_node)
                new_node_data["closest_edge"] = closest_edge
                new_node_data["new_node_pos"] = tuple(point[0:3])
                new_node_data["new_node_weight"] = weight

            return new_node_data

        # Empty dictonaries for the individual heights are created here:
        dict_steinerbaum_mit_leitungslaenge = {key: None for key in z_coordinate_list}
        dict_steiner_tree_with_air_quantities = {key: None for key in z_coordinate_list}
        dict_steiner_tree_with_duct_cross_section = {key: None for key in z_coordinate_list}
        dict_steiner_tree_with_equivalent_cross_section = {key: None for key in z_coordinate_list}
        dict_steinertree_with_shell = {key: None for key in z_coordinate_list}

        graph_dict = {}

        for z_value in z_coordinate_list:

            # Here the coordinates are filtered by level
            filtered_coords_ceiling = [coord for coord in ceiling_point if coord[2] == z_value]

            # Coordinates without air volumes:
            filtered_coords_ceiling_without_airflow = [(x, y, z) for x, y, z, a in filtered_coords_ceiling]

            filtered_main_graph = nx.Graph(main_graph[z_value])

            new_node_data = {}

            for coord in filtered_coords_ceiling:
                point_on_edge, edge = is_point_on_edge_in_graph(filtered_main_graph, coord[0:3])
                if is_point_on_node_in_graph(filtered_main_graph, coord[0:3]):
                    if starting_point[:2] == list(coord[:2]):
                        filtered_main_graph.nodes[coord[0:3]].update(weight=coord[3], color="green")
                    else:
                        filtered_main_graph.nodes[coord[0:3]].update(weight=coord[3], color="blue")
                elif point_on_edge:
                    filtered_main_graph.remove_edge(*edge)
                    filtered_main_graph.add_node(coord[0:3], pos=coord[0:3], weight = coord[3], color="blue")
                    filtered_main_graph.add_edge(edge[0], coord[0:3])
                    filtered_main_graph.add_edge(coord[0:3], edge[1])
                else:
                    data = find_closest_edge(filtered_main_graph, coord)

                    if not is_point_on_node_in_graph(filtered_main_graph, data["projection_node"]):
                        filtered_main_graph.remove_edge(*data["closest_edge"])
                        filtered_main_graph.add_node(data["projection_node"], pos=data["projection_node"], weight=0,
                                                     color="red")
                        filtered_main_graph.add_edge(data["closest_edge"][0], data["projection_node"])
                        filtered_main_graph.add_edge(data["projection_node"], data["closest_edge"][1])

                    new_node_data[coord[0:3]] = data

            for data in new_node_data.values():
                filtered_main_graph.add_node(data["new_node_pos"], pos=data["new_node_pos"],
                                                 weight=data["new_node_weight"], color="blue")
                filtered_main_graph.add_edge(data["projection_node"], data["new_node_pos"])

            graph_dict[z_value] = filtered_main_graph

            print("Check if nodes and edges of forward graph are inside the boundaries of the building")
            filtered_main_graph = self.check_if_graph_in_building_boundaries(filtered_main_graph, z_value)
            print("Check done")

            if self.export_graphs:
                self.visualization_graph(filtered_main_graph,
                                         filtered_main_graph,
                                         z_value,
                                         list(filtered_main_graph.nodes()),
                                         filtered_coords_ceiling_without_airflow,
                                         None,
                                         edge_label="length",
                                         name=f"Steinerbaum mit Luftauslässen",
                                         unit_edge="m³/h",
                                         total_coat_area=False,
                                         building_shaft_supply_air=starting_point
                                         )

            ##### Rohrnetzberechnung #####

            for u, v in filtered_main_graph.edges():
                duct_length = abs(u[0] - v[0]) + abs(u[1] - v[1])
                filtered_main_graph[u][v]["length"] = duct_length * ureg.meter

            # Steinerbaum with ventilation duct lengths
            dict_steinerbaum_mit_leitungslaenge[z_value] = deepcopy(filtered_main_graph)

            # The start point for the leaves is set here
            start_point = (starting_point[0], starting_point[1], z_value)

            # The paths in the tree from the ventilation outlet to the starting point are read out here
            ceiling_point_to_root_list = list()
            for point in filtered_coords_ceiling_without_airflow:
                for path in nx.all_simple_edge_paths(filtered_main_graph, point, start_point):
                    ceiling_point_to_root_list.append(path)

            for u, v in filtered_main_graph.edges():
                filtered_main_graph[u][v]["volume_flow"] = 0

            # The air volumes along the ventilation duct are added up here
            for ceiling_point_to_root in ceiling_point_to_root_list:
                for startingpoint, targetpoint in ceiling_point_to_root:
                    # Search for the ventilation volume to coordinate:
                    value = None
                    for x, y, z, a in filtered_coords_ceiling:
                        if x == ceiling_point_to_root[0][0][0] and y == ceiling_point_to_root[0][0][1] and z == \
                                ceiling_point_to_root[0][0][2]:
                            value = a
                    filtered_main_graph[startingpoint][targetpoint]["volume_flow"] += value

            # Here the individual steiner tree is added to the list with Volume_flow
            dict_steiner_tree_with_air_quantities[z_value] = deepcopy(filtered_main_graph)

            if self.export_graphs:
                self.visualization_graph(filtered_main_graph,
                                          filtered_main_graph,
                                          z_value,
                                          list(filtered_main_graph.nodes()),
                                          filtered_coords_ceiling_without_airflow,
                                          None,
                                          edge_label="volume_flow",
                                          name=f"Steinerbaum mit Luftmenge in m³ pro h",
                                          unit_edge="m³/h",
                                          total_coat_area=False,
                                          building_shaft_supply_air=starting_point
                                          )

            for u, v in filtered_main_graph.edges():
                filtered_main_graph[u][v]["cross_section"] = self.dimensions_ventilation_duct(cross_section_type,
                                                                             self.required_ventilation_duct_cross_section(
                                                                                 filtered_main_graph[u][v][
                                                                                     "volume_flow"]),
                                                                             suspended_ceiling_space)

            # Adding the graph to the dict
            dict_steiner_tree_with_duct_cross_section[z_value] = deepcopy(filtered_main_graph)

            if self.export_graphs:
                self.visualization_graph(filtered_main_graph,
                                          filtered_main_graph,
                                          z_value,
                                         list(filtered_main_graph.nodes()),
                                         filtered_coords_ceiling_without_airflow,
                                         None,
                                         edge_label="cross_section",
                                          name=f"Steinerbaum mit Querschnitt in mm",
                                          unit_edge="mm",
                                          total_coat_area=False,
                                          building_shaft_supply_air=starting_point
                                          )

            # The equivalent diameter of the duct is assigned to the pipe here
            for u, v in filtered_main_graph.edges():
                filtered_main_graph[u][v]["equivalent_diameter"] = self.calculated_diameter(cross_section_type,
                                                                                             self.required_ventilation_duct_cross_section(
                                                                                                 filtered_main_graph[
                                                                                                     u][v][
                                                                                                     "volume_flow"]),
                                                                                             suspended_ceiling_space)

            # Add to dict
            dict_steiner_tree_with_equivalent_cross_section[z_value] = deepcopy(filtered_main_graph)

            if self.export_graphs:
                self.visualization_graph(filtered_main_graph,
                                          filtered_main_graph,
                                          z_value,
                                          list(filtered_main_graph.nodes()),
                                          filtered_coords_ceiling_without_airflow,
                                          None,
                                          edge_label="equivalent_diameter",
                                          name=f"Steinerbaum mit rechnerischem Durchmesser in mm",
                                          unit_edge="mm",
                                          total_coat_area=False,
                                          building_shaft_supply_air=starting_point
                                          )

            # In order to determine the total amount of surface area, this must be added up:
            total_sheath_area_air_duct = 0

            # Here the pipe is assigned the lateral surface of the duct
            for u, v in filtered_main_graph.edges():
                filtered_main_graph[u][v]["circumference"] = round(self.coat_area_ventilation_duct(cross_section_type,
                                                                              self.required_ventilation_duct_cross_section(
                                                                                  filtered_main_graph[u][v][
                                                                                      "volume_flow"]),
                                                                              suspended_ceiling_space), 2
                                                     )

                total_sheath_area_air_duct += round(filtered_main_graph[u][v]["circumference"], 2)

            # Adding the graph to the dict
            dict_steinertree_with_shell[z_value] = deepcopy(filtered_main_graph)

            if self.export_graphs:
                self.visualization_graph(filtered_main_graph,
                                          filtered_main_graph,
                                          z_value,
                                          list(filtered_main_graph.nodes()),
                                          filtered_coords_ceiling_without_airflow,
                                          None,
                                         edge_label="circumference",
                                          name=f"Steinerbaum mit Mantelfläche",
                                          unit_edge="m²/m",
                                          total_coat_area="",
                                          building_shaft_supply_air=starting_point
                                          )

            self.write_json_graph(graph=filtered_main_graph,
                                  filename=f"supply_air_floor_Z_{z_value}.json")

        return (
            dict_steinerbaum_mit_leitungslaenge, dict_steiner_tree_with_duct_cross_section, dict_steiner_tree_with_air_quantities,
            dict_steinertree_with_shell, dict_steiner_tree_with_equivalent_cross_section)


    def rlt_shaft(self,
                    z_coordinate_list,
                    building_shaft_supply_air,
                    airflow_volume_per_storey,
                    position_ahu,
                    dict_steiner_tree_with_duct_length,
                    dict_steiner_tree_with_duct_cross_section,
                    dict_steiner_tree_with_air_volume_supply_air,
                    dict_steiner_tree_with_sheath_area,
                    dict_steiner_tree_with_calculated_cross_section):

        nodes_shaft = list()
        z_coordinate_list = list(z_coordinate_list)
        # From here, the graph for the AHU is created up to the shaft.
        shaft = nx.Graph()

        for z_value in z_coordinate_list:
            # Adding the nodes
            shaft.add_node((building_shaft_supply_air[0], building_shaft_supply_air[1], z_value),
                             weight=airflow_volume_per_storey[z_value], color="green")
            nodes_shaft.append((building_shaft_supply_air[0], building_shaft_supply_air[1], z_value,
                                  airflow_volume_per_storey[z_value]))

        #From here, the graph is created across the storeys:
        # Add edges for shaft:
        for i in range(len(z_coordinate_list) - 1):
            weight = self.euclidean_distance(
                [building_shaft_supply_air[0], building_shaft_supply_air[1], float(z_coordinate_list[i])],
                [building_shaft_supply_air[0], building_shaft_supply_air[1],
                 float(z_coordinate_list[i + 1])]) * ureg.meter
            shaft.add_edge((building_shaft_supply_air[0], building_shaft_supply_air[1], z_coordinate_list[i]),
                             (building_shaft_supply_air[0], building_shaft_supply_air[1], z_coordinate_list[i + 1]),
                             length=weight)

        # Sum Airflow
        sum_airflow = sum(airflow_volume_per_storey.values())

        # Enrich nodes of the air handling unit with total air volume
        shaft.add_node((position_ahu[0], position_ahu[1], position_ahu[2]),
                         weight=sum_airflow, color="green")

        shaft.add_node((building_shaft_supply_air[0], building_shaft_supply_air[1], position_ahu[2]),
                         weight=sum_airflow, color="green")

        # Connecting the AHU to the shaft
        ahu_shaft_weight = self.euclidean_distance([position_ahu[0], position_ahu[1], position_ahu[2]],
                                                      [building_shaft_supply_air[0], building_shaft_supply_air[1],
                                                       position_ahu[2]]
                                                      ) * ureg.meter

        shaft.add_edge((position_ahu[0], position_ahu[1], position_ahu[2]),
                         (building_shaft_supply_air[0], building_shaft_supply_air[1], position_ahu[2]),
                         length=ahu_shaft_weight)

        # If the AHU is not at ceiling level, the air duct must still be connected to the shaft
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

        connection_weight = self.euclidean_distance(
            [building_shaft_supply_air[0], building_shaft_supply_air[1], position_ahu[2]],
            closest
            ) * ureg.meter
        shaft.add_edge((building_shaft_supply_air[0], building_shaft_supply_air[1], position_ahu[2]),
                         closest,
                         length=connection_weight)

        # Add to dict
        dict_steiner_tree_with_duct_length["shaft"] = deepcopy(shaft)

        position_ahu_without_airflow = (position_ahu[0], position_ahu[1], position_ahu[2])

        # The paths in the tree from the ventilation outlet to the starting point are read out here
        shaft_to_ahu = list()
        for point in shaft.nodes():
            for path in nx.all_simple_edge_paths(shaft, point, position_ahu_without_airflow):
                shaft_to_ahu.append(path)

        # The weights of the edges in the steiner_tree are deleted here, as otherwise the amount of air is added to the distance. However, the weight of the edge must not be set to 0 at the beginning either otherwise the steiner_tree will not be calculated correctly
        for u, v in shaft.edges():
            shaft[u][v]["volume_flow"] = 0

        # The air volumes along the line are added up here
        for shaftpoint_to_ahu in shaft_to_ahu:
            for startpunkt, zielpunkt in shaftpoint_to_ahu:
                # Search for the ventilation volume to coordinate:
                wert = int()
                for x, y, z, a in nodes_shaft:
                    if x == shaftpoint_to_ahu[0][0][0] and y == shaftpoint_to_ahu[0][0][1] and z == \
                            shaftpoint_to_ahu[0][0][2]:
                        wert = a
                shaft[startpunkt][zielpunkt]["volume_flow"] += wert

        # Add to dict
        dict_steiner_tree_with_air_volume_supply_air["shaft"] = deepcopy(shaft)

        # duct_cross_section shaft und RLT zu shaft bestimmen
        for u, v in shaft.edges():
            shaft[u][v]["cross_section"] = self.dimensions_ventilation_duct("angular",
                                                                               self.required_ventilation_duct_cross_section(
                                                                                   shaft[u][v][
                                                                                       "volume_flow"]),
                                                                               suspended_ceiling_space=2000 * ureg.millimeter
                                                                               )

        # Add to dict
        dict_steiner_tree_with_duct_cross_section["shaft"] = deepcopy(shaft)

        # Here, the duct is assigned the lateral surface of the trunking
        for u, v in shaft.edges():
            shaft[u][v]["circumference"] = round(self.coat_area_ventilation_duct("angular",
                                                                     self.required_ventilation_duct_cross_section(
                                                                         shaft[u][v]["volume_flow"]),
                                                                     suspended_ceiling_space=2000 ),2)

        # Add to dict
        dict_steiner_tree_with_sheath_area["shaft"] = deepcopy(shaft)

        # The equivalent diameter of the duct is assigned to the pipe here
        for u, v in shaft.edges():
            shaft[u][v]["equivalent_diameter"] = self.calculated_diameter("angular",
                                                             self.required_ventilation_duct_cross_section(
                                                                 shaft[u][v]["volume_flow"]),
                                                             suspended_ceiling_space=2000)

        # Add to dict
        dict_steiner_tree_with_calculated_cross_section["shaft"] = deepcopy(shaft)

        self.write_json_graph(graph=shaft,
                              filename=f"supply_air_shaft.json")

        return (dict_steiner_tree_with_duct_length,
                dict_steiner_tree_with_duct_cross_section,
                dict_steiner_tree_with_air_volume_supply_air,
                dict_steiner_tree_with_sheath_area,
                dict_steiner_tree_with_calculated_cross_section)

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
                print(f"Node {node} is not inside the building boundaries")
                if any(type in graph.nodes[node]["type"] for type in ["radiator_forward",
                                                                      "radiator_backward"]):
                    assert KeyError(f"Delivery node {node} not in building boundaries")
                graph.remove_node(node)

        edges_floor = [edge for edge in graph.edges()]
        for edge in edges_floor:
            if not any(is_edge_inside_shape(shape, edge[0], edge[1]) for shape in storey_floor_shapes):
                print(f"Edge {edge} does not intersect boundaries")
                graph.remove_edge(edge[0], edge[1])
        return graph


    def find_dimension(self, text: str):
        if "Ø" in text:
            # Case 1: "Ø" followed by a number
            number = ureg(text.split("Ø")[1])  # Splits the string at the "Ø" and takes the second part
            return number
        else:
            # Case 2: "250 x 200" format
            number = text.split(" x ")  # Splits the string at " x "
            width = ureg(number[0])
            height = ureg(number[1])
            return width, height

    def three_dimensional_graph(self,
                                 dict_steiner_tree_with_duct_length,
                                 dict_steiner_tree_with_duct_cross_section,
                                 dict_steiner_tree_with_air_volume_supply_air,
                                 dict_steiner_tree_with_sheath_area,
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
        # enriched
        graph_duct_lenght = nx.Graph()
        graph_air_volumes = nx.Graph()
        graph_duct_cross_section = nx.Graph()
        graph_sheath_area = nx.Graph()
        graph_calculated_diameter = nx.Graph()

        position_ahu = (position_ahu[0], position_ahu[1], position_ahu[2])

        # for duct lenght
        for tree in dict_steiner_tree_with_duct_length.values():
            graph_duct_lenght = nx.compose(graph_duct_lenght, tree)

        # Convert graph for duct length into a directed graph
        graph_duct_length_directional = nx.DiGraph()
        add_edges_and_nodes(graph_duct_length_directional, position_ahu, graph_duct_lenght)

        # for air volumes
        for tree in dict_steiner_tree_with_air_volume_supply_air.values():
            graph_air_volumes = nx.compose(graph_air_volumes, tree)

        # Convert graph for air volumes into a directed graph
        graph_air_volume_directional = nx.DiGraph()
        add_edges_and_nodes(graph_air_volume_directional, position_ahu, graph_air_volumes)

        # for duct_cross_section
        for tree in dict_steiner_tree_with_duct_cross_section.values():
            graph_duct_cross_section = nx.compose(graph_duct_cross_section, tree)

        # Convert graph for duct_cross_section into a directed graph
        graph_duct_cross_section_directional = nx.DiGraph()
        add_edges_and_nodes(graph_duct_cross_section_directional, position_ahu, graph_duct_cross_section)

        # for sheath area
        for tree in dict_steiner_tree_with_sheath_area.values():
            graph_sheath_area = nx.compose(graph_sheath_area, tree)

        # Graph für Mantelfläche in einen gerichteten Graphen umwandeln
        graph_sheath_directional = nx.DiGraph()
        add_edges_and_nodes(graph_sheath_directional, position_ahu, graph_sheath_area)

        # for calculated cross_section
        for tree in dict_steiner_tree_with_calculated_cross_section.values():
            graph_calculated_diameter = nx.compose(graph_calculated_diameter, tree)

        # Convert graph for calculated cross_section into a directed graph
        graph_calculated_diameter_directional = nx.DiGraph()
        add_edges_and_nodes(graph_calculated_diameter_directional, position_ahu, graph_calculated_diameter)

        database_distribution_network = pd.DataFrame(columns=[
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
        for u, v in graph_duct_length_directional.edges():
            temp_df = pd.DataFrame({
                'starting_node': [u],
                'target_node': [v],
                'edge': [(u, v)],
                'room type starting_node': [dict_coordinate_with_space_type.get(u, None)],
                'room type target_node': [dict_coordinate_with_space_type.get(v, None)],
                'duct length': [graph_duct_length_directional.get_edge_data(u, v)["length"]],
                'Air volume': [graph_air_volume_directional.get_edge_data(u, v)["volume_flow"]],
                'duct cross section': [graph_duct_cross_section_directional.get_edge_data(u, v)["cross_section"]],
                'Surface area': [graph_sheath_directional.get_edge_data(u, v)["circumference"] *
                                 graph_duct_length_directional.get_edge_data(u, v)["length"]],
                'calculated diameter': [graph_calculated_diameter_directional.get_edge_data(u,
                                                                                            v)["equivalent_diameter"]]
            })
            database_distribution_network = pd.concat([database_distribution_network, temp_df], ignore_index=True)

        for index, line in database_distribution_network.iterrows():
            duct_cross_section = line['duct cross section']

            if "Ø" in duct_cross_section:
                # Find the diameter and update the corresponding value in the database
                database_distribution_network.at[index, 'diameter'] = str(self.find_dimension(duct_cross_section))

            elif "x" in duct_cross_section:
                # Find width and height, decompose the cross-section value and update the corresponding values in the database
                width, height = self.find_dimension(duct_cross_section)
                database_distribution_network.at[index, 'width'] = str(width)
                database_distribution_network.at[index, 'hight'] = str(height)

        if self.export_graphs:
            # Display of the 3D graph:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

            # nodes positions in 3D
            pos = {coord: (coord[0], coord[1], coord[2]) for coord in list(graph_air_volumes.nodes())}

            # draw nodes
            for node, weight in nx.get_node_attributes(graph_air_volumes, 'weight').items():
                if weight > 0:  # Check whether the weight is greater than 0
                    color = 'red'
                else:
                    color = 'black'  # Otherwise red (or another color for weight = 0)

                # Drawing the nodess with the specified color
                ax.scatter(*node, color=color)

            # draw edges
            for edge in graph_air_volumes.edges():
                start, end = edge
                x_start, y_start, z_start = pos[start]
                x_end, y_end, z_end = pos[end]
                ax.plot([x_start, x_end], [y_start, y_end], [z_start, z_end], "blue")

            # Axis labels and titles
            ax.set_xlabel('X-axis in m')
            ax.set_ylabel('Y-axis in m')
            ax.set_zlabel('Z-axis in m')
            ax.set_title("3D Graph supply air")

            # Add a legend
            ax.legend()

            # show diagram
            plt.close()

        return (graph_duct_length_directional,
                graph_air_volume_directional,
                graph_duct_cross_section_directional,
                graph_sheath_directional,
                graph_calculated_diameter_directional,
                database_distribution_network
                )

    def pressure_loss(self,
                      dict_steiner_tree_with_duct_length,
                      z_coordinate_list,
                      building_shaft_supply_air,
                      position_shaft,
                      graph_ventilation_duct_length_supply_air,
                      graph_air_volumes,
                      graph_duct_cross_section,
                      graph_coat_area,
                      graph_calculated_diameter,
                      database_distribution_network):

        def presentation_t_piece(input, duct, output):
            """
            Create a 3D graph of the T-piece
            :param input: Air inlet in T-piece
            :param duct: duct for losses
            :param output: Bending duct
            :return: grafic
            """
            # Creating a 3D plot
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

            # Function for drawing an arrow
            def draw_arrow(start, ende, farbe, stil='solid'):
                ax.quiver(start[0], start[1], start[2], ende[0] - start[0], ende[1] - start[1], ende[2] - start[2],
                          color=farbe, linestyle=stil, arrow_length_ratio=0.1)

            # Drawing the lines with arrows
            draw_arrow(input[0], input[1], 'red')  # Entrance in red
            draw_arrow(duct[0], duct[1], 'red')  # Duct in red
            draw_arrow(output[0], output[1], 'blue',
                          'dashed')  #Bending duct dashed in blue

            # Setting the axis labels
            ax.set_xlabel('X axis')
            ax.set_ylabel('Y axis')
            ax.set_zlabel('Z axis')

            # Title of the plot
            ax.set_title('3D representation of the ducts')

            # Adjust the axis limits based on the coordinates
            alle_koordinaten = duct + output + input
            x_min, x_max = min(k[0] for k in alle_koordinaten), max(k[0] for k in alle_koordinaten)
            y_min, y_max = min(k[1] for k in alle_koordinaten), max(k[1] for k in alle_koordinaten)
            z_min, z_max = min(k[2] for k in alle_koordinaten), max(k[2] for k in alle_koordinaten)

            ax.set_xlim([x_min - 1, x_max + 1])
            ax.set_ylim([y_min - 1, y_max + 1])
            ax.set_zlim([z_min - 1, z_max + 1])

            # show plot
            # plt.show()
            plt.close()

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

        def drag_coefficient_arc_round(angle: int, mean_radius: float, diameter: float) -> float:
            """
            Calculates the resistance coefficient for a curve round A01 according to VDI 3803-6
            :param angle: angle in degree
            :param mean_radius: Average radius of the arc in meters
            :param diameter: Diameter of the duct in meters
            :return: Resistance coefficient curve round A01 according to VDI 3803-6
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * angle)

            b = None
            if 0.5 <= mean_radius / diameter <= 1.0:
                b = 0.21 / ((mean_radius / diameter) ** 2.5)
            elif 1 <= mean_radius / diameter:
                b = (0.21 / (math.sqrt(mean_radius / diameter)))

            c = 1

            return a * b * c

        def drag_coefficient_arc_angular(angle, mean_radius, height, width, calculated_diameter):
            """
            Calculates the resistance coefficient for a bend angular A02 according to VDI 3803-6
            :param angle: angle in degree
            :param mean_radius: Average radius of the arc in meters
            :param height: Height of the duct in meters
            :param width: width of the duct in meters
            :param calculated_diameter: calculated diameter of the duct
            :return: drag coefficient arc angular
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * angle)

            b = None
            if 0.5 <= mean_radius / calculated_diameter <= 1.0:
                b = 0.21 / ((mean_radius / calculated_diameter) ** 2.5)
            elif 1 <= mean_radius / calculated_diameter:
                b = (0.21 / (math.sqrt(mean_radius / calculated_diameter)))

            c = (- 1.03663 * 10 ** (-4) * (height / width) ** 5 + 0.00338 * (height / width) ** 4 - 0.04277 * (
                    height / width)
                 ** 3 + 0.25496 * (height / width) ** 2 - 0.66296 * (height / width) + 1.4499)

            return a * b * c


        def drag_coefficient_cross_sectional_narrowing_continuous(d_1, d_2):
            """
            Berechnet den WiderstandsCoefficient bei einer Querschnittsverengung A15 nach VDI 3803 Blatt 6
            :param d_1: diameter Air inlet in meters
            :param d_2: diameter Air outlet in meters
            :return: Wdrag coefficient
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

        def drag_coefficient_T_piece_separation_round(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                      v_A: float,
                                                      direction: str) -> float:
            """
            Berechnet den WiderstandCoefficient für eine T-Trennung A22 nach VDI 3803 Blatt 6
            :param d: Diameter of the entrance in meters
            :param v: Volume flow of the input in m³/h
            :param d_D: Diameter of the passage in meters
            :param v_D: Volume flow of the passage in m³/h
            :param d_A: Diameter of the outlet in meters
            :param v_A: Volume flow of the outlet in m³/h
            :param direction: "direction of passage" or "branching direction"
            :return: WiderstandCoefficient für eine T-Trennung A22
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

            if direction == "direction of passage":
                zeta_D = (K_D * (1 - w_D / w) ** 2) / (w_D / w) ** 2
                return zeta_D
            elif direction == "branching direction":
                # Es wird Form "a" nach VDI 3803 Blatt 6 gewählt
                zeta_A = 0.26 + 55.29 * math.exp(-(w_A / w) / 0.1286) + 555.26 * math.exp(
                    -(w_A / w) / 0.041) + 5.73 * math.exp(-(w_A / w) / 0.431)
                return zeta_A
            else:
                self.logger.error("No or incorrect direction input")

        def drag_coefficient_T_piece_separation_angular(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                       v_A: float, direction: str) -> float:
            """
            Berechnet den WiderstandCoefficient für eine T-Trennung A24 nach VDI 3803 Blatt 6
            :param d: Diameter of the entrance in meters
            :param v: Volume flow of the input in m³/h
            :param d_D: Diameter of the passage in meters
            :param v_D: Volume flow of the passage in m³/h
            :param d_A: Diameter of the outlet in meters
            :param v_A: Volume flow of the outlet in m³/h
            :param direction: "direction of passage" or "branching direction"
            :return: WiderstandCoefficient für eine T-Trennung A24
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

            if direction == "direction of passage":
                K_1 = 183.3
                K_2 = 0.06
                K_3 = 0.17

                zeta_D = K_1 / (math.exp(w_D / w * 1 / K_2)) + K_3

                return zeta_D

            elif direction == "branching direction":
                K_1 = 301.95
                K_2 = 0.06
                K_3 = 0.75

                zeta_D = K_1 / (math.exp(w_A / w * 1 / K_2)) + K_3

                return zeta_D
            else:
                self.logger.error("No or incorrect direction input")

        def drag_coefficient_kruemmerendstueck_angular(a: float, b: float, d: float, v: float, d_A: float, v_A: float):
            """
            Berechnet den WiderstandsCoefficient für Krümmerabzweig A25 nach VDI 3803
            :param a: Höhe des Eingangs in Metern
            :param b: width des Eingangs in Metern
            :param d: rechnerischer diameter des Eingangs in Metern
            :param v: Volume_flow des Eingangs in m³/h
            :param d_A: rechnerischer diameter des Abzweiges in Metern
            :param v_A: Volume_flow des Abzweiges in m³/h
            :return: WiderstandsCoefficient für Krümmerabzweig A25 nach VDI 3803
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

        def drag_coefficient_T_end_piece_round(d: float, v: float, d_A: float, v_A: float):
            """
            Calculates the drag coefficient for a T-piece round A27 according to VDI 3803
            :param d: calculated diameter of the inlet in meters
            :param v: Volume_flow of the inlet in m³/h
            :param d_A: calculated diameter of the branch in meters
            :param v_A: Volume_flow of the branch in m³/h
            :return: Wiederstandsbeiwert für ein T-Stück round A27 nach VDI 3803
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

        building_shaft_supply_air = (
        building_shaft_supply_air[0], building_shaft_supply_air[1], building_shaft_supply_air[2])

        # Creation of a BFS sequence from the starting point
        bfs_edges = list(nx.edge_bfs(graph_ventilation_duct_length_supply_air, building_shaft_supply_air))

        graph_duct_length_sorted = nx.Graph()

        # Add edges in the BFS order to the new graph
        for edge in bfs_edges:
            graph_duct_length_sorted.add_edge(*edge)

        # pressure_loss calculation
        # Create network:
        net = pp.create_empty_network(fluid="air")

        # Reading out the fluid
        fluid = pp.get_fluid(net)

        # Reading the density
        density = fluid.get_density(temperature=293.15) * ureg.kilogram / ureg.meter ** 3

        # Definition of the parameters for the junctions
        name_junction = [coordinate for coordinate in list(graph_duct_length_sorted.nodes())]
        index_junction = [index for index, wert in enumerate(name_junction)]

        # Create a list for each coordinate axis
        x_coordinate = [coordinate[0] for coordinate in list(graph_duct_length_sorted.nodes())]
        y_coordinate = [coordinate[1] for coordinate in list(graph_duct_length_sorted.nodes())]
        z_coordinate = [coordinate[2] for coordinate in list(graph_duct_length_sorted.nodes())]

        """Create 2D coordinates"""
        # Since only 3D coordinates are available, but 3D coordinates are needed, a dict is created which
        # assigns a 2D coordinate to
        two_d_codrinates = dict()
        position_shaft_graph = (position_shaft[0], position_shaft[1], position_shaft[2])

        # Duct from AHU to shaft
        path_ahu_to_shaft = list(
            nx.all_simple_paths(graph_ventilation_duct_length_supply_air, building_shaft_supply_air,
                                position_shaft_graph))[0]
        number_of_points_path_ahu_to_shaft = -len(path_ahu_to_shaft)

        for punkt in path_ahu_to_shaft:
            two_d_codrinates[punkt] = (number_of_points_path_ahu_to_shaft, 0)
            number_of_points_path_ahu_to_shaft += 1

        # Try to convert all keys into numbers and sort them
        sorted_keys = sorted(
            (key for key in dict_steiner_tree_with_duct_length.keys() if key != "shaft"),
            key=lambda x: float(x)
        )

        y = 0  # start y-coordinate

        for key in sorted_keys:
            graph_floor = dict_steiner_tree_with_duct_length[key]

            shaft_nodes = [node for node in graph_floor.nodes()
                              if node[0] == position_shaft[0] and node[1] == building_shaft_supply_air[1]][0]

            # Identify leaf nodes (nodes with degree 1)
            leaf_nodes = [node for node in graph_floor.nodes()
                            if graph_floor.degree(node) == 1 and node != shaft_nodes]

            # Calculate path from starting_node to each leaf node
            path = [nx.shortest_path(graph_floor, source=shaft_nodes, target=blatt) for blatt in leaf_nodes]

            # Sort path by length
            sorted_pathes = sorted(path, key=len, reverse=True)

            x = 0

            for point in sorted_pathes[0]:
                if point not in two_d_codrinates:
                    two_d_codrinates[point] = (x, y)
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
                    if point not in two_d_codrinates:
                        counter_new_points += 1
                        two_d_codrinates[point] = (x, y)

                        if path_counter == 0:
                            x += 2

                        if path_counter >= 1 and rest_length_path >= 1:
                            if i >= path_counter:
                                x += 2
                            else:
                                y += 2
                                i += 2

                    elif point in two_d_codrinates:
                        counter_points_present += 1
                        x += 2
                        rest_length_path -= 1

                y -= i
                x = -2
                path_counter += 1

            run_again = max(run_again, i) + 4
            y += run_again
        """2D coordinates created"""

        # Create multiple junctions
        for junction in range(len(index_junction)):
            pp.create_junction(net,
                               name=str(name_junction[junction]),
                               index=index_junction[junction],
                               pn_bar=0,
                               tfluid_k=293.15,
                               geodata=two_d_codrinates[name_junction[junction]],
                               x=x_coordinate[junction],
                               y=y_coordinate[junction],
                               height_m=z_coordinate[junction]
                               )

        # Definition of the parameters for the pipes
        name_pipe = [pipe for pipe in
                     list(graph_duct_length_sorted.edges())]  # Designation is the start and end coordinate
        length_pipe = [graph_ventilation_duct_length_supply_air.get_edge_data(pipe[0], pipe[1])["length"] for pipe in
                       name_pipe]  # The length is read from the graph with line lengths

        from_junction = [pipe[0] for pipe in name_pipe]  # Start junction of the pipe
        to_junction = [pipe[1] for pipe in name_pipe]  # Target junction of the pipe
        diameter_pipe = [graph_calculated_diameter.get_edge_data(pipe[0], pipe[1])["equivalent_diameter"] for pipe in
                         name_pipe]

        # Adding the ducts to the network
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

        """From here, the loss coefficients of the pipes are adjusted"""
        for pipe in range(len(name_pipe)):

            # Neighbors of the start node
            neighbors = list(nx.all_neighbors(graph_ventilation_duct_length_supply_air, from_junction[pipe]))

            """Kinks:"""
            if len(neighbors) == 2:  # Bögen finden
                incoming_edge = list(graph_ventilation_duct_length_supply_air.in_edges(from_junction[pipe]))[0]
                ausgehende_kante = list(graph_ventilation_duct_length_supply_air.out_edges(from_junction[pipe]))[0]
                # Calculated diameter of the line
                calculated_diameter = \
                    graph_calculated_diameter.get_edge_data(from_junction[pipe], to_junction[pipe])[
                        "equivalent_diameter"].to(ureg.meter)

                # Dimension of the duct
                dimension_duct = graph_duct_cross_section.get_edge_data(from_junction[pipe], to_junction[pipe])[
                    "cross_section"]

                if not check_if_lines_are_aligned(incoming_edge, ausgehende_kante):

                    zeta_arch = None
                    if "Ø" in dimension_duct:
                        diameter = self.find_dimension(dimension_duct)
                        zeta_arch = drag_coefficient_arc_round(angle=90,
                                                                   mean_radius=0.75 * ureg.meter,
                                                                   diameter=diameter)
                        # print(f"Zeta-Bogen round: {zeta_arch}")

                    elif "x" in dimension_duct:
                        width = self.find_dimension(dimension_duct)[0].to(ureg.meter)
                        height = self.find_dimension(dimension_duct)[1].to(ureg.meter)
                        zeta_arch = drag_coefficient_arc_angular(angle=90,
                                                                    mean_radius=0.75 * ureg.meter,
                                                                    height=height,
                                                                    width=width,
                                                                    calculated_diameter=calculated_diameter
                                                                    )
                        # print(f"Zeta Bogen angular: {zeta_arch}")

                    # Changing the loss_coefficient value
                    net['pipe'].at[pipe, 'loss_coefficient'] += zeta_arch

                    database_distribution_network.loc[database_distribution_network[
                                                    'target_node'] == to_junction[pipe], 'Zeta Bogen'] = zeta_arch

            """Reductions"""
            if len(neighbors) == 2:
                duct = name_pipe[pipe]
                duct_neighbor = to_junction[pipe]
                dimensions_duct = graph_duct_cross_section.get_edge_data(from_junction[pipe], to_junction[pipe])[
                    "cross_section"]

                outgoing_edge = graph_ventilation_duct_length_supply_air.out_edges(from_junction[pipe])

                incoming_edge = list(graph_ventilation_duct_length_supply_air.in_edges(from_junction[pipe]))[0]
                incoming_neighbor_nodes = incoming_edge[1]
                dimensions_incoming_edge = \
                    graph_duct_cross_section.get_edge_data(incoming_edge[0], incoming_edge[1])[
                        "cross_section"]

                """ Daten für WiderstandsCoefficiente"""
                # diameter des Eingangs:
                d = graph_calculated_diameter.get_edge_data(incoming_edge[0], incoming_edge[1])[
                    "equivalent_diameter"].to(ureg.meter)
                # Volume_flow des Eingangs:
                v = graph_air_volumes.get_edge_data(incoming_edge[0], incoming_edge[1])["volume_flow"]

                # diameter des Durchgangs:
                d_D = graph_calculated_diameter.get_edge_data(duct[0], duct[1])["equivalent_diameter"].to(ureg.meter)
                # Volume_flow des Durchgangs:
                v_D = graph_air_volumes.get_edge_data(duct[0], duct[1])["volume_flow"]

                if d > d_D:
                    zeta_reduzierung = drag_coefficient_cross_sectional_narrowing_continuous(d, d_D)

                    # print(f"Zeta T-Reduzierung: {zeta_reduzierung}")

                    net['pipe'].at[pipe, 'loss_coefficient'] += zeta_reduzierung

                    database_distribution_network.loc[database_distribution_network[
                                                    'target_node'] == to_junction[
                                                    pipe], 'Zeta Reduzierung'] = zeta_reduzierung

            """T-Stücke"""
            if len(neighbors) == 3:  # T-Stücke finden
                duct = name_pipe[pipe]
                duct_neighbor = to_junction[pipe]
                dimensions_duct = graph_duct_cross_section.get_edge_data(from_junction[pipe], to_junction[pipe])[
                    "cross_section"]

                outgoing_edge = graph_ventilation_duct_length_supply_air.out_edges(from_junction[pipe])

                kinking_line = [p for p in outgoing_edge if p != duct][0]
                kinking_line_nodes = kinking_line[1]
                dimension_kinking_duct = \
                    graph_duct_cross_section.get_edge_data(kinking_line[0], kinking_line[1])[
                        "cross_section"]

                incoming_edge = list(graph_ventilation_duct_length_supply_air.in_edges(from_junction[pipe]))[0]
                incoming_neighbor_nodes = incoming_edge[1]
                dimensions_incoming_edge = \
                    graph_duct_cross_section.get_edge_data(incoming_edge[0], incoming_edge[1])[
                        "cross_section"]

                """ Data for draf coefficients"""
                # diameter of the entrance:
                d = graph_calculated_diameter.get_edge_data(incoming_edge[0], incoming_edge[1])[
                    "equivalent_diameter"].to(ureg.meter)
                # Volume_flow of the entrance:
                v = graph_air_volumes.get_edge_data(incoming_edge[0], incoming_edge[1])["volume_flow"]

                # diameter of the Passage:
                d_D = graph_calculated_diameter.get_edge_data(duct[0], duct[1])["equivalent_diameter"].to(ureg.meter)
                # Volume_flow of the Passage:
                v_D = graph_air_volumes.get_edge_data(duct[0], duct[1])["volume_flow"]

                # diameter of the outlet:
                d_A = \
                    graph_calculated_diameter.get_edge_data(kinking_line[0], kinking_line[1])[
                        "equivalent_diameter"].to(ureg.meter)
                # Volume_flow ot the outlet
                v_A = graph_air_volumes.get_edge_data(kinking_line[0], kinking_line[1])["volume_flow"]

                zeta_t_piece = 0
                zeta_cross_section_narrowing = 0

                # 3D representation of the T-piece
                # presentation_t_piece(incoming_edge, duct, kinking_line)

                if check_if_lines_are_aligned(incoming_edge, duct) == True:

                    #   duct für Verlust
                    #    |
                    #    |---- Ausgang
                    #    |
                    #  Eingang

                    # print("T-Stück geht durch ")

                    if "Ø" in dimensions_incoming_edge:

                        zeta_t_piece = drag_coefficient_T_piece_separation_round(d=d,
                                                                                  v=v,
                                                                                  d_D=d_D,
                                                                                  v_D=v_D,
                                                                                  d_A=d_A,
                                                                                  v_A=v_A,
                                                                                  direction="direction of passage")

                        # print(f"Zeta T-Stück: {zeta_t_piece}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_piece

                    elif "x" in dimensions_incoming_edge:
                        zeta_t_piece = drag_coefficient_T_piece_separation_angular(d=d,
                                                                                   v=v,
                                                                                   d_D=d_D,
                                                                                   v_D=v_D,
                                                                                   d_A=d_A,
                                                                                   v_A=v_A,
                                                                                   direction="direction of passage")

                        if "Ø" in dimensions_duct and d > d_D:
                            zeta_cross_section_narrowing = drag_coefficient_cross_sectional_narrowing_continuous(d, d_D)
                        else:
                            zeta_cross_section_narrowing = 0

                        # print(f"Zeta T-Stück: {zeta_t_piece + zeta_cross_section_narrowing}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_piece + zeta_cross_section_narrowing




                elif check_if_lines_are_aligned(incoming_edge, kinking_line) == True:

                    #  Ausgang
                    #    |
                    #    |---- duct für Verlust
                    #    |
                    #  Eingang

                    # print("T-Stück knickt ab ")

                    if "Ø" in dimensions_incoming_edge:

                        zeta_t_piece = drag_coefficient_T_piece_separation_round(d=d,
                                                                                  v=v,
                                                                                  d_D=d_D,
                                                                                  v_D=v_D,
                                                                                  d_A=d_A,
                                                                                  v_A=v_A,
                                                                                  direction="branching direction")

                        # print(f"Zeta T-Stück: {zeta_t_piece}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_piece


                    elif "x" in dimensions_incoming_edge:
                        zeta_t_piece = drag_coefficient_T_piece_separation_angular(d=d,
                                                                                   v=v,
                                                                                   d_D=d_D,
                                                                                   v_D=v_D,
                                                                                   d_A=d_A,
                                                                                   v_A=v_A,
                                                                                   direction="branching direction")

                        # print(f"Zeta T-Stück: {zeta_t_piece}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_piece



                elif check_if_lines_are_aligned(duct, kinking_line):
                    # Ausgang ---------- duct für Verlust
                    #              |
                    #           Eingang
                    # print("T-Stück ist Verteiler")

                    if "Ø" in dimensions_incoming_edge:
                        zeta_t_piece = drag_coefficient_T_end_piece_round(d=d,
                                                                            v=v,
                                                                            d_A=max(d_A, d_D),
                                                                            v_A=max(v_A, v_D)
                                                                            )
                        # Wenn der diameter des Rohres kleiner ist als der des Abzweiges, muss noch eine
                        # Querschnittsverengung berücksichtigt werden
                        if d_D < d_A:
                            zeta_cross_section_narrowing = drag_coefficient_cross_sectional_narrowing_continuous(d_A, d_D)
                        else:
                            zeta_cross_section_narrowing = 0

                        # print(f"Zeta T-Stück: {zeta_t_piece}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_piece + zeta_cross_section_narrowing

                    elif "x" in dimensions_incoming_edge:
                        width = self.find_dimension(dimensions_incoming_edge)[0].to(ureg.meter)
                        height = self.find_dimension(dimensions_incoming_edge)[1].to(ureg.meter)
                        zeta_t_piece = drag_coefficient_kruemmerendstueck_angular(a=height,
                                                                                   b=width,
                                                                                   d=d,
                                                                                   v=v,
                                                                                   d_A=d_D,
                                                                                   v_A=v_D
                                                                                   )

                        # print(f"Zeta T-Stück: {zeta_t_piece}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_piece

                database_distribution_network.loc[database_distribution_network[
                                                'target_node'] == to_junction[
                                                pipe], 'Zeta T-Stück'] = zeta_t_piece + zeta_cross_section_narrowing

        # Air volumes from graph
        air_volume = nx.get_node_attributes(graph_air_volumes, 'weight')

        # Find index of the air handling unit
        index_ahu = name_junction.index(tuple(building_shaft_supply_air))
        air_volume_ahu = air_volume[building_shaft_supply_air]
        mdot_kg_per_s_rlt = (air_volume_ahu * density).to(ureg.kilogram / ureg.second)

        # Create an external grid, as the visualization is then better
        pp.create_ext_grid(net, junction=index_ahu, p_bar=0, t_k=293.15, name="Air handling unit")

        # Hinzufügen der Air handling unit zum Netz
        pp.create_source(net,
                         mdot_kg_per_s=mdot_kg_per_s_rlt.magnitude,
                         junction=index_ahu,
                         p_bar=0,
                         t_k=293.15,
                         name="Air handling unit")

        list_ventilation_outlets = list()

        # Adding the ventilation outlets
        for index, element in enumerate(air_volume):
            if element == tuple(building_shaft_supply_air):
                continue  # Skips the current run
            if element[0] == position_shaft[0] and element[1] == position_shaft[1]:
                continue
            if air_volume[element] == 0:
                continue
            pp.create_sink(net,
                           junction=name_junction.index(element),
                           mdot_kg_per_s=(air_volume[element] * density).to(ureg.kilogram / ureg.second).magnitude,
                           )
            list_ventilation_outlets.append(name_junction.index(element))

        # The actual calculation is started with the pipeflow command:
        pp.pipeflow(net)

        # Determination of the pressure_loss
        greatest_pressure_loss = abs(net.res_junction["p_bar"].min())
        difference = net.res_junction["p_bar"].min()

        # Identification of the source by its name or index
        source_index = net['source'].index[net['source']['name'] == "Air handling unit"][0]
        # Identify the external grid by its name or index
        ext_grid_index = net['ext_grid'].index[net['ext_grid']['name'] == "Air handling unit"][0]

        # Changing the pressure value
        net['source'].at[source_index, 'p_bar'] = greatest_pressure_loss
        # Changing the pressure value
        net['ext_grid'].at[ext_grid_index, 'p_bar'] = greatest_pressure_loss

        # Recalculation
        pp.pipeflow(net)

        greatest_pressure_loss = net.res_junction["p_bar"].min()

        # Identification of the source by its name or index
        source_index = net['source'].index[net['source']['name'] == "Air handling unit"][0]
        # Identify the external grid by its name or index
        ext_grid_index = net['ext_grid'].index[net['ext_grid']['name'] == "Air handling unit"][0]

        greatest_pressure_loss -= 0.00100  # 30 Pa for ventilation outlet and 50 Pa for silencer + 20 reserve

        # Changing the pressure value
        net['source'].at[source_index, 'p_bar'] -= greatest_pressure_loss
        # Changing the pressure value
        net['ext_grid'].at[ext_grid_index, 'p_bar'] -= greatest_pressure_loss

        pp.pipeflow(net)

        # Results are saved in tables with the prefix res_... prefix. After the calculation, these tables are also
        # stored in the net container after the calculation.
        dataframe_pipes = pd.concat([net.pipe, net.res_pipe], axis=1)
        dataframe_junctions = pd.concat([net.junction, net.res_junction], axis=1)

        for duct in database_distribution_network['edge']:
            p_from_pa = int(dataframe_pipes.loc[dataframe_pipes["name"] == str(duct), "p_from_bar"].iloc[0] * 100000)
            p_to_pa = int(dataframe_pipes.loc[dataframe_pipes["name"] == str(duct), "p_to_bar"].iloc[0] * 100000)

            database_distribution_network.loc[database_distribution_network['edge'] == duct, "p_from_pa"] = p_from_pa
            database_distribution_network.loc[database_distribution_network['edge'] == duct, "p_to_pa"] = p_to_pa

        database_distribution_network.to_excel(self.paths.export / 'ventilation system' / 'supply air' /
                                               'dataframe_supply_air.xlsx', index=False)

        # path für Speichern
        pipes_excel_pfad = self.paths.export / 'ventilation system' / 'supply air' / 'pressure_loss.xlsx'


        # Export
        dataframe_pipes.to_excel(pipes_excel_pfad)

        with pd.ExcelWriter(pipes_excel_pfad) as writer:
            dataframe_pipes.to_excel(writer, sheet_name="Pipes")
            dataframe_junctions.to_excel(writer, sheet_name="Junctions")

        if self.export_graphs:
            # create additional junction collections for junctions with sink connections and junctions with valve connections
            junction_sink_collection = plot.create_junction_collection(net,
                                                                       junctions=list_ventilation_outlets,
                                                                       patch_type="circle",
                                                                       size=0.12,
                                                                       color="blue")

            junction_source_collection = plot.create_junction_collection(net,
                                                                         junctions=[index_ahu],
                                                                         patch_type="circle",
                                                                         size=0.6,
                                                                         color="green")

            # create additional pipe collection
            pipe_collection = plot.create_pipe_collection(net,
                                                          linewidths=2.,
                                                          color="blue")

            collections = [junction_sink_collection, junction_source_collection, pipe_collection]

            # Draw the collections
            fig, ax = plt.subplots(num=f"pressure_loss", figsize=(18, 12) )

            plot.draw_collections(collections=collections, ax=ax, axes_visible=(True, True))

            # Titel hinzufügen
            ax.set_title("pressure_loss supply_air", fontsize=14, fontweight='bold')

            # Adds the text annotations for the pressures
            for idx, junction in enumerate(net.res_junction.index):
                pressure = net.res_junction.iloc[idx]['p_bar']  # Druck am nodes
                # Coordinates of the nodes
                if junction in net.junction_geodata.index:
                    coords = net.junction_geodata.loc[junction, ['x', 'y']]
                    ax.text(coords['x'], coords['y'], f'{pressure * 100000:.0f} Pa', fontsize=10,
                            horizontalalignment='left', verticalalignment='top', rotation=-45)

            # Define legend entries
            legend_entries = [
                Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=10,
                       label='Ventilation outlets'),
                Line2D([0], [0], marker='o', color='w', markerfacecolor='green', markersize=10, label='Air handling unit'),
                Line2D([0], [0], color='blue', lw=2, label='Kanäle')
            ]

            # Add legend to the plot
            plt.legend(handles=legend_entries, loc="best")

            # add title
            plt.title("Ventilation schemes", fontsize=20)

            # Reduce margin
            plt.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.95)

            x_values = []
            y_values = []

            # Run through all nodes in the index of junction_geodata
            for junction in net.junction_geodata.index:
                # Direct readout of the x and y coordinates for the current node
                coords = net.junction_geodata.loc[junction, ['x', 'y']]
                x = coords['x']  # Read out x-value directly
                y = coords['y']  # Read out y-value directly

                # Adding the x and y values to the respective lis
                x_values.append(x)
                y_values.append(y)

            plt.xlim(min(x_values) - 2, max(x_values) + 2)
            plt.ylim(min(y_values) - 2, max(y_values) + 2)

            # Set the path for the new folder
            folder_path = Path(self.paths.export / 'ventilation system' / 'supply air')

            # Create folder
            folder_path.mkdir(parents=True, exist_ok=True)

            # save graph
            total_name = "pressure_loss supply_air" + ".png"
            path_and_name = self.paths.export / 'ventilation system' / 'supply air' / total_name
            plt.savefig(path_and_name)

            # plt.show()

            plt.close()

        return greatest_pressure_loss * 100000, database_distribution_network

    def sheet_metal_thickness(self, pressure_loss, dimensions):
        """
        Calculates the sheet thickness depending on the channel
        :param pressure_loss: pressure loss of the system
        :param dimensions: dimensions of the duct (400x300 or Ø60)
        :return: Sheet thickness
        """

        if "Ø" in dimensions:
            diameter = self.find_dimension(dimensions).to(ureg.meter)

            if diameter <= 0.2 * ureg.meter:
                sheet_metal_thickness = (0.5 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.2 * ureg.meter < diameter <= 0.4 * ureg.meter:
                sheet_metal_thickness = (0.6 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.4 * ureg.meter < diameter <= 0.5 * ureg.meter:
                sheet_metal_thickness = (0.7 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.5 * ureg.meter < diameter <= 0.63 * ureg.meter:
                sheet_metal_thickness = (0.9 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.63 * ureg.meter < diameter <= 1.25 * ureg.meter:
                sheet_metal_thickness = (1.25 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782

        elif "x" in dimensions:
            width, height = self.find_dimension(dimensions)
            longest_edge = max(width.to(ureg.meter), height.to(ureg.meter))

            if pressure_loss <= 1000:
                if longest_edge <= 0.500 * ureg.meter:
                    sheet_metal_thickness = (0.6 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 0.500 * ureg.meter < longest_edge <= 1.000 * ureg.meter:
                    sheet_metal_thickness = (0.8 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < longest_edge <= 2.000 * ureg.meter:
                    sheet_metal_thickness = (1.0 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

            elif 1000 < pressure_loss <= 2000:
                if longest_edge <= 0.500 * ureg.meter:
                    sheet_metal_thickness = (0.7 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 0.500 * ureg.meter < longest_edge <= 1.000 * ureg.meter:
                    sheet_metal_thickness = (0.9 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < longest_edge <= 2.000 * ureg.meter:
                    sheet_metal_thickness = (1.1 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

            elif 2000 < pressure_loss <= 3000:
                if longest_edge <= 1.000 * ureg.meter:
                    sheet_metal_thickness = (0.95 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < longest_edge <= 2.000 * ureg.meter:
                    sheet_metal_thickness = (1.15 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

        return sheet_metal_thickness

    def room_connection(self, cross_section_type, suspended_ceiling_space, dataframe_rooms):

        # Determining the duct cross-section
        dataframe_rooms["duct cross section"] = \
            dataframe_rooms.apply(lambda row: self.dimensions_ventilation_duct(cross_section_type,
                                                                     self.required_ventilation_duct_cross_section(
                                                                         row["Volume_flow"]),
                                                                     suspended_ceiling_space),
                                  axis=1
                                  )

        # Determining the dimensions
        dataframe_rooms['duct length'] = 2 * ureg.meter
        dataframe_rooms['diameter'] = None
        dataframe_rooms['width'] = None
        dataframe_rooms['hight'] = None

        for index, duct_cross_section in enumerate(dataframe_rooms["duct cross section"]):
            if "Ø" in duct_cross_section:
                dataframe_rooms.at[index, 'diameter'] = self.find_dimension(duct_cross_section)

            elif "x" in duct_cross_section:
                dataframe_rooms.at[index, 'width'] = self.find_dimension(duct_cross_section)[0]
                dataframe_rooms.at[index, 'hight'] = self.find_dimension(duct_cross_section)[1]

        dataframe_rooms['Surface area'] = dataframe_rooms.apply(
            lambda row: self.coat_area_ventilation_duct(
                cross_section_type,
                self.required_ventilation_duct_cross_section(row["Volume_flow"]),
                suspended_ceiling_space
            ) * row['duct length'], axis=1)

        dataframe_rooms['calculated diameter'] = dataframe_rooms.apply(
            lambda row: self.calculated_diameter(cross_section_type,
                                                       self.required_ventilation_duct_cross_section(row["Volume_flow"]),
                                                       suspended_ceiling_space), axis=1)

        # Determining the sheet thickness
        dataframe_rooms["sheet thickness"] = dataframe_rooms.apply(
            lambda row: self.sheet_metal_thickness(70, row["duct cross section"]), axis=1)

        # Check whether a silencer is required
        list_rooms_silencers = ["Bed room",
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
            lambda x: 1 if x in list_rooms_silencers else 0)

        # Volume_flow_controller
        dataframe_rooms["Volume_flow_controller"] = 1

        # Calculation of the sheet volume
        dataframe_rooms["Sheet volume"] = dataframe_rooms["sheet thickness"] * dataframe_rooms['Surface area']

        list_dataframe_rooms_sheet_weight = [v * (7850 * ureg.kilogram / ureg.meter ** 3) for v in
                                             dataframe_rooms["Sheet volume"]]
        # density steel 7850 kg/m³

        # Calculation of the sheet weight
        dataframe_rooms["Sheet weight"] = list_dataframe_rooms_sheet_weight

        return dataframe_rooms

    def co2(self,
            pressure_loss,
            dataframe_rooms,
            dataframe_distribution_network_supply_air):

        def gwp(uuid: str):
            """
            Returns the global warming potential by ÖKOBAUDAT in categories
            :param uuid: UUID according to ÖKOBAUDAT
            :return: Global warming potential according to ÖKOBAUDAT, ReferenceUnit
            """
            # A1-A3: Production
            # C2: Transportation
            # C3: Waste treatment
            # D: Recycling potential

            OKOBAU_URL = "https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/c391de0f-2cfd-47ea-8883-c661d294e2ba"

            """Fetches the data of a specific EPD given its UUID"""
            response = requests.get(f"{OKOBAU_URL}/processes/{uuid}?format=json&view=extended")

            response.raise_for_status()
            data = response.json()

            # Extract the values for modules A1-A3, C2, C3, D
            results = {}
            # Loop through all 'LCIAResults' entries
            for entry in data['LCIAResults']['LCIAResult']:
                # Initialize an empty dictionary for each entry
                results[entry['referenceToLCIAMethodDataSet']['shortDescription'][0]['value']] = {}
                # Loop through all 'other' elements
                for sub_entry in entry['other']['anies']:
                    # Check whether 'module' exists as a key in 'sub_entry'
                    if 'module' in sub_entry:
                        # Adding the value to the dictionary
                        results[entry['referenceToLCIAMethodDataSet']['shortDescription'][0]['value']][
                            sub_entry['module']] = \
                            sub_entry['value']

            wp_reference_unit = data['exchanges']['exchange'][0]['flowProperties'][1]['referenceUnit']

            # Return of the results
            return results['Global Warming Potential - total (GWP-total)'], wp_reference_unit

        """
        Berechnung des CO2 des Lüftungsverteilernetztes des Blechs der supply_air des Verteilernetzes
        """
        # Determining the sheet thickness
        dataframe_distribution_network_supply_air["sheet thickness"] = dataframe_distribution_network_supply_air.apply(
            lambda row: self.sheet_metal_thickness(pressure_loss, row["duct cross section"]), axis=1)

        # Berechnung des BlechvolumensCalculation of the sheet volume
        dataframe_distribution_network_supply_air["Sheet volume"] = dataframe_distribution_network_supply_air[
                                                                        "sheet thickness"] * \
                                                                    dataframe_distribution_network_supply_air[
                                                                        'Surface area']

        list_dataframe_distribution_network_supply_air_blechgewicht = [v * (7850 * ureg.kilogram / ureg.meter ** 3) for
                                                                       v in
                                                                       dataframe_distribution_network_supply_air[
                                                                           "Sheet volume"]]
        # density steel 7850 kg/m³

        # Calculation of the sheet weight
        dataframe_distribution_network_supply_air[
            "Sheet weight"] = list_dataframe_distribution_network_supply_air_blechgewicht

        # Determination of the CO2 of the duct
        dataframe_distribution_network_supply_air["CO2-Kanal"] = dataframe_distribution_network_supply_air[
                                                                     "Sheet weight"] * (
                                                                         float(
                                                                             gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[
                                                                                 0]["A1-A3"]) + float(
                                                                     gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0][
                                                                         "C2"]))

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
                    height = ureg(row['hight'])
                except AttributeError:
                    width = row['width']
                    height = row['hight']
                cross_sectional_area = ((width + 0.04 * ureg.meter) * (height + 0.04 * ureg.meter)) - (
                        width * height)  # 20mm Dämmung des Lüftungskanals nach aneredges Regeln der Technik nach Missel Seite 42

            return cross_sectional_area.to(ureg.meter ** 2)

        # Calculation of the insulation
        dataframe_distribution_network_supply_air[
            'Cross-sectional area of insulation'] = dataframe_distribution_network_supply_air.apply(
            cross_sectional_area_duct_insulation, axis=1)

        dataframe_distribution_network_supply_air['Isolation volume'] = dataframe_distribution_network_supply_air[
                                                                           'Cross-sectional area of insulation'] * \
                                                                       dataframe_distribution_network_supply_air[
                                                                           'duct length']

        gwp_isulation = (
                    121.8 * ureg.kilogram / ureg.meter ** 3 + 1.96 * ureg.kilogram / ureg.meter ** 3 + 10.21 * ureg.kilogram / ureg.meter ** 3)
        # https://www.oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?lang=de&uuid=eca9691f-06d7-48a7-94a9-ea808e2d67e8

        list_dataframe_distribution_network_supply_air_CO2_duct_isolation = [v * gwp_isulation for v in
                                                                            dataframe_distribution_network_supply_air[
                                                                                "Isolation volume"]]

        dataframe_distribution_network_supply_air[
            "CO2 Duct Isolation"] = list_dataframe_distribution_network_supply_air_CO2_duct_isolation


        # Export to Excel
        dataframe_distribution_network_supply_air.to_excel(
            self.paths.export / 'ventilation system' / 'supply air' / 'dataframe_supply_air.xlsx', index=False)

        """
        Berechnung des CO2 für die room_connection
        """
        # Ermittlung des CO2-Kanal
        dataframe_rooms["CO2-Kanal"] = dataframe_rooms["Sheet weight"] * (
                    float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0][
                              "A1-A3"]) + float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"])
                    )

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

            'hight': [100 * ureg.millimeter, 100 * ureg.millimeter, 100 * ureg.millimeter, 100 * ureg.millimeter,
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
                width, height = row['width'], row['hight']
                passende_zeilen = df_trox_tvj_diameter_gewicht[
                    (df_trox_tvj_diameter_gewicht['width'] >= width) & (
                            df_trox_tvj_diameter_gewicht['hight'] >= height)]
                if not passende_zeilen.empty:
                    return passende_zeilen.sort_values(by=['width', 'hight', 'Gewicht']).iloc[0]['Gewicht']
            return None

        # Kombinierte Funktion, die beide Funktionen ausführt
        def gewicht_volumenstromregler(row):
            gewicht_rn = gewicht_runde_volumenstromregler(row)
            if gewicht_rn is not None:
                return gewicht_rn
            return gewicht_angulare_volumenstromregler(row)

        # Anwenden der Funktion auf jede Zeile
        dataframe_rooms['Gewicht Volume_flow_controller'] = dataframe_rooms.apply(gewicht_volumenstromregler, axis=1)

        dataframe_rooms["CO2-Volume_flow_controller"] = dataframe_rooms['Gewicht Volume_flow_controller'] * (
                19.08 + 0.01129 + 0.647) * 0.348432
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

        # Gewicht Dämmung silencer
        dataframe_rooms['Isolation volume silencer'] = dataframe_rooms.apply(volumen_daemmung_schalldaempfer,
                                                                                 axis=1)

        gwp_daemmung_schalldaempfer = (117.4 + 2.132 + 18.43) * (ureg.kilogram / (ureg.meter ** 3))
        # https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=89b4bfdf-8587-48ae-9178-33194f6d1314&version=00.02.000&stock=OBD_2023_I&lang=de

        list_dataframe_distribution_network_supply_air_CO2_schalldaempferdaemmung = [v * gwp_daemmung_schalldaempfer for
                                                                                     v in dataframe_rooms[
                                                                                         "Isolation volume silencer"]]

        dataframe_rooms[
            "CO2-Dämmung silencer"] = list_dataframe_distribution_network_supply_air_CO2_schalldaempferdaemmung

        # Gewicht des Metalls des Schalldämpfers für Trox CA für Packungsdicke 50 bis 400mm danach Packungsdicke 100
        # vordefinierte Daten für Trox CA silencer
        trox_ca_diameter_gewicht = {
            'diameter': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter,
                            200 * ureg.millimeter, 250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter,
                            450 * ureg.millimeter, 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                            710 * ureg.millimeter, 800 * ureg.millimeter],
            'Gewicht': [6 * ureg.kilogram, 6 * ureg.kilogram, 7 * ureg.kilogram, 8 * ureg.kilogram, 10 * ureg.kilogram,
                        12 * ureg.kilogram, 14 * ureg.kilogram, 18 * ureg.kilogram, 24 * ureg.kilogram,
                        28 * ureg.kilogram, 45 * ureg.kilogram * 2 / 3, 47 * ureg.kilogram * 2 / 3,
                        54 * ureg.kilogram * 2 / 3, 62 * ureg.kilogram * 2 / 3]
        }
        df_trox_ca_diameter_gewicht = pd.DataFrame(trox_ca_diameter_gewicht)

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

        dataframe_rooms["CO2-Blech Schalldämfer"] = dataframe_rooms["Gewicht Blech silencer"] * (
                float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["A1-A3"]) + float(
            gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"]))

        # Berechnung der Dämmung
        dataframe_rooms['Cross-sectional area of insulation'] = dataframe_rooms.apply(cross_sectional_area_duct_insulation,
                                                                              axis=1)

        dataframe_rooms['Isolation volume'] = dataframe_rooms['Cross-sectional area of insulation'] * dataframe_rooms[
            'duct length']

        gwp_kanaldaemmung = (
                    121.8 * (ureg.kilogram / ureg.meter ** 3) + 1.96 * (ureg.kilogram / ureg.meter ** 3) + 10.21 * (
                        ureg.kilogram / ureg.meter ** 3))
        # https://www.oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?lang=de&uuid=eca9691f-06d7-48a7-94a9-ea808e2d67e8

        list_dataframe_rooms_CO2_kanaldaemmung = [v * gwp_kanaldaemmung for v in dataframe_rooms["Isolation volume"]]

        dataframe_rooms['CO2 Duct Isolation'] = list_dataframe_rooms_CO2_kanaldaemmung


        # Export to Excel
        dataframe_rooms.to_excel(self.paths.export / 'ventilation system' / 'supply air' / 'dataframe_rooms.xlsx', index=False)

        return pressure_loss, dataframe_rooms, dataframe_distribution_network_supply_air
