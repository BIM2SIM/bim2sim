import os
import math
import pandas as pd
from openpyxl.utils import get_column_letter
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
        self.calc_air_flow_zone(thermal_zones)
        self.logger.info("Caluclated airflows for spaces succesful")

        self.logger.info("Start calculating the needed air flow for the buiding")
        # The sum of the air volumes is calculated here
        air_flow_building = self.calc_air_flow_building(thermal_zones)
        self.logger.info(f"Caluclated airflow for building {air_flow_building} succesful")

        self.logger.info("Creation of the dataframe for the air volume calculation")
        self.create_dataframe_air_volumes(thermal_zones)

        return elements, air_flow_building

    def calc_air_flow_zone(self, thermal_zones):
        """Function calculates the airflow of one specific zone.

        Args:
            thermal_zones: ThermalZone bim2sim element
        Returns:
            airflow: calculated airflow of the specific zone
        """

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
                tz.air_flow = tz.air_flow.to(ureg.meter**3 / ureg.hour)
            else:
                tz.air_flow = 0 * ureg.meter**3 / ureg.hour

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
