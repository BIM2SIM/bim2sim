import math
import pandas as pd
from openpyxl.utils import get_column_letter
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.elements.mapping.units import ureg


class CalcAirFlow(ITask):
    """Calculate the needed airflow for all rooms/spaces in the building.

    - welche annahmen (Normen/Richtlinien)
    - welche inputs etc.

    Args:
        instances: bim2sim elements
    Returns:
        instances: bim2sim elements enriched with needed air flows
    """
    reads = ('instances', )
    touches = ('instances', )

    def run(self, instances):

        self.logger.info("Start calculating the needed air flows for each zone")
        thermal_zones = filter_instances(instances, 'ThermalZone')
        for tz in thermal_zones:
            tz.air_flow = self.calc_air_flow_zone(tz)
            print(tz)
        self.logger.info("Caluclated airflows for spaces succesful")

        self.logger.info("Start calculating the needed air flow for the buiding")
        air_flow_building = self.calc_air_flow_building(thermal_zones)
        print(air_flow_building)
        self.logger.info("Caluclated airflow for building succesful")


        output = True
        # TODO use sim_setting instead of output boolean
        if output:
            self.output_to_csv(thermal_zones)


        return instances,

    def calc_air_flow_zone(self, tz):
        """Function calculates the airflow of one specific zone.

        #TODO
        Args:
            tz: ThermalZone bim2sim element
        Returns:
            airflow: calculated airflow of the specific zone
        """
        name = tz.zone_name # Name of the room
        persons_per_square_meter = tz.persons  # persons/m² (data source is din 18599)
        area = tz.net_area # Area of the room
        persons_per_room = math.ceil(persons_per_square_meter * area) # number of people per room, rounded up!


        # TODO have a look at:
        #  bim2sim/assets/enrichment/usage/UseConditions.json
        factor_usage_dict = {
            "buero": []
        }
        # TODO
        area_air_flow_factor = 0.7 * ureg.liter / (ureg.s * ureg.meter ** 2 )
        persons_air_flow_factor = 7 * ureg.liter / ureg.s # from DIN EN 16798-1:2022-03 table B.6, Kat II
        area_airflow = area * area_air_flow_factor
        person_airflow = persons_per_room * persons_air_flow_factor
        air_flow = person_airflow + area_airflow
        print(name, air_flow)
        return air_flow

    def calc_air_flow_building(self, thermal_zones):
        """Function calculates the airflow of the complete building.

        #TODO
        Args:
            tz: ThermalZone bim2sim element
        Returns:
            building airflow: calculated airflow of the building
        """
        building_air_flow = 0 * ureg.meter ** 3 / ureg.second
        for tz in thermal_zones:
             building_air_flow += tz.air_flow

        print(building_air_flow)
        return building_air_flow


    def output_to_csv(self, thermal_zones):
        luftmengen_df = pd.DataFrame({
            "Raumname": [tz.zone_name for tz in thermal_zones],
            "Nutzungsart": [tz.usage for tz in thermal_zones],
            "Raumvolumen [m³]": [tz.net_volume for tz in thermal_zones],
            "Lichte Höhe des Raumes [m]": [tz.height for tz in thermal_zones],
            "Grundfläche des Raumes [m²]": [tz.net_area for tz in thermal_zones],
            # "Raumart": liste_raumart,
            "Personenanzahl": [math.ceil(tz.persons * tz.net_area) for tz in thermal_zones],
            # "Luftmengen Person [l/s]": luftmengen()[0],
            # "Luftmenge Fläche [l/s]": luftmengen()[1],
            "Luftmenge gesamt [m³/h]": [tz.air_flow for tz in thermal_zones]
        })

        # Pfad für Speichern
        luftmengen_excel_pfad = r"D:\OneDrive - Students RWTH Aachen University\0 UNI\Masterarbeit\TGA-Lueftung\Excel\Raumvolumen_neu.xlsx"

        # Hinzufügen einer neuen Zeile mit Nullen (oder NaNs, je nach Bedarf)
        luftmengen_df.loc['Summe'] = 0

        summe = luftmengen_df['Luftmenge gesamt [m³/h]'].sum()

        # Setzen der Summe nur in der gewünschten Spalte
        luftmengen_df.loc['Summe', 'Luftmenge gesamt [m³/h]'] = summe

        # Speichern als Excel
        luftmengen_df.to_excel(luftmengen_excel_pfad)

        # Verwenden von Pandas ExcelWriter mit der openpyxl Engine
        with pd.ExcelWriter(luftmengen_excel_pfad, engine='openpyxl') as writer:
            luftmengen_df.to_excel(writer, index=False, sheet_name="Luftmengenberechnung")

            # Autoanpassung der Spaltenbreiten
            for column in writer.sheets['Luftmengenberechnung'].columns:
                max_length = 0
                column = [cell for cell in column if cell.value]
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(cell.value)
                    except:
                        pass
                adjusted_width = (max_length + 2)
                writer.sheets['Luftmengenberechnung'].column_dimensions[
                    get_column_letter(column[0].column)].width = adjusted_width
