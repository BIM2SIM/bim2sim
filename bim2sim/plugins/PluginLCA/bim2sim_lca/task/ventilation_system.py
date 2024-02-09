import decimal
import bim2sim
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D
from itertools import chain
import math
import pandas as pd
import pandapipes as pp
import numpy as np
import requests
from pathlib import Path
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from decimal import Decimal, ROUND_UP
from networkx.utils import pairwise
from copy import deepcopy
import pandapipes.plotting as plot


class DesignVentilationSystem(ITask):
    """Design of the LCA

    Annahmen:
    Inputs: IFC Modell, Räume,

    Args:
        instances: bim2sim elements
    Returns:
        instances: bim2sim
    """
    reads = ('corners_building',
             'building_shaft_supply_air',
             'graph_ventilation_duct_length_supply_air',
             'pressure_loss_supply_air',
             'database_rooms_supply_air',
             'database_distribution_network_supply_air',
             'building_shaft_exhaust_air',
             'graph_ventilation_duct_length_exhaust_air',
             'pressure_loss_exhaust_air',
             'database_rooms_exhaust_air',
             'database_distribution_network_exhaust_air',
             'air_flow_building'
             )
    touches = ()

    def run(self,
            corners_building,
            building_shaft_supply_air,
            graph_ventilation_duct_length_supply_air,
            pressure_loss_supply_air,
            database_rooms_supply_air,
            database_distribution_network_supply_air,
            building_shaft_exhaust_air,
            graph_ventilation_duct_length_exhaust_air,
            pressure_loss_exhaust_air,
            database_rooms_exhaust_air,
            database_distribution_network_exhaust_air,
            air_flow_building
            ):

        export = self.playground.sim_settings.ventilation_lca_system
        print(air_flow_building)
        self.logger.info("Plot 3D Graph")
        self.plot_3d_graphs(graph_ventilation_duct_length_supply_air,
                            graph_ventilation_duct_length_exhaust_air)

        self.logger.info("Calculate Fire Dampers")
        (database_fire_dampers_supply_air,
         database_fire_dampers_exhaust_air) = self.fire_dampers(corners_building,
                                                                building_shaft_supply_air,
                                                                database_distribution_network_supply_air,
                                                                building_shaft_exhaust_air,
                                                                database_distribution_network_exhaust_air,
                                                                export)

        self.logger.info("CO2-Calcualtion for the complete ventilation system")
        self.co2_ventilation_system(database_rooms_supply_air,
                                    database_rooms_exhaust_air,
                                    database_distribution_network_supply_air,
                                    database_distribution_network_exhaust_air,
                                    database_fire_dampers_supply_air,
                                    database_fire_dampers_exhaust_air,
                                    export
                                    )

    def plot_3d_graphs(self, graph_ventilation_duct_length_supply_air, graph_ventilation_duct_length_exhaust_air):
        # Initialize the 3D plot
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Function to draw a graph
        def draw_graph(graph, color_nodes, color_edges):
            pos = {node: (node[0], node[1], node[2]) for node in graph.nodes()}
            for node, weight in nx.get_node_attributes(graph, 'weight').items():
                color = color_nodes if weight > 0 else 'black'
                ax.scatter(*node, color=color,
                           label='_nolegend_')  # '_nolegend_' entfernt doppelte Einträge in der Legende
            for edge in graph.edges():
                start, end = edge
                x_start, y_start, z_start = pos[start]
                x_end, y_end, z_end = pos[end]
                ax.plot([x_start, x_end], [y_start, y_end], [z_start, z_end], color=color_edges, label='_nolegend_')

        # Draw both graphs
        draw_graph(graph_ventilation_duct_length_supply_air, 'blue', 'blue')  # Colors for the first graph
        draw_graph(graph_ventilation_duct_length_exhaust_air, 'orange', 'orange')  # Colors for the second graph

        # Axis labels and title
        ax.set_xlabel('X-Axis [m]')
        ax.set_ylabel('Y-Axis [m]')
        ax.set_zlabel('Z-Axis [m]')
        ax.set_title("3D Graph of Ventilation Ducts")

        # Create custom legends
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=10, label='Supply Air'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', markersize=10, label='Exhaust Air')]
        ax.legend(handles=legend_elements)

        # plt.show()

        plt.close()

    def fire_dampers(self,
                     corners_building,
                     building_shaft_supply_air,
                     database_distribution_network_supply_air,
                     building_shaft_exhaust_air,
                     database_distribution_network_exhaust_air,
                     export):
        """
        The function fire dampers calculates the number of needed firedampers.
        Assumptions: 400m² rule according to Bau Ord. NRW. for example
                     number of fire dampers per floor: fire section = floor area/400m²
                     number of fire dampers = (fire_sections + 1) / 2
                     It is assumed that the duct cross-section constantly decreases away from the ventilation shaft.
                     The first fire damper therefore has the full size and the other fire dampers are selected smaller
                     as a percentage.
        :param corners_building: tuple ((xmin, ymin, zmin),(xmax, ymax, zmax))
        :param building_shaft_supply_air: tuple (x,y,z) shaft position
        :param database_distribution_network_supply_air: Database
        :param building_shaft_exhaust_air: tuple (x,y,z) shaft positio
        :param database_distribution_network_exhaust_air: Database
        :param export: True or False
        :return: Database fire dampers supply and exhaust air
        """

        # Function that receives a nominal size and returns the weight of the next larger nominal size
        def get_next_larger_weight_fire_damp(nominal_size):
            # Schako Fire Damper https://schako.com/wp-content/uploads/bsk-rpr_de.pdf
            nominal_size_weight_dict = {
                100: 6.73,
                125: 7.69,
                140: 8.27,
                160: 9.02,
                180: 9.79,
                200: 10.59,
                224: 11.58,
                250: 12.62,
                280: 16.55,
                315: 18.40,
                355: 20.53,
                400: 22.89,
                450: 25.84,
                500: 28.75
            }
            # Sort the nominal sizes in ascending order
            sorted_nominal_sizes = sorted(nominal_size_weight_dict.keys())

            # Find the next larger nominal size and return its weight
            for size in sorted_nominal_sizes:
                if size > nominal_size:
                    return nominal_size_weight_dict[size]
            return None  # If there is no larger nominal size, return None

        floor_space_building = int((corners_building[0][0] - corners_building[1][0]) * (
                corners_building[0][1] - corners_building[1][1]))

        # 400m2 rule from BAU Ord.Nrw
        fire_sections = (Decimal(floor_space_building) / 400).quantize(Decimal('1.'), rounding=ROUND_UP)
        fire_dampers_per_floor = (fire_sections + 1) / 2

        # Database fire damper supply air:
        database_fire_dampers_supply_air = pd.DataFrame(columns=['Startknoten',
                                                                 'Zielknoten',
                                                                 'Kante',
                                                                 'rechnerischer Durchmesser'])  # Dataframe for fire
        # fire dampers for supply air
        for index, line in database_distribution_network_supply_air.iterrows():
            starting_point = line['Startknoten']
            end_point = line['Zielknoten']
            if (starting_point[0] == building_shaft_supply_air[0]) and (
                    starting_point[1] == building_shaft_supply_air[1] and (
                    starting_point[2] == end_point[2]
            )):
                new_rows = [{'Startknoten': database_distribution_network_supply_air.at[index, 'Startknoten'],
                             'Zielknoten': database_distribution_network_supply_air.at[index, 'Zielknoten'],
                             'Kante': database_distribution_network_supply_air.at[index, 'Kante'],
                             'rechnerischer Durchmesser': database_distribution_network_supply_air.at[
                                 index, 'rechnerischer Durchmesser'],
                             'Gewicht Brandschutzklappe': get_next_larger_weight_fire_damp(
                                 database_distribution_network_supply_air.at[index, 'rechnerischer Durchmesser'])}
                            ]

                # Add to Dataframe
                database_fire_dampers_supply_air = pd.concat([database_fire_dampers_supply_air, pd.DataFrame(new_rows)],
                                                             ignore_index=True)

        database_fire_dampers_supply_air['Number of Fire Dampers'] = fire_dampers_per_floor

        # Database fire damper exhaust air:
        database_fire_dampers_exhaust_air = pd.DataFrame(columns=['Startknoten',
                                                                  'Zielknoten',
                                                                  'Kante',
                                                                  'rechnerischer Durchmesser'])  # Dataframe for fire dampers for supply air

        for index, line in database_distribution_network_exhaust_air.iterrows():
            starting_point = line['Startknoten']
            end_point = line['Zielknoten']
            if (end_point[0] == building_shaft_exhaust_air[0]) and (
                    end_point[1] == building_shaft_exhaust_air[1]) and (
                    starting_point[2] == end_point[2]
            ):
                new_rows = [{'Startknoten': database_distribution_network_exhaust_air.at[index, 'Startknoten'],
                             'Zielknoten': database_distribution_network_exhaust_air.at[index, 'Zielknoten'],
                             'Kante': database_distribution_network_exhaust_air.at[index, 'Kante'],
                             'rechnerischer Durchmesser': database_distribution_network_exhaust_air.at[
                                 index, 'rechnerischer Durchmesser'],
                             'Gewicht Brandschutzklappe': get_next_larger_weight_fire_damp(
                                 database_distribution_network_exhaust_air.at[index, 'rechnerischer Durchmesser'])}
                            ]

                # Add to Dataframe
                database_fire_dampers_exhaust_air = pd.concat(
                    [database_fire_dampers_exhaust_air, pd.DataFrame(new_rows)], ignore_index=True)

        database_fire_dampers_exhaust_air['Number of Fire Dampers'] = fire_dampers_per_floor

        gwp_fire_damper_per_kilo = (20.7 + 0.177 + 0.112 + 2.84) / 6.827
        # https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=e8f279e9-d72d-4645-bb33-5651d9ec07c0&version=00.01.000&stock=OBD_2023_I&lang=de

        # Calculating CO2
        database_fire_dampers_supply_air['CO2 Fire Damper'] = (
                database_fire_dampers_supply_air['Gewicht Brandschutzklappe'].astype(float) *
                database_fire_dampers_supply_air['Number of Fire Dampers'].astype(float) *
                gwp_fire_damper_per_kilo
        )

        database_fire_dampers_exhaust_air['CO2 Fire Damper'] = (
                database_fire_dampers_exhaust_air['Gewicht Brandschutzklappe'].astype(float) *
                database_fire_dampers_exhaust_air['Number of Fire Dampers'].astype(float) *
                gwp_fire_damper_per_kilo
        )

        if export:
            # Pfad für die Exportdatei definieren
            export_pfad = self.paths.export / 'Brandschutzklappen.xlsx'

            # ExcelWriter verwenden, um mehrere DataFrames in einer Excel-Datei zu speichern
            with pd.ExcelWriter(export_pfad) as writer:
                # Speichern des ersten DataFrames in einem Tabellenblatt
                database_fire_dampers_supply_air.to_excel(writer, sheet_name='Brandschutzklappen Zuluft', index=False)

                # Speichern des anderen DataFrames in einem anderen Tabellenblatt
                database_fire_dampers_exhaust_air.to_excel(writer, sheet_name='Brandschutzklappen Abluft', index=False)

        return database_fire_dampers_supply_air, database_fire_dampers_exhaust_air

    def co2_ventilation_system(self,
                               database_rooms_supply_air,
                               database_rooms_exhaust_air,
                               database_distribution_network_supply_air,
                               database_distribution_network_exhaust_air,
                               database_fire_dampers_supply_air,
                               database_fire_dampers_exhaust_air,
                               export
                               ):

        # List of DataFrames
        databases = [
            ('Rooms Supply Air', database_rooms_supply_air),
            ('Rooms Exhaust Air', database_rooms_exhaust_air),
            ('Distribution Supply Air', database_distribution_network_supply_air),
            ('Distribution Exhaust Air', database_distribution_network_exhaust_air),
            ('Fire Dampers Supply Air', database_fire_dampers_supply_air),
            ('Fire Dampers Exhaust Air', database_fire_dampers_exhaust_air)
        ]

        # Results list
        results_list = []

        # Calculate the sum for each column in each DataFrame
        for name, df in databases:
            for column in df.columns:
                if "CO2" in column:
                    total_sum = df[column].sum()
                    results_list.append({'Database': name, 'Title': column, 'Sum CO2': total_sum})

        # Store the result in a new DataFrame
        co2_result_distribution_by_type = pd.DataFrame(results_list)

        co2_result_supply = float()

        # Initialize sums for supply and exhaust
        supply_sum = 0
        exhaust_sum = 0
        orther_sum = 0

        # Iterate through each row and add to the appropriate sum
        for _, row in co2_result_distribution_by_type.iterrows():
            if 'Supply' in row['Database']:
                supply_sum += row['Sum CO2']
            elif 'Exhaust' in row['Database']:
                exhaust_sum += row['Sum CO2']
            elif row['Database']:
                orther_sum += row['Sum CO2']

        co2_result_supply_exhaust_others = pd.DataFrame({'type': ['Supply', 'Exhaust', 'Other'],
                                                         'CO2': [supply_sum, exhaust_sum, orther_sum]})

        if export:
            # path for folder
            folder_path = Path(self.paths.export / 'CO2')

            # Create folder
            folder_path.mkdir(parents=True, exist_ok=True)

            # Export to Excel
            with pd.ExcelWriter(folder_path / 'CO2.xlsx', engine='openpyxl') as writer:
                co2_result_distribution_by_type.to_excel(writer, sheet_name='CO2-distribution broken down', index=False)
                co2_result_supply_exhaust_others.to_excel(writer, sheet_name='CO2-distribution', index=False)

