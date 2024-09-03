import json

import pandas as pd
import pint_pandas
from pint_pandas import PintArray

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils
from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.units import ureg
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task import CreateResultDF as BPSResultDF

bim2sim_energyplus_mapping_base = {
    "Environment:Site Outdoor Air Drybulb Temperature [C](Hourly)": "site_outdoor_air_temp",
    "SPACEGUID:Zone Operative Temperature [C](Hourly)": "operative_air_temp_rooms",
    "SPACEGUID:Zone Thermal Comfort CEN 15251 Adaptive Model Category I Status [](Hourly)": "cen15251_cat1_status_rooms",
    "SPACEGUID:Zone Thermal Comfort CEN 15251 Adaptive Model Category II Status [](Hourly)": "cen15251_cat2_status_rooms",
    "SPACEGUID:Zone Thermal Comfort CEN 15251 Adaptive Model Category III Status [](Hourly)": "cen15251_cat3_status_rooms",
    "SPACEGUID:Zone Thermal Comfort CEN 15251 Adaptive Model Running Average Outdoor Air Temperature [C](Hourly)": "cen15251_adapt_outdoor_air_temp_rooms",
    "SPACEGUID:Zone Thermal Comfort Fanger Model PMV [](Hourly)":
        "fanger_pmv_rooms",
    "SPACEGUID:Zone Thermal Comfort Fanger Model PPD [%](Hourly)":
        "fanger_ppd_rooms",
}

pint_pandas.PintType.ureg = ureg
unit_mapping = {
    "_status": ureg.dimensionless,
    "air_temp": ureg.degree_Celsius,
}


class CreateResultDF(BPSResultDF):
    """This ITask creates a result dataframe for EnergyPlus Comfort BEPS.

    Args:
        idf: eppy idf
    Returns:
        df_final: final dataframe that holds only relevant data, with generic
        `bim2sim` names and index in form of MM/DD-hh:mm:ss
    """
    reads = ('idf', 'sim_results_path', 'df_finals')
    touches = ('df_finals',)

    def run(self, idf, sim_results_path, df_finals):
        # only create dataframes if plots are requested.
        if not self.playground.sim_settings.create_plots:
            self.logger.warning("Skipping task Comfort CreateResultDF as "
                                "sim_setting 'create_plots' is set to False and "
                                "no DataFrame ist needed.")
            return df_finals,

        raw_csv_path = sim_results_path / self.prj_name / 'eplusout.csv'
        zone_dict_path = sim_results_path / self.prj_name / 'zone_dict.json'
        with open(zone_dict_path) as j:
            zone_dict =json.load(j)

        df_original = PostprocessingUtils.read_csv_and_format_datetime(
            raw_csv_path)
        df_original = PostprocessingUtils.shift_dataframe_to_midnight(df_original)
        df_final = self.format_dataframe(df_original, zone_dict)
        df_finals[self.prj_name] = pd.concat([df_finals[self.prj_name], df_final], axis=1)
        return df_finals,

    def format_dataframe(self, df_original: pd.DataFrame, zone_dict: dict) \
            -> pd.DataFrame:
        """Formats the dataframe to generic bim2sim output structure.

        This function:
         - adds the space GUIDs to the results
         - selects only the selected simulation outputs from the result

        Args:
            df_original: original dataframe directly taken from simulation
            zone_dict: dictionary with all zones, in format {GUID : Zone Usage}

        Returns:
            df_final: converted dataframe in `bim2sim` result structure
        """
        bim2sim_energyplus_mapping = self.map_zonal_results(
            bim2sim_energyplus_mapping_base, zone_dict)
        # select only relevant columns
        short_list = \
            list(bim2sim_energyplus_mapping.keys())
        df_final = df_original[df_original.columns[
            df_original.columns.isin(short_list)]].rename(
            columns=bim2sim_energyplus_mapping)

        # convert negative cooling demands and energies to absolute values
        df_final = df_final.abs()
        # handle units
        for column in df_final:
            for key, unit in unit_mapping.items():
                if key in column:
                    df_final[column] = PintArray(df_final[column], unit)

        return df_final

