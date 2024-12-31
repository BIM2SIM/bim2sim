import json
import logging
from pathlib import Path
from typing import List

import matplotlib as mpl
import numpy as np
import pandas as pd
from RWTHColors import ColorManager
from matplotlib import pyplot as plt
from matplotlib.colors import ListedColormap, Normalize

from bim2sim.tasks.bps import PlotBEPSResults
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import BoundaryOrientation

INCH = 2.54

logger = logging.getLogger(__name__)
cm = ColorManager()
plt.rcParams.update(mpl.rcParamsDefault)
plt.style.use(['science', 'grid', 'rwth'])
plt.style.use(['science', 'no-latex'])

# Update rcParams for font settings
plt.rcParams.update({
    'font.size': 20,
    'font.family': 'sans-serif',  # Use sans-serif font
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans', 'sans-serif'],
    # Specify sans-serif fonts
    'legend.frameon': True,
    'legend.facecolor': 'white',
    'legend.framealpha': 0.5,
    'legend.edgecolor': 'black',
    "lines.linewidth": 0.4,
    "text.usetex": False,  # use inline math for ticks
    "pgf.rcfonts": True,
})


class PlotComfortResults(PlotBEPSResults):
    reads = ('df_finals', 'sim_results_path', 'ifc_files', 'elements')
    final = True

    def run(self, df_finals: dict, sim_results_path: Path,
            ifc_files: List[Path], elements: dict):
        """Plots the results for BEPS simulations.

         This holds pre configured functions to plot the results of the BEPS
         simulations with the EnergyPlus-based PluginComfort .

         Args:
             df_finals: dict of final results where key is the building name and
              value is the dataframe holding the results for this building
             sim_results_path: base path where to store the plots
             ifc_files: bim2sim IfcFileClass holding the ifcopenshell ifc instance
             elements (dict): Dictionary of building elements.
         """
        if not self.playground.sim_settings.create_plots:
            logger.info("Visualization of Comfort Results is skipped ...")
            return
        logger.info("Visualization of Comfort Results started ...")
        plot_single_guid = self.playground.sim_settings.plot_singe_zone_guid

        zone_dict_path = sim_results_path / self.prj_name / 'zone_dict.json'
        with open(zone_dict_path) as j:
            zone_dict = json.load(j)
        if plot_single_guid:
            logger.info("Check if plot_single_guid is valid space name.")
            if not plot_single_guid in zone_dict.keys():
                plot_single_guid = ''
                logger.info("Requested plot_single_guid is not found in IFC "
                            "file, plotting results for all spaces instead.")
        if self.playground.sim_settings.rename_plot_keys:
            with open(self.playground.sim_settings.rename_plot_keys_path) as rk:
                rename_keys = json.load(rk)
            zone_dict = self.rename_zone_usage(zone_dict, rename_keys)

        for bldg_name, df in df_finals.items():
            export_path = sim_results_path / bldg_name / 'plots'
            if not export_path.exists():
                export_path.mkdir(parents=False, exist_ok=False)
            # generate DIN EN 16798-1 adaptive comfort scatter plot and
            # return analysis of comfort categories for further plots
            self.limited_local_comfort_DIN16798_NA(df, elements, export_path)

            if not plot_single_guid:
                cat_analysis, cat_analysis_occ, cat_analysis_occ_hours = (
                    self.apply_en16798_to_all_zones(df, zone_dict,
                                                    export_path))
            else:
                cat_analysis, cat_analysis_occ, cat_analysis_occ_hours = (
                    self.apply_en16798_to_single_zone(df, zone_dict,
                                                      export_path,
                                                      plot_single_guid))
            # plot a barplot combined with table of comfort categories from
            # DIN EN 16798.
            self.table_bar_plot_16798(cat_analysis, export_path)
            self.table_bar_plot_16798(cat_analysis_occ, export_path, tag='occ')
            self.table_bar_plot_16798(cat_analysis_occ_hours, export_path,
                                      tag='occ_hours', normalize=False,
                                      unit=u'degree hours', y_scale='log')

            fanger_pmv = df[[col for col in df.columns if 'fanger_pmv' in col]]
            if plot_single_guid:
                fanger_pmv = fanger_pmv[[col for col in fanger_pmv.columns if
                                         plot_single_guid in col]]
                self.pmv_plot(fanger_pmv, export_path,
                              f"pmv_{plot_single_guid}")
            for col in fanger_pmv.columns:
                # generate calendar plot for daily mean pmv results
                self.visualize_calendar(pd.DataFrame(fanger_pmv[col]),
                                        export_path, save_as='calendar_',
                                        add_title=True,
                                        color_only=True, figsize=[11, 12],
                                        zone_dict=zone_dict)

    def limited_local_comfort_DIN16798_NA(self, df, elements, export_path,
                                          occupied=True):
        spaces = filter_elements(elements, 'ThermalZone')
        local_discomfort_dict = {}
        local_discomfort_overview = pd.DataFrame(columns=['space',
                                                          'wall_min',
                                                          'wall_max',
                                                          'floor_min',
                                                          'floor_max',
                                                          'ceiling_min',
                                                          'ceiling_max'])
        initial_row = {col: True for col in local_discomfort_overview.columns if
                       col != 'space'}

        for space in spaces:
            self.logger.info(f"Space: {space.usage}, GUID: {space.guid}")
            local_discomfort_dict.update({
                space.guid:
                    {
                        'wall': {'min': {'count': 0,
                                         'hours': 0},
                                 'max': {'count': 0,
                                         'hours': 0}},
                        'floor': {'min': {'count': 0,
                                          'hours': 0},
                                  'max': {'count': 0,
                                          'hours': 0}},
                        'ceiling':
                            {'min': {'count': 0,
                                     'hours': 0},
                             'max': {'count': 0,
                                     'hours': 0}},
                    }})
            new_row = {**initial_row, 'space': space.guid}
            local_discomfort_overview = pd.concat(
                [local_discomfort_overview, pd.DataFrame([new_row])],
                ignore_index=True)
            space_temperature = df[f"air_temp_rooms_{space.guid}"].apply(
                lambda x: x.magnitude)
            if occupied:
                n_persons_df = df['n_persons_rooms_' + space.guid]
                common_index = space_temperature.index.intersection(
                    n_persons_df.index)
                space_temperature = space_temperature.loc[common_index][
                    n_persons_df.loc[common_index] > 0]
            wall_df = pd.DataFrame()
            floor_df = pd.DataFrame()
            ceiling_df = pd.DataFrame()

            for bound in space.space_boundaries:
                bound_temperature = df.filter(like=bound.guid)
                if bound_temperature.empty or bound.bound_element is None:
                    continue
                try:
                    bound_temperature = bound_temperature.iloc[:, 0].apply(
                        lambda x: x.magnitude)
                except AttributeError:
                    self.logger.warning(f"object has no attribute 'magnitude'")
                if occupied:
                    common_index = bound_temperature.index.intersection(
                        n_persons_df.index)
                    bound_temperature = bound_temperature.loc[common_index][
                        n_persons_df.loc[common_index] > 0]
                if 'WALL' in bound.bound_element.key.upper():
                    wall_df = pd.concat([wall_df, bound_temperature], axis=1)
                if (('FLOOR' in bound.bound_element.key.upper() and
                     bound.top_bottom == BoundaryOrientation.top) or
                        ('ROOF' in bound.bound_element.key.upper())):
                    ceiling_df = pd.concat([ceiling_df, bound_temperature],
                                           axis=1)
                if ('FLOOR' in bound.bound_element.key.upper()
                        and bound.top_bottom == BoundaryOrientation.bottom):
                    floor_df = pd.concat([floor_df, bound_temperature], axis=1)
            min_wall_df, max_wall_df = self.get_exceeded_temperature_hours(
                wall_df,
                10, 23,
                space_temperature)
            min_floor_df, max_floor_df = self.get_exceeded_temperature_hours(
                floor_df, 19,
                29, 0)
            min_ceiling_df, max_ceiling_df = (
                self.get_exceeded_temperature_hours(
                    ceiling_df,
                    14,
                    5, space_temperature))
            if not min_wall_df.empty:
                num_min_wall, hours_min_wall = (
                    self.calc_exceeded_temperature_hours(
                        min_wall_df, space_temperature, 10))
                local_discomfort_dict.update({space.guid: {
                    'wall': {'min': {'count': num_min_wall,
                                     'hours': hours_min_wall}}}})
                local_discomfort_overview.iloc[
                    -1, local_discomfort_overview.columns.get_loc(
                        'wall_min')] = False
            if not max_wall_df.empty:
                num_max_wall, hours_max_wall = (
                    self.calc_exceeded_temperature_hours(
                        max_wall_df, space_temperature, 23))
                local_discomfort_dict.update({space.guid: {
                    'wall': {'max': {'count': num_max_wall,
                                     'hours': num_max_wall}}}})
                local_discomfort_overview.iloc[
                    -1, local_discomfort_overview.columns.get_loc(
                        'wall_max')] = False
            if not min_floor_df.empty:
                num_min_floor, hours_min_floor = (
                    self.calc_exceeded_temperature_hours(
                        min_floor_df, 0, 19))
                local_discomfort_dict.update({space.guid: {
                    'floor': {'min': {'count': num_min_floor,
                                      'hours': hours_min_floor}}}})
                local_discomfort_overview.iloc[
                    -1, local_discomfort_overview.columns.get_loc(
                        'floor_min')] = False
            if not max_floor_df.empty:
                num_max_floor, hours_max_floor = (
                    self.calc_exceeded_temperature_hours(
                        max_floor_df, 0, 29))
                local_discomfort_dict.update({space.guid: {
                    'floor': {'max': {'count': num_max_floor,
                                      'hours': hours_max_floor}}}})
                local_discomfort_overview.iloc[
                    -1, local_discomfort_overview.columns.get_loc(
                        'floor_max')] = False
            if not min_ceiling_df.empty:
                num_min_ceiling, hours_min_ceiling = (
                    self.calc_exceeded_temperature_hours(
                        min_ceiling_df, 0, 14))
                local_discomfort_dict.update({space.guid: {
                    'ceiling': {'min': {'count': num_min_ceiling,
                                        'hours': hours_min_ceiling}}}})
                local_discomfort_overview.iloc[
                    -1, local_discomfort_overview.columns.get_loc(
                        'ceiling_min')] = False
            if not max_ceiling_df.empty:
                num_max_ceiling, hours_max_ceiling = (
                    self.calc_exceeded_temperature_hours(
                        max_ceiling_df, 0, 5))
                local_discomfort_dict.update({space.guid: {
                    'ceiling': {'max': {'count': num_max_ceiling,
                                        'hours': hours_max_ceiling}}}})
                local_discomfort_overview.iloc[
                    -1, local_discomfort_overview.columns.get_loc(
                        'ceiling_max')] = False
            last_row_values = local_discomfort_overview.iloc[-1]
            all_true_except_space = all(
                last_row_values[col] for col in last_row_values.index if
                col != 'space')
            if all_true_except_space:
                self.logger.info(f'DIN EN 16798-1 NA (GER), '
                                 f'limited local comfort check passed for space '
                                 f'usage "{space.usage}" with '
                                 f'guid "{space.guid}". ')
            else:
                self.logger.warning(f'DIN EN 16798-1 NA (GER), limited local '
                                    f'comfort check FAILED for space usage '
                                    f'"{space.usage}" with '
                                    f'guid "{space.guid}". Please check '
                                    f'beps_local_discomfort.json for details.')
        with open(export_path / 'beps_local_discomfort.json', 'w+') as file:
            json.dump(local_discomfort_dict, file, indent=4)
        local_discomfort_overview.to_csv(
            export_path / 'local_discomfort_overview.csv')

    def calc_exceeded_temperature_hours(self, df, reference, limit):
        value_over_reference = abs(df.sub(reference, axis=0).dropna()) - limit
        return len(value_over_reference), value_over_reference.values.sum()

    def get_exceeded_temperature_hours(self, df, min_limit, max_limit,
                                       ref_value):
        df_min = pd.DataFrame()
        df_max = pd.DataFrame()
        array = df.values
        mask_max = df.sub(ref_value, axis=0) > max_limit
        if mask_max.values.any():
            filtered_array = np.where(mask_max, array, np.nan)
            max_values = []
            for row in filtered_array:
                if not np.isnan(row).all():
                    max_values.append(np.nanmax(row))
                else:
                    max_values.append(np.nan)
            max_values = np.array(max_values)
            max_indices = np.where(~np.isnan(max_values))[0]
            df_max = pd.DataFrame(max_values[max_indices],
                                  index=df.index[max_indices],
                                  columns=['MaxValue'])
        mask_min = df.sub(ref_value, axis=0) < -min_limit
        if mask_min.values.any():
            filtered_array = np.where(mask_min, array, np.nan)
            min_values = []
            for row in filtered_array:
                if not np.isnan(row).all():
                    min_values.append(np.nanmin(row))
                else:
                    min_values.append(np.nan)
            min_values = np.array(min_values)
            min_indices = np.where(~np.isnan(min_values))[0]
            df_min = pd.DataFrame(min_values[min_indices],
                                  index=df.index[min_indices],
                                  columns=['MinValue'])

        return df_min, df_max

    @staticmethod
    def rename_duplicates(dictionary):
        value_counts = {}
        renamed_dict = {}
        for key, value in dictionary.items():
            if value in value_counts:
                value_counts[value] += 1
                new_value = f"{value}_{value_counts[value]}"
            else:
                value_counts[value] = 1
                new_value = value

            renamed_dict[key] = new_value
        return renamed_dict

    def rename_zone_usage(self, zone_dict, rename_keys):
        for key in zone_dict.keys():
            for key2 in rename_keys.keys():
                if zone_dict[key] == key2:
                    zone_dict[key] = rename_keys[key2]
        zone_usage = self.rename_duplicates(zone_dict)
        return zone_usage

    @staticmethod
    def pmv_plot(df, save_path, file_name):
        PlotBEPSResults.plot_dataframe(df, save_path=save_path,
                                       file_name=file_name,
                                       x_axis_title="Date",
                                       y_axis_title="PMV")

    def apply_en16798_to_all_zones(self, df, zone_dict, export_path,
                                   use_NA=True):
        """Generate EN 16798 diagrams for all thermal zones.

        """
        if use_NA:
            add_NA_str = ' NA (GER)'
        else:
            add_NA_str = ''
        logger.info(f"Plot DIN EN 16798{add_NA_str} diagrams for all zones ...")

        cat_analysis = pd.DataFrame()
        cat_analysis_occ = pd.DataFrame()
        cat_analysis_occ_hours = pd.DataFrame()
        for guid, room_name in zone_dict.items():
            temp_cat_analysis = None
            temp_cat_analysis_occ = None
            temp_cat_analysis_occ_hours = None
            if use_NA:
                (temp_cat_analysis, temp_cat_analysis_occ,
                 temp_cat_analysis_occ_hours) = (
                    self.plot_en16798_adaptive_count_NA(
                        df, guid, room_name + '_' + guid, export_path))
                cat_analysis_occ_hours = pd.concat([cat_analysis_occ_hours,
                                                    temp_cat_analysis_occ_hours])
            else:
                temp_cat_analysis, temp_cat_analysis_occ = (
                    self.plot_new_en16798_adaptive_count(
                        df, guid, room_name + '_' + guid, export_path))
            cat_analysis = pd.concat([cat_analysis, temp_cat_analysis])
            cat_analysis_occ = pd.concat([cat_analysis_occ,
                                          temp_cat_analysis_occ])
        return cat_analysis, cat_analysis_occ, cat_analysis_occ_hours

    def apply_en16798_to_single_zone(self, df, zone_dict, export_path,
                                     zone_guid, use_NA=True):
        if use_NA:
            add_NA_str = ' NA (GER)'
        else:
            add_NA_str = ''

        logger.info(f"Plot DIN EN 16798{add_NA_str} diagram "
                    f"for zone {zone_guid} ...")

        cat_analysis = pd.DataFrame()
        cat_analysis_occ = pd.DataFrame()
        cat_analysis_occ_hours = pd.DataFrame()
        for guid, room_name in zone_dict.items():
            if not guid == zone_guid:
                continue
            temp_cat_analysis = None
            temp_cat_analysis_occ = None
            if use_NA:
                (temp_cat_analysis, temp_cat_analysis_occ,
                 temp_cat_analysis_occ_hours) = (
                    self.plot_en16798_adaptive_count_NA(df, guid,
                                                        room_name + '_' + guid,
                                                        export_path))
                cat_analysis_occ_hours = pd.concat([cat_analysis_occ_hours,
                                                    temp_cat_analysis_occ_hours])
            else:
                temp_cat_analysis, temp_cat_analysis_occ = (
                    self.plot_new_en16798_adaptive_count(df, guid, room_name
                                                         + '_' + guid,
                                                         export_path))
            cat_analysis = pd.concat([cat_analysis, temp_cat_analysis])
            cat_analysis_occ = pd.concat(
                [cat_analysis_occ, temp_cat_analysis_occ])
        return cat_analysis, cat_analysis_occ, cat_analysis_occ_hours

    @staticmethod
    def plot_new_en16798_adaptive_count(df, guid, room_name, export_path):
        """Plot EN 16798 diagram for thermal comfort categories for a single
        thermal zone.

        """
        logger.info(f"Plot DIN EN 16798 diagrams for zone {guid}: {room_name}.")

        def is_within_thresholds_cat1_16798(row):
            if 10 <= row.iloc[0] <= 30:
                y_threshold1 = 0.33 * row.iloc[0] + 18.8 - 3
                y_threshold2 = 0.33 * row.iloc[0] + 18.8 + 2
                return y_threshold1 <= row.iloc[1] <= y_threshold2
            else:
                return False

        def is_within_thresholds_cat2_16798(row):
            if 10 <= row.iloc[0] <= 30:
                y_threshold1a = 0.33 * row.iloc[0] + 18.8 - 4
                y_threshold1b = 0.33 * row.iloc[0] + 18.8 - 3
                y_threshold2a = 0.33 * row.iloc[0] + 18.8 + 2
                y_threshold2b = 0.33 * row.iloc[0] + 18.8 + 3
                return any([y_threshold1a <= row.iloc[1] <= y_threshold1b,
                            y_threshold2a <= row.iloc[1] <= y_threshold2b])
            else:
                return False

        def is_within_thresholds_cat3_16798(row):
            if 10 <= row.iloc[0] <= 30:
                y_threshold1a = 0.33 * row.iloc[0] + 18.8 - 5
                y_threshold1b = 0.33 * row.iloc[0] + 18.8 - 4
                y_threshold2a = 0.33 * row.iloc[0] + 18.8 + 3
                y_threshold2b = 0.33 * row.iloc[0] + 18.8 + 4
                return any([y_threshold1a <= row.iloc[1] <= y_threshold1b,
                            y_threshold2a <= row.iloc[1] <= y_threshold2b])
            else:
                return False

        def is_outside_thresholds_16798(row):
            if 10 <= row.iloc[0] <= 30:
                y_threshold1 = 0.33 * row.iloc[0] + 18.8 - 5
                y_threshold2 = 0.33 * row.iloc[0] + 18.8 + 4
                return any([y_threshold1 >= row.iloc[1], y_threshold2
                            <= row.iloc[1]])
            else:
                return False

        def plot_scatter_en16798(cat1_df, cat2_df, cat3_df, out_df,
                                 path, name):
            plt.figure(figsize=(13.2 / INCH, 8.3 / INCH))

            plt.scatter(cat1_df.iloc[:, 0],
                        cat1_df.iloc[:, 1],
                        s=0.1,
                        color='green', marker=".")
            plt.scatter(cat2_df.iloc[:, 0],
                        cat2_df.iloc[:, 1],
                        s=0.1,
                        color='orange', marker=".")
            plt.scatter(cat3_df.iloc[:, 0],
                        cat3_df.iloc[:, 1],
                        s=0.1,
                        color='red', marker=".")
            plt.scatter(out_df.iloc[:, 0],
                        out_df.iloc[:, 1],
                        s=0.1, color='blue', label='OUT OF RANGE', marker=".")
            coord_cat1_low = [[10, 0.33 * 10 + 18.8 - 3.0],
                              [30, 0.33 * 30 + 18.8 - 3.0]]
            coord_cat1_up = [[10, 0.33 * 10 + 18.8 + 2.0],
                             [30, 0.33 * 30 + 18.8 + 2.0]]
            cc1lx, cc1ly = zip(*coord_cat1_low)
            cc1ux, cc1uy = zip(*coord_cat1_up)
            plt.plot(cc1lx, cc1ly, linestyle='dashed', color='green',
                     label='DIN EN 16798-1: Thresholds Category I')
            plt.plot(cc1ux, cc1uy, linestyle='dashed', color='green')
            coord_cat2_low = [[10, 0.33 * 10 + 18.8 - 4.0],
                              [30, 0.33 * 30 + 18.8 - 4.0]]
            coord_cat2_up = [[10, 0.33 * 10 + 18.8 + 3.0],
                             [30, 0.33 * 30 + 18.8 + 3.0]]
            cc2lx, cc2ly = zip(*coord_cat2_low)
            cc2ux, cc2uy = zip(*coord_cat2_up)
            plt.plot(cc2lx, cc2ly, linestyle='dashed', color='orange',
                     label='DIN EN 16798-1: Thresholds Category II')
            plt.plot(cc2ux, cc2uy, linestyle='dashed', color='orange')

            coord_cat3_low = [[10, 0.33 * 10 + 18.8 - 5.0],
                              [30, 0.33 * 30 + 18.8 - 5.0]]
            coord_cat3_up = [[10, 0.33 * 10 + 18.8 + 4.0],
                             [30, 0.33 * 30 + 18.8 + 4.0]]
            cc3lx, cc3ly = zip(*coord_cat3_low)
            cc3ux, cc3uy = zip(*coord_cat3_up)
            plt.plot(cc3lx, cc3ly, linestyle='dashed', color='red',
                     label='DIN EN 16798-1: Thresholds Category III')
            plt.plot(cc3ux, cc3uy, linestyle='dashed', color='red')

            # Customize plot
            plt.xlabel('Running Mean Outdoor Temperature (\u00B0C)',
                       fontsize=8)
            plt.ylabel('Operative Temperature (\u00B0C)', fontsize=8)
            plt.xlim([lim_min, lim_max])
            plt.ylim([16.5, 35.5])
            plt.grid()
            lgnd = plt.legend(loc="upper left", scatterpoints=1, fontsize=8)
            plt.savefig(
                path / str('DIN_EN_16798_new_' + name + '.pdf'))

        lim_min = 10
        lim_max = 30

        ot = df['operative_air_temp_rooms_' + guid]
        out_temp = df['site_outdoor_air_temp']
        n_persons_df = df['n_persons_rooms_' + guid]

        merged_df = pd.merge(out_temp, ot, left_index=True, right_index=True)
        merged_df = merged_df.map(lambda x: x.m)
        filtered_df_cat1 = merged_df[
            merged_df.apply(is_within_thresholds_cat1_16798,
                            axis=1)]
        filtered_df_cat2 = merged_df[
            merged_df.apply(is_within_thresholds_cat2_16798,
                            axis=1)]
        filtered_df_cat3 = merged_df[
            merged_df.apply(is_within_thresholds_cat3_16798,
                            axis=1)]
        filtered_df_outside = merged_df[
            merged_df.apply(is_outside_thresholds_16798,
                            axis=1)]
        common_index_c1 = filtered_df_cat1.index.intersection(
            n_persons_df.index)
        common_index_c2 = filtered_df_cat2.index.intersection(
            n_persons_df.index)
        common_index_c3 = filtered_df_cat3.index.intersection(
            n_persons_df.index)
        common_index_out = filtered_df_outside.index.intersection(
            n_persons_df.index)

        filter_occ_cat1 = filtered_df_cat1.loc[common_index_c1][
            n_persons_df.loc[common_index_c1] > 0]
        filter_occ_cat2 = filtered_df_cat2.loc[common_index_c2][
            n_persons_df.loc[common_index_c2] > 0]
        filter_occ_cat3 = filtered_df_cat3.loc[common_index_c3][
            n_persons_df.loc[common_index_c3] > 0]
        filter_occ_out = filtered_df_outside.loc[common_index_out][
            n_persons_df.loc[common_index_out] > 0]
        cat_analysis_dict = {
            'ROOM': room_name,
            'CAT1': len(filtered_df_cat1),
            'CAT2': len(filtered_df_cat2),
            'CAT3': len(filtered_df_cat3),
            'OUT': len(filtered_df_outside)
        }
        cat_analysis_df = pd.DataFrame(cat_analysis_dict, index=[0])
        cat_analysis_occ_dict = {
            'ROOM': room_name,
            'CAT1': len(filter_occ_cat1),
            'CAT2': len(filter_occ_cat2),
            'CAT3': len(filter_occ_cat3),
            'OUT': len(filter_occ_out)
        }
        cat_analysis_occ_df = pd.DataFrame(cat_analysis_occ_dict, index=[0])

        analysis_file = export_path / 'DIN_EN_16798_analysis.csv'
        cat_analysis_df.to_csv(analysis_file, mode='a+', header=False, sep=';')
        analysis_occ_file = export_path / 'DIN_EN_16798_analysis_occ.csv'
        cat_analysis_occ_df.to_csv(analysis_occ_file, mode='a+', header=False,
                                   sep=';')

        plot_scatter_en16798(filtered_df_cat1, filtered_df_cat2,
                             filtered_df_cat3, filtered_df_outside,
                             export_path, room_name)
        plot_scatter_en16798(filter_occ_cat1, filter_occ_cat2, filter_occ_cat3,
                             filtered_df_outside, export_path,
                             room_name + '_occupancy')
        return cat_analysis_df, cat_analysis_occ_df

    def plot_en16798_adaptive_count_NA(self, df, guid, room_name, export_path):
        """Plot EN 16798 German National Appendix for a single thermal zone. """
        logger.info(f"Plot DIN EN 16798 diagram (NA) for zone {guid}:"
                    f" {room_name}.")

        def is_within_thresholds_16798_NA(row, calc_K_hours=False):
            if 16 <= row.iloc[0] <= 32:
                y_threshold1 = 18 + 0.25 * row.iloc[0] - 2
                y_threshold2 = 18 + 0.25 * row.iloc[0] + 2
            elif row.iloc[0] > 32:
                y_threshold1 = 26 - 2
                y_threshold2 = 26 + 2
            elif row.iloc[0] < 16:
                y_threshold1 = 22 - 2
                y_threshold2 = 22 + 2
            else:
                return False
            if not calc_K_hours:
                return y_threshold1 <= row.iloc[1] <= y_threshold2
            else:
                return 0

        def is_above_thresholds_16798_NA(row, calc_K_hours=False):
            if 16 <= row.iloc[0] <= 32:
                y_threshold1 = 18 + 0.25 * row.iloc[0] + 2
                y_threshold2 = 18 + 0.25 * row.iloc[0] + 4
            elif row.iloc[0] > 32:
                y_threshold1 = 26 + 2
                y_threshold2 = 26 + 4
            elif row.iloc[0] < 16:
                y_threshold1 = 22 + 2
                y_threshold2 = 22 + 4
            else:
                return False
            if not calc_K_hours:
                return y_threshold1 < row.iloc[1] <= y_threshold2
            else:
                if y_threshold1 < row.iloc[1] <= y_threshold2:
                    return abs(y_threshold1 - row.iloc[1])
                else:
                    return 0

        def is_below_thresholds_16798_NA(row, calc_K_hours=False):
            if 16 <= row.iloc[0] <= 32:
                y_threshold1 = 18 + 0.25 * row.iloc[0] - 2
                y_threshold2 = 18 + 0.25 * row.iloc[0] - 4
            elif row.iloc[0] > 32:
                y_threshold1 = 26 - 2
                y_threshold2 = 26 - 4
            elif row.iloc[0] < 16:
                y_threshold1 = 22 - 2
                y_threshold2 = 22 - 4
            else:
                return False
            if not calc_K_hours:
                return y_threshold1 > row.iloc[1] >= y_threshold2
            else:
                if y_threshold1 > row.iloc[1] >= y_threshold2:
                    return abs(y_threshold1 - row.iloc[1])
                else:
                    return 0

        def is_out_above_thresholds_16798_NA(row, calc_K_hours=False):
            if 16 <= row.iloc[0] <= 32:
                y_threshold2 = 18 + 0.25 * row.iloc[0] + 4
            elif row.iloc[0] > 32:
                y_threshold2 = 26 + 4
            elif row.iloc[0] < 16:
                y_threshold2 = 22 + 4
            else:
                return False
            if not calc_K_hours:
                return row.iloc[1] > y_threshold2
            else:
                if row.iloc[1] > y_threshold2:
                    return abs(y_threshold2 - row.iloc[1])
                else:
                    return 0

        def is_out_below_thresholds_16798_NA(row, calc_K_hours=False):
            if 16 <= row.iloc[0] <= 32:
                y_threshold2 = 18 + 0.25 * row.iloc[0] - 4
            elif row.iloc[0] > 32:
                y_threshold2 = 26 - 4
            elif row.iloc[0] < 16:
                y_threshold2 = 22 - 4
            else:
                return False
            if not calc_K_hours:
                return row.iloc[1] < y_threshold2
            else:
                if row.iloc[1] < y_threshold2:
                    return abs(y_threshold2 - row.iloc[1])
                else:
                    return 0

        def plot_scatter_en16798(in_df, above_df, below_df, out_above_df,
                                 out_below_df,
                                 path, name):
            plt.figure(figsize=(13.2 / INCH, 8.3 / INCH))

            plt.scatter(in_df.iloc[:, 0],
                        in_df.iloc[:, 1],
                        s=0.1,
                        color='green', marker=".", label='within range of DIN '
                                                         'EN '
                                                         '16798-1 NA (GER)')
            plt.scatter(above_df.iloc[:, 0],
                        above_df.iloc[:, 1],
                        s=0.1,
                        color='orange', marker=".", label='above range of DIN '
                                                          'EN 16798-1 NA ('
                                                          'GER), within 2K '
                                                          'range')
            plt.scatter(out_above_df.iloc[:, 0],
                        out_above_df.iloc[:, 1],
                        s=0.1,
                        color='red', marker=".", label='above range of '
                                                       'DIN EN 16798-1 NA ('
                                                       'GER), out of 2K range')
            plt.scatter(below_df.iloc[:, 0],
                        below_df.iloc[:, 1],
                        s=0.1,
                        color='cyan', marker=".", label='below range of DIN '
                                                        'EN 16798-1 NA ('
                                                        'GER), within 2K range')
            plt.scatter(out_below_df.iloc[:, 0],
                        out_below_df.iloc[:, 1],
                        s=0.1,
                        color='blue', marker=".", label='below range of DIN '
                                                        'EN 16798-1 NA ('
                                                        'GER), out of 2K range')
            coord_cat1_low = [
                [10, 22 - 2],
                [16, 18 + 0.25 * 16 - 2],
                [32, 18 + 0.25 * 32 - 2],
                [36, 26 - 2]]
            coord_cat1_up = [
                [10, 22 + 2],
                [16, 18 + 0.25 * 16 + 2],
                [32, 18 + 0.25 * 32 + 2],
                [36, 26 + 2]]
            cc1lx, cc1ly = zip(*coord_cat1_low)
            cc1ux, cc1uy = zip(*coord_cat1_up)
            plt.plot(cc1lx, cc1ly, linestyle='dashed', color='black',
                     label='DIN EN 16798-1 NA (GER): Acceptability range')
            plt.plot(cc1ux, cc1uy, linestyle='dashed', color='black')
            coord_2Kmax_low = [
                [10, 22 - 4],
                [16, 18 + 0.25 * 16 - 4],
                [32, 18 + 0.25 * 32 - 4],
                [36, 26 - 4]]
            coord_2Kmax_up = [
                [10, 22 + 4],
                [16, 18 + 0.25 * 16 + 4],
                [32, 18 + 0.25 * 32 + 4],
                [36, 26 + 4]]
            cc2lx, cc2ly = zip(*coord_2Kmax_low)
            cc2ux, cc2uy = zip(*coord_2Kmax_up)
            plt.plot(cc2lx, cc2ly, linestyle='dashed', color='purple',
                     label='DIN EN 16798-1 NA (GER): Limit for additional 2K '
                           'range')
            plt.plot(cc2ux, cc2uy, linestyle='dashed', color='purple')

            # Customize plot
            plt.xlabel('Hourly Mean Outdoor Temperature (\u00B0C)',
                       fontsize=8)
            plt.ylabel('Operative Temperature (\u00B0C)', fontsize=8)
            plt.xlim([lim_min, lim_max])
            plt.ylim([18, 34])
            plt.grid()
            lgnd = plt.legend(loc="upper left", scatterpoints=1, fontsize=8)
            plt.savefig(
                path / str('DIN_EN_16798_NA_' + name + '.pdf'))

        lim_min = 10
        lim_max = 36

        ot = df['operative_air_temp_rooms_' + guid]
        out_temp = df['site_outdoor_air_temp']
        n_persons_df = df['n_persons_rooms_' + guid]
        n_persons_df = n_persons_df.map(lambda x: x.m)
        n_persons_scaling_df = n_persons_df / n_persons_df.max()

        merged_df = pd.merge(out_temp, ot, left_index=True, right_index=True)
        merged_df = merged_df.map(lambda x: x.m)
        filtered_df_within_NA = merged_df[
            merged_df.apply(is_within_thresholds_16798_NA,
                            axis=1)]
        filtered_df_above_NA = merged_df[
            merged_df.apply(is_above_thresholds_16798_NA,
                            axis=1)]
        filtered_df_out_above_NA = merged_df[
            merged_df.apply(is_out_above_thresholds_16798_NA,
                            axis=1)]
        filtered_df_below_NA = merged_df[
            merged_df.apply(is_below_thresholds_16798_NA,
                            axis=1)]
        filtered_df_out_below_NA = merged_df[
            merged_df.apply(is_out_below_thresholds_16798_NA,
                            axis=1)]
        filtered_df_within_NA_hours = (
            filtered_df_within_NA.apply(is_within_thresholds_16798_NA,
                                        calc_K_hours=True, axis=1))
        filtered_df_above_NA_hours = (
            filtered_df_above_NA.apply(is_above_thresholds_16798_NA,
                                       calc_K_hours=True, axis=1))
        filtered_df_out_above_NA_hours = (
            filtered_df_out_above_NA.apply(is_out_above_thresholds_16798_NA,
                                           calc_K_hours=True, axis=1))
        filtered_df_below_NA_hours = (
            filtered_df_below_NA.apply(is_below_thresholds_16798_NA,
                                       calc_K_hours=True, axis=1))
        filtered_df_out_below_NA_hours = (
            filtered_df_out_below_NA.apply(is_out_below_thresholds_16798_NA,
                                           calc_K_hours=True,
                                           axis=1))
        common_index_within = filtered_df_within_NA.index.intersection(
            n_persons_df.index)
        common_index_above = filtered_df_above_NA.index.intersection(
            n_persons_df.index)
        common_index_out_above = filtered_df_out_above_NA.index.intersection(
            n_persons_df.index)
        common_index_below = filtered_df_below_NA.index.intersection(
            n_persons_df.index)
        common_index_out_below = filtered_df_out_below_NA.index.intersection(
            n_persons_df.index)

        filtered_df_within_NA_occ = filtered_df_within_NA.loc[
            common_index_within][n_persons_df.loc[common_index_within] > 0]
        filtered_df_above_NA_occ = filtered_df_above_NA.loc[common_index_above][
            n_persons_df.loc[common_index_above] > 0]
        filtered_df_out_above_NA_occ = filtered_df_out_above_NA.loc[
            common_index_out_above][
            n_persons_df.loc[common_index_out_above] > 0]
        filtered_df_below_NA_occ = filtered_df_below_NA.loc[common_index_below][
            n_persons_df.loc[common_index_below] > 0]
        filtered_df_out_below_NA_occ = filtered_df_out_below_NA.loc[
            common_index_out_below][
            n_persons_df.loc[common_index_out_below] > 0]
        filtered_df_within_NA_hours_occ = filtered_df_within_NA_hours.loc[
            common_index_within][n_persons_df.loc[common_index_within] > 0]
        filtered_df_above_NA_hours_occ = filtered_df_above_NA_hours.loc[
            common_index_above][
            n_persons_df.loc[common_index_above] > 0]
        filtered_df_out_above_NA_hours_occ = filtered_df_out_above_NA_hours.loc[
            common_index_out_above][
            n_persons_df.loc[common_index_out_above] > 0]
        filtered_df_below_NA_hours_occ = filtered_df_below_NA_hours.loc[
            common_index_below][
            n_persons_df.loc[common_index_below] > 0]
        filtered_df_out_below_NA_hours_occ = filtered_df_out_below_NA_hours.loc[
            common_index_out_below][
            n_persons_df.loc[common_index_out_below] > 0]
        if self.playground.sim_settings.comfort_occupancy_weighting:
            filtered_df_within_NA_hours_occ = (
                    filtered_df_within_NA_hours_occ * n_persons_scaling_df.loc[
                filtered_df_within_NA_hours_occ.index])
            filtered_df_above_NA_hours_occ = (
                    filtered_df_above_NA_hours_occ * n_persons_scaling_df.loc[
                filtered_df_above_NA_hours_occ.index])
            filtered_df_out_above_NA_hours_occ = (
                    filtered_df_out_above_NA_hours_occ * n_persons_scaling_df.loc[
                filtered_df_out_above_NA_hours_occ.index])
            filtered_df_below_NA_hours_occ = (
                    filtered_df_below_NA_hours_occ * n_persons_scaling_df.loc[
                filtered_df_below_NA_hours_occ.index])
            filtered_df_out_below_NA_hours_occ = (
                    filtered_df_out_below_NA_hours_occ * n_persons_scaling_df.loc[
                filtered_df_out_below_NA_hours_occ.index])

        cat_analysis_dict = {
            'ROOM': room_name,
            'total': 8760,
            'within': len(filtered_df_within_NA),
            'above': len(filtered_df_above_NA),
            'below': len(filtered_df_below_NA),
            'out above': len(filtered_df_out_above_NA),
            'out below': len(filtered_df_out_below_NA)
        }
        cat_analysis_hours_dict = {
            'ROOM': room_name,
            'total': 8760*2,
            'within': filtered_df_within_NA_hours.sum(),
            'above': filtered_df_above_NA_hours.sum(),
            'below': filtered_df_below_NA_hours.sum(),
            'out above': filtered_df_out_above_NA_hours.sum(),
            'out below': filtered_df_out_below_NA_hours.sum()
        }
        # acceptable over-temperature hours
        occupied_2K_hours = {
            'ROOM': room_name,
            'total': len(n_persons_df[n_persons_df > 0]),
            'within': 8760 * 2,
            # random choice, over-temperature hours are zero
            'above': len(n_persons_df[n_persons_df > 0]) * 2,
            'below': len(n_persons_df[n_persons_df > 0]) * 2,
            'out above': 0,
            'out below': 0
        }

        cat_analysis_df = pd.DataFrame(cat_analysis_dict, index=[0])
        cat_analysis_hours_df = pd.DataFrame(cat_analysis_hours_dict, index=[0])
        cat_analysis_occ_dict = {
            'ROOM': room_name,
            'total': len(n_persons_df[n_persons_df > 0]),
            'within': len(filtered_df_within_NA_occ),
            'above': len(filtered_df_above_NA_occ),
            'below': len(filtered_df_below_NA_occ),
            'out above': len(filtered_df_out_above_NA_occ),
            'out below': len(filtered_df_out_below_NA_occ)
        }
        cat_analysis_occ_hours_dict = {
            'ROOM': room_name,
            'total': len(n_persons_df[n_persons_df > 0]),
            'within': filtered_df_within_NA_hours_occ.sum(),
            'above': filtered_df_above_NA_hours_occ.sum(),
            'below': filtered_df_below_NA_hours_occ.sum(),
            'out above': filtered_df_out_above_NA_hours_occ.sum(),
            'out below': filtered_df_out_below_NA_hours_occ.sum()
        }
        cat_analysis_occ_df = pd.DataFrame(cat_analysis_occ_dict, index=[0])
        cat_analysis_hours_occ_df = pd.DataFrame(cat_analysis_occ_hours_dict,
                                                 index=[0])
        failed = False
        failing_reasons = dict()
        for key, value in occupied_2K_hours.items():
            if key in ['ROOM', 'total']:
                continue
            if (0.01 * occupied_2K_hours[key] - cat_analysis_occ_hours_dict[
                key]) < -1e-4:
                failed = True
                if occupied_2K_hours[key] > 0:
                    failing_reasons.update(
                        {key: str(round(100*(cat_analysis_occ_hours_dict[key] /
                              occupied_2K_hours[key]), 2))+' %'})
                else:
                    failing_reasons.update({key: '100 %'})
        if failed:
            logger.warning(f'Adaptive thermal comfort test failed for space '
                           f'{room_name} due to exceeded limits in '
                           f'{failing_reasons}.')
        analysis_file = export_path / 'DIN_EN_16798_NA_analysis.csv'
        cat_analysis_df.to_csv(analysis_file, mode='a+', header=False, sep=';')
        analysis_hours_file = export_path / 'DIN_EN_16798_NA_hours_analysis.csv'
        cat_analysis_hours_df.to_csv(analysis_hours_file, mode='a+',
                                     header=False,
                                     sep=';')
        analysis_occ_file = export_path / 'DIN_EN_16798_NA_analysis_occ.csv'
        cat_analysis_occ_df.to_csv(analysis_occ_file, mode='a+', header=False,
                                   sep=';')
        analysis_hours_occ_file = (export_path /
                                   'DIN_EN_16798_NA_hours_analysis_occ.csv')
        cat_analysis_hours_occ_df.to_csv(analysis_hours_occ_file, mode='a+',
                                         header=False, sep=';')

        plot_scatter_en16798(filtered_df_within_NA, filtered_df_above_NA,
                             filtered_df_below_NA, filtered_df_out_above_NA,
                             filtered_df_out_below_NA,
                             export_path, room_name)
        plot_scatter_en16798(filtered_df_within_NA_occ,
                             filtered_df_above_NA_occ,
                             filtered_df_below_NA_occ,
                             filtered_df_out_above_NA_occ,
                             filtered_df_out_below_NA_occ,
                             export_path,
                             room_name + '_occupancy')
        return cat_analysis_df, cat_analysis_occ_df, cat_analysis_hours_occ_df

    @staticmethod
    def table_bar_plot_16798(df, export_path, tag='', normalize=True,
                             unit='', y_scale='linear'):
        """Create bar plot with a table below for EN 16798 thermal comfort.

        This function creates a bar plot with a table below along with the
        thermal comfort categories according to EN 16798. This table
        considers all hours of the day, not only the occupancy hours.

        """
        # with columns: 'ROOM', 'CAT1', 'CAT2', 'CAT3', 'OUT'
        logger.info(f"Plot DIN EN 16798 table bar plot all zones.")
        if tag:
            tag = '_' + tag
        rename_columns = {
            'CAT1': 'CAT I',
            'CAT2': 'CAT II',
            'CAT3': 'CAT III',
            'OUT': u'> CAT III',
            # Add more entries for other columns
        }

        # Rename the columns of the DataFrame using the dictionary
        df.rename(columns=rename_columns, inplace=True)

        # Set 'ROOM' column as the index
        df.set_index('ROOM', inplace=True)
        if normalize:
            row_sums = df.loc[:, df.columns != 'total'].sum(axis=1)
            # Create a new DataFrame by dividing the original DataFrame by the row
            # sums
            normalized_df = df.loc[:, df.columns != 'total'].div(row_sums, axis=0)
            normalized_df = normalized_df * 100
        else:
            normalized_df = df.loc[:, df.columns != 'total']
        fig, ax = plt.subplots(
            figsize=(24, 12))  # Adjust figure size to allow more space

        x_pos = np.arange(len(set(normalized_df.index))) * 0.8
        bar_width = 0.35
        bottom = np.zeros(len(normalized_df.index))

        # Create the bar chart
        for i, col in enumerate(normalized_df.columns):
            if col == 'total':
                continue
            color = 'purple'
            if col == 'CAT I':
                color = 'green'
            elif col == 'CAT II':
                color = 'blue'
            elif col == 'CAT III':
                color = 'orange'
            elif col == u'> CAT III':
                color = 'red'
            elif col == 'within':
                color = 'green'
            elif col == 'above':
                color = 'orange'
            elif col == 'below':
                color = 'cyan'
            elif col == 'out above':
                color = 'red'
            elif col == 'out below':
                color = 'blue'
            ax.bar(normalized_df.index, normalized_df[col], width=-bar_width,
                   label=col, align='edge',
                   bottom=bottom, color=color)
            bottom += normalized_df[col]

        # Set consistent font size for all elements
        common_fontsize = 11
        if normalize:
            ax.set_ylabel(u'% of hours per category', fontsize=common_fontsize)
        else:
            ax.set_ylabel(unit, fontsize=common_fontsize)

        ax.tick_params(axis='y',
                       labelsize=common_fontsize)  # Match font size for y-axis ticks
        ax.tick_params(axis='x', labelrotation=90)
        if normalize:
            plt.ylim([0, 100])
        else:
            # Set the y-axis to logarithmic scale
            ax.set_yscale(y_scale)
        plt.xlim([-bar_width / 2 - 0.5,
                  len(normalized_df.index) - bar_width / 2 - 0.5])
        plt.xticks([])  # Remove x-ticks for table
        if normalize:
            formatted_df = normalized_df.applymap(lambda x: f'{x:.1f}')
        else:
            def format_value(x, index):
                total = df.loc[index, "total"]
                return f'{x:.1f} ({(x / (total * 2)) * 100:.1f} %)'

            formatted_df = normalized_df.apply(
                lambda row: row.apply(lambda x: format_value(x, row.name)),
                axis=1)
        cell_text = [formatted_df[column] for column in formatted_df.columns]

        if normalize:
        # Create the table
            table = plt.table(cellText=cell_text,
                              rowLabels=formatted_df.columns + u' / %',
                              colLabels=formatted_df.index,
                              cellLoc='center',
                              loc='bottom')
        else:
            cell_text.insert(0, df['total'])
            table = plt.table(cellText=cell_text,
                              rowLabels=['occupied hours / hours'] + list(
                                  formatted_df.columns + f' / {unit}'),
                              colLabels=formatted_df.index,
                              cellLoc='center',
                              loc='bottom')

        # Ensure consistent font size for the table
        table.auto_set_font_size(False)
        table.set_fontsize(common_fontsize)

        # Dynamically calculate the required height for rotated text
        renderer = fig.canvas.get_renderer()
        max_text_height = 0  # Track the maximum height
        table.scale(1.0, 5.0)  # Adjust scaling for overall table size

        for i in range(len(cell_text[0])):
            cell = table[(0, i)]  # Access header cells
            text = cell.get_text()
            text.set_rotation(90)  # Rotate the text by 90 degrees

            # Measure text size dynamically
            fig.canvas.draw()  # Update layout for accurate text size
            bbox = text.get_window_extent(renderer=renderer)
            text_height = bbox.height / 200  # Convert
            # height
            # to figure-relative units
            max_text_height = max(max_text_height, text_height)

        # Apply a uniform height to all header cells
        for i in range(len(cell_text[0])):
            cell = table[(0, i)]
            cell.set_height(
                max_text_height * 1.05)  # Add a slight margin factor

        # Scale table rows and columns

        # Adjust the layout to fit the table properly
        fig.subplots_adjust(
            bottom=0.7)  # Allocate space below the plot for the table

        # Adjust the legend placement BELOW the table
        legend_y_offset = -0.8 - max_text_height  # Dynamically calculate offset
        lgnd = plt.legend(framealpha=0.0, prop={'size': common_fontsize},
                          loc='lower center',
                          bbox_to_anchor=(0.5, legend_y_offset),
                          ncol=len(normalized_df.columns))  # Adjust legend
        # position

        # Save the figure
        fig.savefig(export_path / f'DIN_EN_16798{tag}_all_zones_bar_table.pdf',
                    bbox_inches='tight',
                    bbox_extra_artists=(lgnd, table))

    @staticmethod
    def visualize_calendar(calendar_df, export_path, year='',
                           color_only=False, save=True,
                           save_as='',
                           construction='', skip_legend=False,
                           add_title=False, figsize=[7.6, 8], zone_dict=None):

        logger.info(f"Plot PMV calendar plot for zone {calendar_df.columns[0]}")

        def visualize(zone_dict):

            fig, ax = plt.subplots(
                figsize=(figsize[0] / INCH, figsize[1] / INCH))
            daily_mean = calendar_df.resample('D').mean()
            calendar_heatmap(ax, daily_mean, color_only)
            title_name = calendar_df.columns[0]
            for key, item in zone_dict.items():
                if key in title_name:
                    title_name = title_name.replace(key, item)
            if add_title:
                plt.title(str(year) + ' ' + title_name)
            if save:
                plt.savefig(export_path / str(construction +
                                              save_as + title_name
                                              + '.pdf'),
                            bbox_inches='tight')
                if skip_legend:
                    plt.savefig(export_path / 'subplots' / str(construction +
                                                               save_as + title_name
                                                               + '.pdf'),
                                bbox_inches='tight')
            plt.draw()
            plt.close()

        def calendar_array(dates, data):
            i, j = zip(*[(d.day, d.month) for d in dates])
            i = np.array(i) - min(i)
            j = np.array(j) - 1
            ni = max(i) + 1
            calendar = np.empty([ni, 12])  # , dtype='S10')
            calendar[:] = np.nan
            calendar[i, j] = data
            return i, j, calendar

        def calendar_heatmap(ax, df, color_only):

            color_schema = ['#0232c2', '#028cc2', '#03ffff',
                            '#02c248', '#bbc202', '#c27f02']
            # Labels and their corresponding indices
            labels = ['-3 to -2', '-2 to -1', '-1 to 0',
                      '0 to 1', '1 to 2', '2 to 3']
            label_indices = np.arange(len(labels) + 1) - 3

            # Create a ListedColormap from the color schema
            cmap = ListedColormap(color_schema)
            df_dates = df.index
            df_data = df[df.columns[0]].values
            norm = Normalize(vmin=-3, vmax=3)

            i, j, calendar = calendar_array(df_dates, df_data)

            im = ax.imshow(calendar, aspect='auto', interpolation='none',
                           cmap=cmap, norm=norm)
            label_days(ax, df_dates, i, j, calendar)
            if not color_only:
                label_data(ax, calendar)
            label_months(ax, df_dates, i, j, calendar)
            if not skip_legend:
                cbar = ax.figure.colorbar(im, ticks=label_indices)
            # Minor ticks
            ax.set_xticks(np.arange(-.5, len(calendar[0]), 1), minor=True)
            ax.set_yticks(np.arange(-.5, len(calendar[:, 0]), 1), minor=True)

            ax.grid(False)
            # Gridlines based on minor ticks
            ax.grid(which='minor', color='w', linestyle='-', linewidth=0.5)

            # Remove minor ticks
            ax.tick_params(which='minor', bottom=False,
                           left=False)  # ax.get_yaxis().set_ticks(label_indices)
            # ax.get_yaxis().set_ticklabels(labels)

        def label_data(ax, calendar):
            for (i, j), data in np.ndenumerate(calendar):
                if type(data) == str:
                    ax.text(j, i, data, ha='center', va='center')
                elif np.isfinite(data):
                    ax.text(j, i, round(data, 1), ha='center', va='center')

        def label_days(ax, dates, i, j, calendar):
            ni, nj = calendar.shape
            day_of_month = np.nan * np.zeros((ni, nj))
            day_of_month[i, j] = [d.day for d in dates]

            yticks = np.arange(31)
            yticklabels = [i + 1 for i in yticks]
            ax.set_yticks(yticks)
            ax.set_yticklabels(yticklabels, fontsize=6)
            # ax.set(yticks=yticks,
            #        yticklabels=yticklabels)

        def label_months(ax, dates, i, j, calendar):
            month_labels = np.array(
                ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul',
                 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
            months = np.array([d.month for d in dates])
            uniq_months = sorted(set(months))
            # xticks = [i[months == m].mean() for m in uniq_months]
            xticks = [i - 1 for i in uniq_months]
            labels = [month_labels[m - 1] for m in uniq_months]
            ax.set(xticks=xticks)
            ax.set_xticklabels(labels, fontsize=6, rotation=90)
            ax.xaxis.tick_top()

        visualize(zone_dict)
