import math
import pandas as pd
from openpyxl.utils import get_column_letter
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.elements.mapping.units import ureg


class CalcAirFlow(ITask):
    """Calculate the needed airflow for all rooms/spaces in the building.

    Annahmen: DIN EN 16798-1
    Inputs: IFC Modell, Räume,

    Args:
        instances: bim2sim elements
    Returns:
        instances: bim2sim elements enriched with needed air flows
    """
    reads = ('instances', )
    touches = ('instances', )



    def run(self, instances):

        output = False

        thermal_zones = filter_instances(instances, 'ThermalZone')

        nutzung_ohne_lueftung = ["Stock, technical equipment, archives",
                                 "Storehouse, logistics building, Auxiliary areas (without common rooms)"
                                 ]
        #TODO die Liste muss erweitert werden, wenn andere Modelle verwendet werden!

        self.logger.info("Check whether a ventilation system is required")
        # Da nicht in jedem Raum nach DIN eine Lüftungsanlage erforderlich ist, wird hier überprüft, ob eine Lüftung
        # sinnvoll/ erforlderich ist oder ob es sich um einen nicht dauerhaft benutzten Raum handelt.
        # Es werden die vom 20.11.2023 vorhandenen Raumtypen zugrunde gelegt
        self.ventilation_system(thermal_zones, nutzung_ohne_lueftung)
        self.logger.info("Check successful")

        self.logger.info("Start calculating the needed air flows for each zone")
        # Hier werden die benötigten Luftmengen pro Raum berechnet
        self.calc_air_flow_zone(thermal_zones, nutzung_ohne_lueftung)
        self.logger.info("Caluclated airflows for spaces succesful")

        self.logger.info("Start calculating the needed air flow for the buiding")
        # Hier wird die Summe der Luftmengen berechnet
        air_flow_building = self.calc_air_flow_building(thermal_zones)
        self.logger.info(f"Caluclated airflow for building {air_flow_building} succesful")


        if output:
            self.output_to_csv(thermal_zones)

        return instances,

    def ventilation_system(self, thermal_zones, nutzung_ohne_lueftung):
        """Function decides whether ventilation is required

        Args:
            termal_zones: ThermalZone bim2sim element
            nutzung_ohne_lueftung: List
        Returns:
            ventilation_system True or False
        """
        for tz in thermal_zones:
            if tz.usage in nutzung_ohne_lueftung:
                tz.ventilation_system = False
            elif tz.zone_name == "Flur 3.OG Treppe": # So bekommt das 3. OG keine Lüftung!
                tz.ventilation_system = False
            else:
                tz.ventilation_system = True

    def calc_air_flow_zone(self, thermal_zones, nutzung_ohne_lueftung):
        """Function calculates the airflow of one specific zone.

        Args:
            thermal_zones: ThermalZone bim2sim element
        Returns:
            airflow: calculated airflow of the specific zone
        """

        for tz in thermal_zones:
            name = tz.zone_name # Name of the room
            persons_per_square_meter = tz.persons  # persons/m² (data source is din 18599)
            area = tz.net_area # Area of the room
            persons_per_room = math.ceil(persons_per_square_meter * area) # number of people per room, rounded up!

            if tz.usage == "WC and sanitary rooms in non-residential buildings":
                tz.area_air_flow_factor = 3.06 # ASR A4.1
                tz.persons_air_flow_factor = 0
            else:
                tz.area_air_flow_factor = 0.7   # from DIN EN 16798-1:2022-03 table B.7 , Kat II, Schadstoffarmes Gebäude
                tz.persons_air_flow_factor = 7  # from DIN EN 16798-1:2022-03 table B.6, Kat II

            area_airflow = area * tz.area_air_flow_factor
            person_airflow = persons_per_room * tz.persons_air_flow_factor

            if tz.ventilation_system == True:
                tz.air_flow = person_airflow + area_airflow
            elif tz.ventilation_system == False:
                tz.air_flow = 0


    def calc_air_flow_building(self, thermal_zones):
        """Function calculates the airflow of the complete building.

        #TODO Wie soll die Gesamtluftmenge zurückgeben werden???
        Args:
            tz: ThermalZone bim2sim element
        Returns:
            building airflow: calculated airflow of the building
        """
        building_air_flow = 0 * ureg.liter/ureg.second
        for tz in thermal_zones:
            if tz.ventilation_system == True:
                building_air_flow += tz.air_flow
            elif tz.ventilation_system == False:
                building_air_flow += 0

        return building_air_flow


    def output_to_csv(self, thermal_zones):
        luftmengen_df = pd.DataFrame({
            "Raumname": [tz.zone_name for tz in thermal_zones],
            "Deckenkoordinate": [round(tz.space_center.Z() + tz.height.magnitude / 2, 2) for tz in thermal_zones],
            "Nutzungsart": [tz.usage for tz in thermal_zones],
            "Lichte Höhe des Raumes [m]": [tz.height for tz in thermal_zones],
            "Raumvolumen [m³]": [tz.net_volume for tz in thermal_zones],
            "Personenanzahl": [math.ceil(tz.persons * tz.net_area) for tz in thermal_zones],
            "Luftmengenfaktor Person [l/s]": [tz.persons_air_flow_factor for tz in thermal_zones],
            "Grundfläche des Raumes [m²]": [tz.net_area for tz in thermal_zones],
            "Luftmengenfaktor Fläche [l/(s*m²)]": [tz.area_air_flow_factor for tz in thermal_zones],
            "Lüftung erforderlich:": [tz.ventilation_system for tz in thermal_zones],
            "Luftmenge gesamt [l/s]": [tz.air_flow for tz in thermal_zones]
        })

        # Pfad für Speichern
        luftmengen_excel_pfad = self.paths.export / "Luftmengenberechnung.xlsx"

        # Hinzufügen einer neuen Zeile mit Nullen (oder NaNs, je nach Bedarf)
        luftmengen_df.loc['Summe'] = 0

        summe = luftmengen_df['Luftmenge gesamt [l/s]'].sum()

        # Setzen der Summe nur in der gewünschten Spalte
        luftmengen_df.loc['Summe', 'Luftmenge gesamt [l/s]'] = summe

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
