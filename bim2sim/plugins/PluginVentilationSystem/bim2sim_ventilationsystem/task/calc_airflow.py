import os
import math
import pandas as pd
from openpyxl.utils import get_column_letter
from ebcpy import TimeSeriesData
import pickle

from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.elements.mapping.units import ureg


class CalcAirFlow(ITask):
    """Calculate the needed airflow for all rooms/spaces in the building.

    Annahmen: DIN EN 16798-1
    Inputs: IFC Modell, Räume,

    Args:
        elements: bim2sim elements
    Returns:
        elements: bim2sim elements enriched with needed air flows
    """
    reads = ('elements',)
    touches = ('elements', 'air_flow_building')

    # Define user-defined unit for persons
    ureg.define('person = []')

    def run(self, elements):

        export = self.playground.sim_settings.export_graphs

        thermal_zones = filter_elements(elements, 'ThermalZone')

        self.logger.info("Start calculating the needed air flows for each zone")

        # ToDo Differentiate thermal zones in attic in commonUsages
        for tz in thermal_zones:
            for storey in tz.storeys:
                if storey.name == "Dachgeschoss":
                    tz.with_ahu = False

        # The required air volumes per room are calculated here
        self.calc_air_flow_zone(thermal_zones=thermal_zones,
                                elements=elements,
                                get_from_simulation=True)
        self.logger.info("Caluclated airflows for spaces succesful")

        self.logger.info("Start calculating the needed air flow for the buiding")
        # The sum of the air volumes is calculated here
        air_flow_building = self.calc_air_flow_building(thermal_zones)
        self.logger.info(f"Caluclated airflow for building {air_flow_building} succesful")

        self.logger.info("Creation of the dataframe for the air volume calculation")
        self.create_dataframe_air_volumes(thermal_zones)

        return elements, air_flow_building

    def calc_air_flow_zone(self, thermal_zones, elements, get_from_simulation: bool = False):
        """Function calculates the airflow of one specific zone.

        Args:
            thermal_zones: ThermalZone bim2sim element
        Returns:
            airflow: calculated airflow of the specific zone
        """

        if get_from_simulation:
            pickle_path = self.playground.sim_settings.serialized_elements_path
            with open(pickle_path, 'rb') as file:
                deserialized_elements = pickle.load(file)

            tzs = filter_elements(deserialized_elements, 'ThermalZone')
            agg_tzs = filter_elements(deserialized_elements, 'AggregatedThermalZone')
            for agg_tz in agg_tzs:
                tzs.append(agg_tz)

            teaser_max_vent_rate_dict = self.read_teaser_result_file()

            max_vent_rate_dict = {}
            tz_i = 1
            for tz in tzs:
                max_vent_rate_dict[str(tz_i)] = {}
                max_vent_rate_dict[str(tz_i)]["space_guids"] = []
                max_vent_rate_dict[str(tz_i)]["space_guids"].append(tz.guid)
                tz_i += 1

            for key, values in max_vent_rate_dict.items():
                max_vent_rate = teaser_max_vent_rate_dict[str(key)]["MaxVentRate"] / ureg.hour
                design_vent_rate = max_vent_rate / 1.5  # Reduces design ventilation rate due to aerodynamic reasons (losses, acoustics)
                values["design_vent_rate"] = design_vent_rate

                for tz_values in tzs:
                    if tz_values.guid == values["space_guids"][0]:
                        values["usage"] = tz_values.usage

            max_vent_rate_disagg = {}
            k = 1
            for i, tz in enumerate(tzs):
                i += 1
                if tz.element_type == "ThermalZone":
                    max_vent_rate_disagg[k] = max_vent_rate_dict[str(i)]
                    k += 1
                else:
                    tz_in_agg_tz_dict = {}
                    max_vent_rate_agg_tz = max_vent_rate_dict[str(i)]['design_vent_rate']
                    for guid in tz.elements:
                        tz_in_agg_tz_dict[guid] = {}
                        tz_in_agg_tz_dict[guid]['usage'] = elements[guid].usage

                    for guid, values in tz_in_agg_tz_dict.items():
                        max_vent_rate_tz = max_vent_rate_agg_tz
                        max_vent_rate_disagg[k] = {'design_vent_rate': max_vent_rate_tz,
                                                   'space_guids': [guid],
                                                   'usage': values['usage']}
                        k += 1

            tz_i = 1
            for tz in thermal_zones:
                tz.air_flow = max_vent_rate_disagg[tz_i]['design_vent_rate'] * tz.volume
                tz_i += 1

        else:
            for tz in thermal_zones:
                # persons_per_square_meter = tz.persons * ureg.person # persons/m² (data source is din 18599)
                # area = tz.net_area  # Area of the room
                # persons_per_room = math.ceil(persons_per_square_meter * area.magnitude) # number of people
                # per room,
                # rounded up!

                # if tz.usage == "WC and sanitary rooms in non-residential buildings":
                #     tz.area_air_flow_factor = 11 * (ureg.meter**3)/(ureg.hour * ureg.meter**2)  # ASR A4.1 Page 5; 5.1. Allgemeines
                #     tz.persons_air_flow_factor = 0
                # else:
                #     tz.area_air_flow_factor = 0.7 * (ureg.liter/(ureg.second * ureg.meter**2))  # from DIN EN 16798-1:2022-03 table B.7 , Kat II, Schadstoffarmes Gebäude
                #     tz.persons_air_flow_factor = 7 * (ureg.liter/(ureg.second * ureg.person)) # from DIN EN 16798-1:2022-03 table B.6, Kat II

                # area_airflow = area * tz.area_air_flow_factor
                # person_airflow = persons_per_room * tz.persons_air_flow_factor

                if tz.with_ahu:  # True
                    # tz.air_flow = person_airflow + area_airflow
                    # TODO
                    tz.air_flow = tz.max_ahu * tz.net_area
                    tz.air_flow = tz.air_flow.to(ureg.meter ** 3 / ureg.hour)
                else:
                    tz.air_flow = 0 * ureg.meter ** 3 / ureg.hour

    def read_teaser_result_file(self):
        """Reads teaser result file and extracts maximal ventilation rates per thermal zone

            Args:
                None
            Returns:
                teaser_max_vent_rates: dict of maximal ventilation rate per thermal zone
        """

        filepath = self.playground.sim_settings.teaser_result_file
        tsd = TimeSeriesData(filepath)

        time_column = tsd.index
        teaser_names = tsd.get_variable_names()
        teaser_max_vent_rate_dict = {}
        for teaser_var in teaser_names:
            var = "ventRate"
            if var in teaser_var:
                try:
                    zone = teaser_var.split(".")[1]
                except:
                    print(f'Warning: {teaser_var} has no "." in name.')
                # thermal_zonenplugin_teasern
                if zone.find("[") > -1:
                    thermal_zone = zone[zone.find("[") + 1:zone.rfind("]")]
                    if thermal_zone.find(",") > -1:
                        split = thermal_zone.split(",")
                        thermal_zone = split[0]

                    if thermal_zone not in teaser_max_vent_rate_dict:
                        teaser_max_vent_rate_dict[thermal_zone] = {}

                    value_list = (tsd[teaser_var].values.tolist())
                    max_value = max(value_list[24:])

                    teaser_max_vent_rate_dict[thermal_zone]["MaxVentRate"] = max_value

        return teaser_max_vent_rate_dict

    def calc_air_flow_building(self, thermal_zones):
        """Function calculates the airflow of the complete building.

        Args:
            tz: ThermalZone bim2sim element
        Returns:
            building airflow: calculated airflow of the building
        """
        building_air_flow = 0 * ureg.liter / ureg.second
        for tz in thermal_zones:
            building_air_flow += tz.air_flow
        return building_air_flow

    def create_dataframe_air_volumes(self, thermal_zones):
        """
        Function create a dataframe for the air volumes
        :param thermal_zones: Thermal Zones
        :return: dataframe and export Excel
        """
        air_volumes_df = pd.DataFrame({
            "GUID": [tz.guid for tz in thermal_zones],
            "Room name": [tz.zone_name for tz in thermal_zones],
            "Ceiling coordinate": [round(tz.space_center.Z() + tz.height.magnitude / 2, 2) for tz in thermal_zones],
            "Type of use": [tz.usage for tz in thermal_zones],
            "Clear height of the room": [tz.height for tz in thermal_zones],
            "Room volume": [tz.net_volume for tz in thermal_zones],
            "Number of persons": [math.ceil(tz.persons * tz.net_area.magnitude) for tz in thermal_zones],
            # "Air volume factor person": [tz.persons_air_flow_factor for tz in thermal_zones],
            "Floor area of the room": [tz.net_area for tz in thermal_zones],
            # "Air volume factor Area": [tz.area_air_flow_factor for tz in thermal_zones],
            "Ventilation required:": [tz.with_ahu for tz in thermal_zones],
            "Total air volume": [tz.air_flow for tz in thermal_zones]
        })

        # Path for saving
        ventilation_directory = self.paths.export / 'ventilation system'
        air_volumes_excel_path = ventilation_directory / 'air_volume_calculation.xlsx'

        ventilation_directory.mkdir(parents=True, exist_ok=True)

        # Add a new line with zeros (or NaNs, as required)
        air_volumes_df.loc['sum'] = 0

        summe = air_volumes_df['Total air volume'].sum()

        # Calculating the sum
        air_volumes_df.loc['sum', 'Total air volume'] = summe

        # Save as Excel
        air_volumes_df.to_excel(air_volumes_excel_path)

        # Save
        with pd.ExcelWriter(air_volumes_excel_path, engine='openpyxl') as writer:
            air_volumes_df.to_excel(writer, index=False, sheet_name="Air volume calculation")

            # Auto-adjustment of the column widths
            for column in writer.sheets['Air volume calculation'].columns:
                max_length = 0
                column = [cell for cell in column if cell.value]
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(cell.value)
                    except:
                        pass
                adjusted_width = (max_length + 2)
                writer.sheets['Air volume calculation'].column_dimensions[
                    get_column_letter(column[0].column)].width = adjusted_width
