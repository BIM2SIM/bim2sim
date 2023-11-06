from ebcpy import TimeSeriesData
import pandas as pd
from pint_pandas import PintArray

from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.units import ureg

bim2sim_teaser_mapping_base = {
    "multizonePostProcessing.PHeaterSum": "heat_demand_total",
    "multizonePostProcessing.PHeater[numZones]": "heat_demand_rooms",
    "multizonePostProcessing.PCoolerSum": "cool_demand_total",
    "multizonePostProcessing.PCooler[numZones]": "cool_demand_rooms",
    "multizonePostProcessing.WHeaterSum": "heat_energy_total",
    "multizonePostProcessing.WCoolerSum": "cool_energy_total",
    "multizonePostProcessing.WHeater[numZones].y": "heat_energy_rooms",
    "multizonePostProcessing.WCooler[numZones].y": "cool_energy_rooms",
    "weaDat.weaBus.TDryBul": "air_temp_out",
    "multizonePostProcessing.TOperativeAverageCalc.u[numZones]":
        "operative_temp_rooms",
    "multizonePostProcessing.TAir[numZones]": "air_temp_rooms",
}

unit_mapping = {
    "heat_demand": ureg.watt,
    "cool_demand": ureg.watt,
    "heat_energy": ureg.joule,
    "cool_energy": ureg.joule,
    "operative_temp": ureg.kelvin,
    "air_temp": ureg.kelvin,
}


class CreateResultDF(ITask):
    """This ITask creates a result dataframe for TEASER BEPS simulations.

    Args:
        teaser_mat_result_paths: path to simulation result file
        tz_mapping: dict with mapping between IFC space GUIDs and rooms/zones
    Returns:
        df_final: final dataframe that holds only relevant data, with generic
        `bim2sim` names and index in form of MM/DD-hh:mm:ss
    """
    reads = ('teaser_mat_result_paths', 'sim_results_path',
             'tz_mapping')
    touches = ('df_finals',)

    def run(self, teaser_mat_result_paths, sim_results_path,
            tz_mapping):
        # ToDO handle multiple buildings/ifcs #35
        df_finals = {}
        for bldg_name, result_path in teaser_mat_result_paths.items():
            df_original = TimeSeriesData(result_path).to_df()
            df_final = self.format_dataframe(df_original, tz_mapping)
            df_finals[bldg_name] = df_final
        return df_finals,

    def format_dataframe(
            self, df_original: pd.DataFrame, tz_mapping: dict) -> pd.DataFrame:
        """Formats the dataframe to generic bim2sim output structure.

        This function:
         - adds the space GUIDs or bim2sim aggreated room names to the results
         - selects only the selected simulation outputs from the result
         - sets the index to the format MM/DD-hh:mm:ss
         - uses absolute values instead negative ones for cooling

        Args:
            df_original: original dataframe directly taken from simulation
            tz_mapping:

        Returns:
            df_final: converted dataframe in `bim2sim` result structure
        """
        bim2sim_teaser_mapping_selected = self.select_wanted_results()
        bim2sim_teaser_mapping = self.map_zonal_results(
            tz_mapping, bim2sim_teaser_mapping_selected)

        # select only relevant columns
        df_final = df_original.loc[
                   :, list(bim2sim_teaser_mapping.keys())].rename(
            columns=bim2sim_teaser_mapping)

        # update index to format MM/DD-hh:mm:ss
        df_final = self.convert_time_index(df_final)

        # convert negative cooling demands and energies to absolute values
        df_final = df_final.abs()

        # handle units
        for column in df_final:
            for key, unit in unit_mapping.items():
                if key in column:
                    df_final[column] = PintArray(df_final[column], unit)

        return df_final

    def select_wanted_results(self):
        """Selected only the wanted outputs based on sim_setting sim_results"""
        bim2sim_teaser_mapping = bim2sim_teaser_mapping_base.copy()
        for key, value in bim2sim_teaser_mapping_base.items():
            if value not in self.playground.sim_settings.sim_results:
                del bim2sim_teaser_mapping[key]
        return bim2sim_teaser_mapping

    @staticmethod
    def map_zonal_results(tz_mapping, bim2sim_teaser_mapping_selected):
        """Add zone/space guids/names to mapping dict.

        Dymola outputs the results just via a counting of zones/rooms
        starting with [1]. This function adds the real zone/space guids or
        aggregation names to the dict for easy readable results.
        Rooms are mapped with their space GUID, aggregated zones are mapped
        with their zone name. The mapping between zones and rooms can be taken
        from tz_mapping.json file with can be found in export directory.

        Args:
            tz_mapping (dict): A dictionary containing mapping information
             for simulation results and space guids.
            bim2sim_teaser_mapping_selected: Holds the mapping between
             simulation outputs and generic `bim2sim` output names. Only
             outputs selected via sim_results sim-setting are included.

        Returns:
            dict: A mapping between simulation results and space guids, with
             appropriate adjustments for aggregated zones.

        """
        bim2sim_teaser_mapping = {}
        space_guid_list = []
        for key, value in tz_mapping.items():
            if not value["aggregated"]:
                space_guid_list.append(value["space_guids"][0])
            else:
                space_guid_list.append(key.split('_')[-1])
        for key, value in bim2sim_teaser_mapping_selected.items():
            # add entry for each room/zone
            if "numZones" in key:
                for i, space_guid in enumerate(space_guid_list, 1):
                    new_key = key.replace("numZones", str(i))
                    new_value = value.replace("rooms", space_guid)
                    bim2sim_teaser_mapping[new_key] = new_value
            else:
                bim2sim_teaser_mapping[key] = value
        return bim2sim_teaser_mapping

    @staticmethod
    def convert_time_index(df):
        """This converts the index of the result df to "days hh:mm:ss format"""
        # Convert the index to a timedelta object
        df.index = pd.to_timedelta(df.index, unit='s')
        # handle leap years
        if len(df.index) > 8761:
            year = 2020
        else:
            year = 2021
        # Add the specified year to the date
        df.index = pd.to_datetime(
            df.index.total_seconds(), unit='s', origin=f'{year}-01-01')

        # Format the date to [mm/dd-hh:mm:ss]
        df.index = df.index.strftime('%m/%d-%H:%M:%S')

        # delete last value (which is first value of next year) to have 8760
        # time steps
        df = df[:-1]
        return df
