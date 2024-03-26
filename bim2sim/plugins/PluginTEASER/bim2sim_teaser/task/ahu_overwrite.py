from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
import pandas as pd
from pint import UnitRegistry

class OverwriteAHU(ITask):
    reads = ('elements',)

    def run(self, elements):
        tz_list = filter_elements(elements, 'ThermalZone')
        # read your csv
        # Path to the Excel file
        filepath = r"C:\Users\svenh\AppData\Local\Temp\bim2sim_example_lca_2qzl7wtys\export\Air volume calculation.xlsx"

        # Read the Excel file into a DataFrame
        df_air_volume = pd.read_excel(filepath)
        ureg = UnitRegistry()


        for tz in tz_list:
            # e.g. set AHU to True for all zones
            line = df_air_volume[df_air_volume['GUID'] == tz.guid]
            print(line["Ventilation required:"].iloc[0])
            print(type(line["Ventilation required:"].iloc[0]))

            air_volume = ureg(line["Total air volume"].iloc[0]).magnitude

            if int(line["Ventilation required:"].iloc[0]) == 1:
                tz.min_ahu = air_volume/1000
                tz.max_ahu = air_volume/1000
                # tz.central_ahu = True
                tz.with_ahu = True
                tz.natural_ventilation = False
            else:
                tz.min_ahu = 0
                tz.max_ahu = 0
                tz.with_ahu = True
                # tz.central_ahu = True
                tz.natural_ventilation = True
