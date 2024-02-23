import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D
import pandas as pd
from pathlib import Path
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from decimal import Decimal, ROUND_UP



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
             'dataframe_rooms_supply_air',
             'dataframe_distribution_network_supply_air',
             'building_shaft_exhaust_air',
             'graph_ventilation_duct_length_exhaust_air',
             'pressure_loss_exhaust_air',
             'dataframe_rooms_exhaust_air',
             'dataframe_distribution_network_exhaust_air',
             'air_flow_building'
             )
    touches = ()

    def run(self,
            corners_building,
            building_shaft_supply_air,
            graph_ventilation_duct_length_supply_air,
            pressure_loss_supply_air,
            dataframe_rooms_supply_air,
            dataframe_distribution_network_supply_air,
            building_shaft_exhaust_air,
            graph_ventilation_duct_length_exhaust_air,
            pressure_loss_exhaust_air,
            dataframe_rooms_exhaust_air,
            dataframe_distribution_network_exhaust_air,
            air_flow_building
            ):

        export = self.playground.sim_settings.ventilation_lca_system
        air_flow_building = air_flow_building.to('m**3 / hour')

        self.logger.info("Plot 3D Graph")
        self.plot_3d_graphs(graph_ventilation_duct_length_supply_air,
                            graph_ventilation_duct_length_exhaust_air)

        self.logger.info("Calculate Fire Dampers")
        (dataframe_fire_dampers_supply_air,
         dataframe_fire_dampers_exhaust_air) = self.fire_dampers(corners_building,
                                                                building_shaft_supply_air,
                                                                dataframe_distribution_network_supply_air,
                                                                building_shaft_exhaust_air,
                                                                dataframe_distribution_network_exhaust_air,
                                                                export)

        self.logger.info("CO2-Calcualtion for the complete ventilation system")
        self.co2_ventilation_system(air_flow_building,
                                    dataframe_rooms_supply_air,
                                    dataframe_rooms_exhaust_air,
                                    dataframe_distribution_network_supply_air,
                                    dataframe_distribution_network_exhaust_air,
                                    dataframe_fire_dampers_supply_air,
                                    dataframe_fire_dampers_exhaust_air,
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
                     dataframe_distribution_network_supply_air,
                     building_shaft_exhaust_air,
                     dataframe_distribution_network_exhaust_air,
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
        :param dataframe_distribution_network_supply_air: dataframe
        :param building_shaft_exhaust_air: tuple (x,y,z) shaft positio
        :param dataframe_distribution_network_exhaust_air: dataframe
        :param export: True or False
        :return: dataframe fire dampers supply and exhaust air
        """

        # Function that receives a nominal size and returns the weight of the next larger nominal size
        def get_next_larger_weight_fire_damp(nominal_size):
            # Schako Fire Damper https://schako.com/wp-content/uploads/bsk-rpr_de.pdf
            nominal_size_weight_dict = {
                100*ureg.millimeter: 6.73*ureg.kilogram,
                125*ureg.millimeter: 7.69*ureg.kilogram,
                140*ureg.millimeter: 8.27*ureg.kilogram,
                160*ureg.millimeter: 9.02*ureg.kilogram,
                180*ureg.millimeter: 9.79*ureg.kilogram,
                200*ureg.millimeter: 10.59*ureg.kilogram,
                224*ureg.millimeter: 11.58*ureg.kilogram,
                250*ureg.millimeter: 12.62*ureg.kilogram,
                280*ureg.millimeter: 16.55*ureg.kilogram,
                315*ureg.millimeter: 18.40*ureg.kilogram,
                355*ureg.millimeter: 20.53*ureg.kilogram,
                400*ureg.millimeter: 22.89*ureg.kilogram,
                450*ureg.millimeter: 25.84*ureg.kilogram,
                500*ureg.millimeter: 28.75*ureg.kilogram,
                550 * ureg.millimeter: 31.69 * ureg.kilogram, # Extrapoliert
                600 * ureg.millimeter: 34.60 * ureg.kilogram, # Extrapoliert
                650 * ureg.millimeter: 37.51 * ureg.kilogram, # Extrapoliert
                700 * ureg.millimeter: 40.42 * ureg.kilogram, # Extrapoliert
                750 * ureg.millimeter: 43.33 * ureg.kilogram, # Extrapoliert
                800 * ureg.millimeter: 46.24 * ureg.kilogram # Extrapoliert
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

        # dataframe fire damper supply air:
        dataframe_fire_dampers_supply_air = pd.DataFrame(columns=['Startknoten',
                                                                 'Zielknoten',
                                                                 'Kante',
                                                                 'rechnerischer Durchmesser'])  # dataframe for fire
        # fire dampers for supply air
        for index, line in dataframe_distribution_network_supply_air.iterrows():
            starting_point = line['Startknoten']
            end_point = line['Zielknoten']
            if (starting_point[0] == building_shaft_supply_air[0]) and (
                    starting_point[1] == building_shaft_supply_air[1] and (
                    starting_point[2] == end_point[2]
            )):
                new_rows = [{'Startknoten': dataframe_distribution_network_supply_air.at[index, 'Startknoten'],
                             'Zielknoten': dataframe_distribution_network_supply_air.at[index, 'Zielknoten'],
                             'Kante': dataframe_distribution_network_supply_air.at[index, 'Kante'],
                             'rechnerischer Durchmesser': dataframe_distribution_network_supply_air.at[
                                 index, 'rechnerischer Durchmesser'],
                             'Gewicht Brandschutzklappe': get_next_larger_weight_fire_damp(
                                 dataframe_distribution_network_supply_air.at[index, 'rechnerischer Durchmesser'])}
                            ]

                # Add to dataframe
                dataframe_fire_dampers_supply_air = pd.concat([dataframe_fire_dampers_supply_air, pd.DataFrame(new_rows)],
                                                             ignore_index=True)

        dataframe_fire_dampers_supply_air['Number of Fire Dampers'] = fire_dampers_per_floor

        # dataframe fire damper exhaust air:
        dataframe_fire_dampers_exhaust_air = pd.DataFrame(columns=['Startknoten',
                                                                  'Zielknoten',
                                                                  'Kante',
                                                                  'rechnerischer Durchmesser'])  # dataframe for fire dampers for supply air

        for index, line in dataframe_distribution_network_exhaust_air.iterrows():
            starting_point = line['Startknoten']
            end_point = line['Zielknoten']
            if (end_point[0] == building_shaft_exhaust_air[0]) and (
                    end_point[1] == building_shaft_exhaust_air[1]) and (
                    starting_point[2] == end_point[2]
            ):
                new_rows = [{'Startknoten': dataframe_distribution_network_exhaust_air.at[index, 'Startknoten'],
                             'Zielknoten': dataframe_distribution_network_exhaust_air.at[index, 'Zielknoten'],
                             'Kante': dataframe_distribution_network_exhaust_air.at[index, 'Kante'],
                             'rechnerischer Durchmesser': dataframe_distribution_network_exhaust_air.at[
                                 index, 'rechnerischer Durchmesser'],
                             'Gewicht Brandschutzklappe': get_next_larger_weight_fire_damp(
                                 dataframe_distribution_network_exhaust_air.at[index, 'rechnerischer Durchmesser'])}
                            ]

                # Add to dataframe
                dataframe_fire_dampers_exhaust_air = pd.concat(
                    [dataframe_fire_dampers_exhaust_air, pd.DataFrame(new_rows)], ignore_index=True)

        dataframe_fire_dampers_exhaust_air['Number of Fire Dampers'] = fire_dampers_per_floor

        gwp_fire_damper_per_kilo = (20.7 + 0.177 + 0.112 + 2.84) / 6.827
        # https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=e8f279e9-d72d-4645-bb33-5651d9ec07c0&version=00.01.000&stock=OBD_2023_I&lang=de

        dataframe_fire_dampers_supply_air['Gewicht Brandschutzklappe ges'] = dataframe_fire_dampers_supply_air['Gewicht Brandschutzklappe'] * dataframe_fire_dampers_supply_air['Number of Fire Dampers'].astype(float)
        dataframe_fire_dampers_exhaust_air['Gewicht Brandschutzklappe ges'] = dataframe_fire_dampers_exhaust_air['Gewicht Brandschutzklappe'] * dataframe_fire_dampers_exhaust_air['Number of Fire Dampers'].astype(float)

        # Calculating CO2
        list_dataframe_fire_dampers_supply_air_CO2_fire_dampers = [v * gwp_fire_damper_per_kilo for v in dataframe_fire_dampers_supply_air['Gewicht Brandschutzklappe ges']]
        dataframe_fire_dampers_supply_air['CO2 Fire Damper'] = list_dataframe_fire_dampers_supply_air_CO2_fire_dampers

        list_dataframe_fire_dampers_exhaust_air_CO2_fire_dampers = [v * gwp_fire_damper_per_kilo for v in
                                                                   dataframe_fire_dampers_exhaust_air[
                                                                       'Gewicht Brandschutzklappe ges']]
        dataframe_fire_dampers_supply_air['CO2 Fire Damper'] = list_dataframe_fire_dampers_exhaust_air_CO2_fire_dampers

        if export:
            # Pfad für die Exportdatei definieren
            export_pfad = self.paths.export / 'Brandschutzklappen.xlsx'

            # ExcelWriter verwenden, um mehrere dataframes in einer Excel-Datei zu speichern
            with pd.ExcelWriter(export_pfad) as writer:
                # Speichern des ersten dataframes in einem Tabellenblatt
                dataframe_fire_dampers_supply_air.to_excel(writer, sheet_name='Brandschutzklappen Zuluft', index=False)

                # Speichern des anderen dataframes in einem anderen Tabellenblatt
                dataframe_fire_dampers_exhaust_air.to_excel(writer, sheet_name='Brandschutzklappen Abluft', index=False)

        return dataframe_fire_dampers_supply_air, dataframe_fire_dampers_exhaust_air

    def co2_ventilation_system(self,
                               air_flow_building,
                               dataframe_rooms_supply_air,
                               dataframe_rooms_exhaust_air,
                               dataframe_distribution_network_supply_air,
                               dataframe_distribution_network_exhaust_air,
                               dataframe_fire_dampers_supply_air,
                               dataframe_fire_dampers_exhaust_air,
                               export
                               ):

        # List of dataframes
        dataframes = [
            ('Rooms Supply Air', dataframe_rooms_supply_air),
            ('Rooms Exhaust Air', dataframe_rooms_exhaust_air),
            ('Distribution Supply Air', dataframe_distribution_network_supply_air),
            ('Distribution Exhaust Air', dataframe_distribution_network_exhaust_air),
            ('Fire Dampers Supply Air', dataframe_fire_dampers_supply_air),
            ('Fire Dampers Exhaust Air', dataframe_fire_dampers_exhaust_air)
        ]

        # Results list
        results_list = []

        # Calculate the sum for each column in each dataframe
        for name, df in dataframes:
            for column in df.columns:
                if "CO2" in column:
                    total_sum = df[column].sum()
                    results_list.append({'dataframe': name, 'Title': column, 'Sum CO2': total_sum})

        # Store the result in a new dataframe
        co2_result_distribution_by_type = pd.DataFrame(results_list)

        # Initialize sums for supply and exhaust
        supply_sum = 0 * ureg.kilogram
        exhaust_sum = 0 * ureg.kilogram
        orther_sum = 0 * ureg.kilogram

        # Iterate through each row and add to the appropriate sum
        for _, row in co2_result_distribution_by_type.iterrows():
            if 'Supply' in row['dataframe']:
                supply_sum += row['Sum CO2']
            elif 'Exhaust' in row['dataframe']:
                exhaust_sum += row['Sum CO2']
            elif row['dataframe']:
                orther_sum += row['Sum CO2']

        def gwp_ventilation_unit(air_flow_building):
            # ventilation system (https://www.epddanmark.dk/media/43kpnonw/md-23024-en.pdf):
            gwp_total_3000m3_per_h_ventilation_unit = 3540.0 * ureg.kilogram
            gwp_total_15000m3_per_h_ventilation_unit = 9210.0 * ureg.kilogram

            gwp_ventilation_unit_total = None

            if air_flow_building.magnitude < 3000:
                gwp_ventilation_unit_total = gwp_total_3000m3_per_h_ventilation_unit
            elif 3000 <= air_flow_building.magnitude <= 15000:
                gwp_ventilation_unit_total = gwp_total_3000m3_per_h_ventilation_unit + (
                        gwp_total_15000m3_per_h_ventilation_unit - gwp_total_3000m3_per_h_ventilation_unit) / (
                                                     15000 - 3000) * (air_flow_building.magnitude - 3000)
            elif air_flow_building.magnitude > 15000:
                gwp_ventilation_unit_total = "Out of range"

            return gwp_ventilation_unit_total

        # Electrical power for the ventilation system: Beim Einbau einer Klimaanlage, die eine Nennleistung für den
        # Kältebedarf von mehr als 12 Kilowatt hat, und einer raumlufttechnischen Anlage mit Zu- und Abluftfunktion,
        # die für einen Volumenstrom der Zuluft von wenigstens 4 000 Kubikmetern je Stunde ausgelegt ist,
        # in ein Gebäude sowie bei der Erneuerung von einem Zentralgerät oder Luftkanalsystem einer solchen Anlage
        # muss diese Anlage so ausgeführt werden, dass bei Auslegungsvolumenstrom der Grenzwert für die spezifische
        # Ventilatorleistung nach DIN EN 16798-3: 2017-11 Kategorie 4 nicht überschritten wird [...]
        #
        # Der Grenzwert für die spezifische Ventilatorleistung der Kategorie 4 kann um Zuschläge nach DIN EN 16798:
        # 2017-11 Abschnitt 9.5.2.2 für Gas- und Schwebstofffilter- sowie Wärmerückführungsbauteile der Klasse H2
        # nach DIN EN 13053: 2012-02 erweitert werden.
        #
        # Druckverlust für Wärmerückgewinnungseinheit nach VDI 3803-6 Tabelle 11 Wärmerückgewinnungseinheit Klasse H2
        # normal: 300 Pa

        def electrical_power_for_the_ventilation_system(air_flow_building):
            # Classification of the specific fan performance: Table 14 DIN EN 16798-3:2022-12
            # Cat 4:
            p_sft = 2000  # W/(m³/s)

            p_ventilation = p_sft * air_flow_building.to('m**3 / sec').magnitude

            # DIN EN 13053:2020-05 formular 35
            p_heat_recovery_unit = air_flow_building.to('m**3 / sec').magnitude * 300 * 1 / 0.6

            return (p_ventilation + p_heat_recovery_unit) * ureg.watt

        def co2_electrical_power_for_the_ventilation_system(electrical_power_for_the_ventilation_system):
            # Lifetime of ventilation system: 20 years
            # Residual electricity mix 2030 https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?lang=en&uuid=bef62d91-ae8d-4c27-bdf8-386f9dfc8477&version=20.23.050
            gwp_residual_electricity_mix = 0.8415 * ureg.kilogram / (1000 * ureg.watt * ureg.hour)
            # two ventilators needed (supply and exhaust air)
            # 250 working days per year
            # 12 hours a day

            co2_electrical_power = 2 * electrical_power_for_the_ventilation_system * gwp_residual_electricity_mix * 12 * ureg.hour / ureg.day * 250 * ureg.day * 20  # years

            return co2_electrical_power

        co2_result_supply_exhaust_others = pd.DataFrame({'type': ['Supply',
                                                                  'Exhaust',
                                                                  'Ventilation Unit',
                                                                  'Electrical power',
                                                                  'Other'],
                                                         'CO2': [supply_sum,
                                                                 exhaust_sum,
                                                                 gwp_ventilation_unit(air_flow_building),
                                                                 co2_electrical_power_for_the_ventilation_system(
                                                                     electrical_power_for_the_ventilation_system(
                                                                         air_flow_building)),
                                                                 orther_sum]})

        if export:
            # path for folder
            folder_path = Path(self.paths.export / 'CO2')

            # Create folder
            folder_path.mkdir(parents=True, exist_ok=True)

            # Export to Excel
            with pd.ExcelWriter(folder_path / 'CO2.xlsx', engine='openpyxl') as writer:
                co2_result_distribution_by_type.to_excel(writer, sheet_name='CO2-distribution broken down', index=False)
                co2_result_supply_exhaust_others.to_excel(writer, sheet_name='CO2-distribution', index=False)
