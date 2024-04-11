from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
import pandas as pd
from pint import UnitRegistry
from bim2sim.elements.mapping.units import ureg

class OverwriteAHU(ITask):
    reads = ('elements',)

    def run(self, elements):
        tz_list = filter_elements(elements, 'ThermalZone')
        bldgs = filter_elements(elements, 'Building')
        # read your csv
        # Path to the Excel file
        filepath = r"D:\OneDrive - Students RWTH Aachen University\0 UNI\Masterarbeit\Air volume calculation.xlsx"
        # filepath = r"D:/01_Kurzablage/MA_Hartmann/Air volume calculation.xlsx"

        # Read the Excel file into a DataFrame
        df_air_volume = pd.read_excel(filepath)

        # active central ahu in all buildings
        for bldg in bldgs:
            bldg.with_ahu = True


        for tz in tz_list:
            # e.g. set AHU to True for all zones
            line = df_air_volume[df_air_volume['GUID'] == tz.guid]
            air_volume = ureg(line["Total air volume"].iloc[0]).to('m**3/hour')

            if int(line["Ventilation required:"].iloc[0]) == 1:
                # TODO this should be correct, but please test this again @sven
                # correct unit is m³ / m² / h
                # in liter ??? warum ist das so? macht keinen Sinn

                if (line["Type of use"].iloc[0] == "Group Office (between 2 and 6 employees)" or
                        line["Type of use"].iloc[0] == "Single Office" or
                        line["Type of use"].iloc[0] == "Meeting, Conference, Seminar"):

                    # For AHU
                    tz.with_ahu = True
                    tz.min_ahu = 0 # air_volume / tz.net_area
                    tz.max_ahu = air_volume / tz.net_area * 3600 # * 0.8

                else:
                    # For AHU
                    tz.with_ahu = True
                    tz.min_ahu = 0  # air_volume / tz.net_area
                    tz.max_ahu = air_volume / tz.net_area * 3600

                    # tz.central_ahu = True
                    # tz.with_ahu = True
                    # tz.natural_ventilation = False
                    tz.natural_ventilation = True
            else:
                tz.min_ahu = 0
                tz.max_ahu = 0
                tz.natural_ventilation = True

                # # For Fensterlüftung
                # tz.natural_ventilation = True
                # tz.max_user_infiltration = air_volume / tz.gross_volume * 3600
