from ebcpy import TimeSeriesData
import pandas as pd
import pint_pandas

from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.units import ureg
from bim2sim.utilities.common_functions import filter_elements

# Important: if these are adjusted, also adjust export_vars in ExportTEASER
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
    # TODO check if the array indexing works correctly
    "multizonePostProcessing.QIntGains_flow[numZones,1]":
        "internal_gains_lights_rooms",
    "multizonePostProcessing.QIntGains_flow[numZones,2]":
        "internal_gains_machines_rooms",
    "multizonePostProcessing.QIntGains_flow[numZones,3]":
        "internal_gains_persons_rooms",
    # TODO calculate by specificPersons*roomArea
    # "multizone.zone[numZones].humanSenHeaDependent.specificPersons *"
    # " multizone.zone[numZones].humanSenHeaDependent.roomArea":
    #     "n_persons_rooms",
    "multizone.zone[numZones].ventCont.y": "infiltration_rooms",
    "multizone.zone[numZones].ventRate": "mech_ventilation_rooms",
    "tableTSet.y[numZones]": "heat_set_rooms",
    "tableTSetCool.y[numZones]": "cool_set_rooms",
    "CPUtime": "cpu_time"
}

# bim2sim_teaser_indirect_mapping = {
#     "n_persons_rooms": [
#         "*",
#         "multizone.zone[numZones].humanSenHeaDependent.specificPersons",
#         "multizone.zone[numZones].humanSenHeaDependent.roomArea"]
# }

pint_pandas.PintType.ureg = ureg
unit_mapping = {
    "heat_demand": ureg.watt,
    "cool_demand": ureg.watt,
    "heat_energy": ureg.joule,
    "cool_energy": ureg.joule,
    "operative_temp": ureg.kelvin,
    "air_temp": ureg.kelvin,
    "infiltration": ureg.hour ** -1,
    "mech_ventilation": ureg.hour ** -1,
    "heat_set": ureg.kelvin,
    "cool_set": ureg.kelvin,
    "internal_gains": ureg.watt,
    "cpu_time": ureg.second
}


class CreateResultDF(ITask):
    """Creates result dataframe, run() method holds detailed information."""

    reads = ('sim_results_path', 'bldg_names', 'elements')
    touches = ('df_finals',)

    def run(self, sim_results_path, bldg_names, elements):
        """Creates a result dataframe for BEPS simulations.

        The created dataframe holds the data for the  generic plot
         functionality for BEPS simulation in `bim2sim` post-processing,
         regardless if the simulation results come from TEASER
        or EnergyPlus. Therefore, the simulation results are mapped into a
        generic form with unified timestamps and only the results wanted,
        defined by the sim_settings, are exported to the dataframe.

        Args:
            teaser_mat_result_paths: path to simulation result file
            bldg_names (list): list of all buildings
            elements: bim2sim elements created based on ifc data
        Returns:
            df_final: final dataframe that holds only relevant data, with
            generic `bim2sim` names and index in form of MM/DD-hh:mm:ss
        """
        if not self.playground.sim_settings.dymola_simulation:
            self.logger.warning("Skipping task CreateResultDF as sim_setting "
                             "'dymola_simulation' is set to False and no "
                             "simulation was performed.")
            return None,
        if not self.playground.sim_settings.create_plots:
            self.logger.warning("Skipping task CreateResultDF as sim_setting "
                                "'create_plots' is set to False and no "
                                "DataFrame ist needed.")
            return None,
                # ToDO handle multiple buildings/ifcs #35
        df_finals = {}
        for bldg_name in bldg_names:
            result_path = sim_results_path / bldg_name / "teaser_results.mat"
            bim2sim_teaser_mapping_selected = self.select_wanted_results()
            # bim2sim_teaser_mapping = self.calc_indirect_result()
            bim2sim_teaser_mapping = self.map_zonal_results(
                bim2sim_teaser_mapping_selected, elements)
            relevant_vars = list(bim2sim_teaser_mapping.keys())
            df_original = TimeSeriesData(
                result_path, variable_names=relevant_vars).to_df()
            df_final = self.format_dataframe(
                df_original, bim2sim_teaser_mapping, relevant_vars)
            df_finals[bldg_name] = df_final
        return df_finals,

    def format_dataframe(
            self, df_original: pd.DataFrame,
            bim2sim_teaser_mapping: dict,
            relevant_vars: list) -> pd.DataFrame:
        """Formats the dataframe to generic bim2sim output structure.

        This function:
         - adds the space GUIDs or bim2sim aggregated room names to the results
         - selects only the selected simulation outputs from the result
         - sets the index to the format MM/DD-hh:mm:ss
         - uses absolute values instead negative ones for cooling

        Args:
            df_original: original dataframe directly taken from simulation
            bim2sim_teaser_mapping: dict[simulation var name:
            relevant_vars: list of simulation variables to have in dataframe

        Returns:
            df_final: converted dataframe in `bim2sim` result structure
        """

        # rename columns based on bim2sim_teaser_mapping
        df_final = df_original.rename(
            columns=bim2sim_teaser_mapping)

        # update index to format MM/DD-hh:mm:ss
        df_final = self.convert_time_index(df_final)

        # make energy consumptions hourly instead cumulated
        for column in df_final.columns:
            if "_energy_" in column:
                df_final[column] = df_final[column].diff()
        df_final.fillna(0, limit=1, inplace=True)

        # convert negative cooling demands and energies to absolute values
        df_final = df_final.abs()

        # handle units
        for column in df_final:
            for key, unit in unit_mapping.items():
                if key in column:
                    df_final[column] = pint_pandas.PintArray(
                        df_final[column], unit)

        return df_final

    def select_wanted_results(self):
        """Selected only the wanted outputs based on sim_setting sim_results"""
        bim2sim_teaser_mapping = bim2sim_teaser_mapping_base.copy()
        for key, value in bim2sim_teaser_mapping_base.items():
            if value not in self.playground.sim_settings.sim_results:
                del bim2sim_teaser_mapping[key]
        return bim2sim_teaser_mapping

    @staticmethod
    def map_zonal_results(bim2sim_teaser_mapping_selected, elements: dict):
        """Add zone/space guids/names to mapping dict.

        Dymola outputs the results just via a counting of zones/rooms
        starting with [1]. This function adds the real zone/space guids or
        aggregation names to the dict for easy readable results.
        Rooms are mapped with their space GUID, aggregated zones are mapped
        with their zone name. Therefore, we load the additional information
        like what spaces are aggregated from elements structure.

        Args:
            bim2sim_teaser_mapping_selected: dict holds the mapping between
             simulation outputs and generic `bim2sim` output names. Only
             outputs selected via sim_results sim-setting are included.
            elements: dict[guid: element]

        Returns:
            dict: A mapping between simulation results and space guids, with
             appropriate adjustments for aggregated zones.

        """
        bim2sim_teaser_mapping = {}
        space_guid_list = []
        agg_tzs = filter_elements(elements, 'AggregatedThermalZone')
        if agg_tzs:
            for agg_tz in agg_tzs:
                space_guid_list.append(agg_tz.guid)
        else:
            tzs = filter_elements(elements, 'ThermalZone')
            for tz in tzs:
                space_guid_list.append(tz.guid)
        for key, value in bim2sim_teaser_mapping_selected.items():
            # add entry for each room/zone
            if "numZones" in key:
                for i, space_guid in enumerate(space_guid_list, 1):
                    new_key = key.replace("numZones", str(i))
                    new_value = value.replace("rooms", "rooms_" + space_guid)
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
        # df.index = pd.date_range(start=f'{year}-01-01', end=f'{year+1}-01-01', freq='H')
        df.index = pd.to_datetime(
            df.index.total_seconds(), unit='s', origin=f'{year}-01-01')
        # TODO remove this in EP as well if correct
        # # Format the date to [mm/dd-hh:mm:ss]
        # df.index = df.index.strftime('%m/%d-%H:%M:%S')

        # delete last value (which is first value of next year) to have 8760
        # time steps
        df = df[:-1]
        return df

    @staticmethod
    def calc_indirect_result(bim2sim_teaser_mapping_selected):
        # TODO
        pass
