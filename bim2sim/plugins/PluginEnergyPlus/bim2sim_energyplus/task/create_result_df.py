import json
from pathlib import Path

import pandas as pd
import pint_pandas
from geomeppy import IDF
from pint_pandas import PintArray

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task import \
    IdfPostprocessing
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils
from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.units import ureg


bim2sim_energyplus_mapping_base = {
    "NOT_AVAILABLE": "heat_demand_total",
    "SPACEGUID IDEAL LOADS AIR SYSTEM:Zone Ideal Loads Zone Total Heating "
    "Rate [W](Hourly)": "heat_demand_rooms",
    "NOT_AVAILABLE": "cool_demand_total",
    "SPACEGUID IDEAL LOADS AIR SYSTEM:Zone Ideal Loads Zone Total Cooling "
    "Rate [W](Hourly)": "cool_demand_rooms",
    "Heating:EnergyTransfer [J](Hourly)": "heat_energy_total",
    "Cooling:EnergyTransfer [J](Hourly) ": "cool_energy_total",
    "SPACEGUID:Zone Total Internal Total Heating Energy [J](Hourly)":
        "heat_energy_rooms",
    "SPACEGUID IDEAL LOADS AIR SYSTEM:Zone Ideal Loads Zone Total Cooling Energy [J](Hourly)":
        "cool_energy_rooms",
    "Environment:Site Outdoor Air Drybulb Temperature [C](Hourly)":
        "air_temp_out",
    "SPACEGUID:Zone Operative Temperature [C](Hourly)":
        "operative_temp_rooms",
    "SPACEGUID:Zone Mean Air Temperature [C](Hourly)": "air_temp_rooms",
    "SPACEGUID:Zone Electric Equipment Total Heating Rate [W](Hourly)": "internal_gains_machines_rooms",
    "SPACEGUID:Zone People Total Heating Rate [W](Hourly)": "internal_gains_persons_rooms",
    "SPACEGUID:Zone People Occupant Count [](Hourly)": "n_persons_rooms",
    "SPACEGUID:Zone Lights Total Heating Rate [W](Hourly)": "internal_gains_lights_rooms",
    "SPACEGUID:Zone Infiltration Air Change Rate [ach](Hourly)": "infiltration_rooms",
    "SPACEGUID:Zone Ventilation Standard Density Volume Flow Rate [m3/s](Hourly)": "mech_ventilation_rooms",
    "SPACEGUID:Zone Thermostat Heating Setpoint Temperature [C](Hourly)": "heat_set_rooms",
    "SPACEGUID:Zone Thermostat Cooling Setpoint Temperature [C](Hourly)": "cool_set_rooms",
}

pint_pandas.PintType.ureg = ureg
unit_mapping = {
    "heat_demand": ureg.watt,
    "cool_demand": ureg.watt,
    "heat_energy": ureg.joule,
    "cool_energy": ureg.joule,
    "operative_temp": ureg.degree_Celsius,
    "air_temp": ureg.degree_Celsius,
    "heat_set": ureg.degree_Celsius,
    "cool_set": ureg.degree_Celsius,
    "internal_gains": ureg.watt,
    "n_persons": ureg.dimensionless,
    "infiltration": ureg.hour**(-1),
    "mech_ventilation": (ureg.meter**3) / ureg.second,
}


class CreateResultDF(ITask):
    """This ITask creates a result dataframe for EnergyPlus BEPS simulations

    See detailed explanation in the run function below.
    """

    reads = ('idf', 'sim_results_path', 'elements')
    touches = ('df_finals',)

    def run(self, idf: IDF, sim_results_path: Path, elements: dict) \
            -> dict[str: pd.DataFrame]:
        """ Create a result DataFrame for EnergyPlus BEPS results.

        This function transforms the EnergyPlus simulation results to the
        general result data format used in this bim2sim project. The
        simulation results stored in the EnergyPlus result file (
        "eplusout.csv") are shifted by one hour to match the simulation
        results of the modelica simulation. Afterwards, the simulation
        results are formatted to match the bim2sim dataframe format.

        Args:
            idf (IDF): eppy idf
            sim_results_path (Path): path to the simulation results from
                EnergyPlus
            elements (dict): dictionary in the format dict[guid: element],
                holds preprocessed elements including space boundaries.
        Returns:
            df_finals (dict): dictionary in the format
            dict[str(project name): pd.DataFrame], final dataframe
            that holds only relevant data, with generic `bim2sim` names and
            index in form of MM/DD-hh:mm:ss

        """
        # ToDO handle multiple buildings/ifcs #35
        df_finals = {}
        if not self.playground.sim_settings.create_plots:
            self.logger.warning("Skipping task CreateResultDF as sim_setting "
                                "'create_plots' is set to False and no "
                                "DataFrame ist needed.")
            return df_finals,
        raw_csv_path = sim_results_path / self.prj_name / 'eplusout.csv'
        # TODO @Veronika: the zone_dict.json can be removed and instead the
        #  elements structure can be used to get the zone guids
        zone_dict_path = sim_results_path / self.prj_name / 'zone_dict.json'
        if not zone_dict_path.exists():
            IdfPostprocessing.write_zone_names(idf, elements,
                                               sim_results_path / self.prj_name)
        with open(zone_dict_path) as j:
            zone_dict =json.load(j)
        df_original = PostprocessingUtils.read_csv_and_format_datetime(
            raw_csv_path)
        df_original = (
            PostprocessingUtils.shift_dataframe_to_midnight(df_original))
        df_final = self.format_dataframe(df_original, zone_dict)
        df_finals[self.prj_name] = df_final

        return df_finals,

    def format_dataframe(
            self, df_original: pd.DataFrame, zone_dict: dict) -> pd.DataFrame:
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
        short_list.remove('NOT_AVAILABLE')
        df_final = df_original[df_original.columns[
            df_original.columns.isin(short_list)]].rename(
            columns=bim2sim_energyplus_mapping)

        # convert negative cooling demands and energies to absolute values
        energy_and_demands = df_final.filter(like='energy').columns.union(
            df_final.filter(like='demand').columns)
        df_final[energy_and_demands].abs()
        heat_demand_columns = df_final.filter(like='heat_demand')
        cool_demand_columns = df_final.filter(like='cool_demand')
        df_final['heat_demand_total'] = heat_demand_columns.sum(axis=1)
        df_final['cool_demand_total'] = cool_demand_columns.sum(axis=1)
        # handle units
        for column in df_final:
            for key, unit in unit_mapping.items():
                if key in column:
                    df_final[column] = PintArray(df_final[column], unit)

        return df_final

    def select_wanted_results(self):
        """Selected only the wanted outputs based on sim_setting sim_results"""
        bim2sim_energyplus_mapping = bim2sim_energyplus_mapping_base.copy()
        for key, value in bim2sim_energyplus_mapping_base.items():
            if value not in self.playground.sim_settings.sim_results:
                del bim2sim_energyplus_mapping[key]
        return bim2sim_energyplus_mapping

    @staticmethod
    def map_zonal_results(bim2sim_energyplus_mapping_base, zone_dict):
        """Add zone/space guids/names to mapping dict.

        EnergyPlus outputs the results referencing to the IFC-GlobalId. This
        function adds the real zone/space guids or
        aggregation names to the dict for easy readable results.
        Rooms are mapped with their space GUID, aggregated zones are mapped
        with their zone name. The mapping between zones and rooms can be taken
        from tz_mapping.json file with can be found in export directory.

        Args:
            bim2sim_energyplus_mapping_base: Holds the mapping between
             simulation outputs and generic `bim2sim` output names.
            zone_dict: dictionary with all zones, in format {GUID : Zone Usage}

        Returns:
            dict: A mapping between simulation results and space guids, with
             appropriate adjustments for aggregated zones.

        """
        bim2sim_energyplus_mapping = {}
        space_guid_list = list(zone_dict.keys())
        for key, value in bim2sim_energyplus_mapping_base.items():
            # add entry for each room/zone
            if "SPACEGUID" in key:
                # TODO write case sensitive GUIDs into dataframe
                for i, space_guid in enumerate(space_guid_list):
                    new_key = key.replace("SPACEGUID", space_guid.upper())
                    # todo: according to #497, names should keep a _zone_ flag
                    new_value = value.replace("rooms", 'rooms_' + space_guid)
                    bim2sim_energyplus_mapping[new_key] = new_value
            else:
                bim2sim_energyplus_mapping[key] = value
        return bim2sim_energyplus_mapping
