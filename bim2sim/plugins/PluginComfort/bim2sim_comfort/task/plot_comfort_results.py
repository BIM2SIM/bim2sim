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
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans', 'sans-serif'],  # Specify sans-serif fonts
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
            if not plot_single_guid:
                cat_analysis, cat_analysis_occ = (
                    self.apply_en16798_to_all_zones(df, zone_dict,
                                                               export_path))
            else:
                cat_analysis, cat_analysis_occ = (
                    self.apply_en16798_to_single_zone(df, zone_dict,
                                                      export_path,
                                                      plot_single_guid))
            # plot a barplot combined with table of comfort categories from
            # DIN EN 16798.
            self.table_bar_plot_16798(cat_analysis, export_path)
            self.table_bar_plot_16798(cat_analysis_occ, export_path, tag='occ')

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


    def apply_en16798_to_all_zones(self, df, zone_dict, export_path):
        """Generate EN 16798 diagrams for all thermal zones.

        """
        logger.info("Plot DIN EN 16798 diagrams for all zones ...")

        cat_analysis = pd.DataFrame()
        cat_analysis_occ = pd.DataFrame()
        for guid, room_name in zone_dict.items():
            temp_cat_analysis = None
            temp_cat_analysis_occ = None
            temp_cat_analysis, temp_cat_analysis_occ = (
                self.plot_new_en16798_adaptive_count(
                df, guid, room_name+'_'+guid, export_path))
            cat_analysis = pd.concat([cat_analysis, temp_cat_analysis])
            cat_analysis_occ = pd.concat([cat_analysis_occ,
                                          temp_cat_analysis_occ])
        return cat_analysis, cat_analysis_occ

    def apply_en16798_to_single_zone(self, df, zone_dict, export_path,
                                     zone_guid):
        logger.info(f"Plot DIN EN 16798 diagrams for zone {zone_guid} ...")

        cat_analysis = pd.DataFrame()
        cat_analysis_occ = pd.DataFrame()
        for guid, room_name in zone_dict.items():
            if not guid == zone_guid:
                continue
            temp_cat_analysis = None
            temp_cat_analysis_occ = None
            temp_cat_analysis, temp_cat_analysis_occ = self.plot_new_en16798_adaptive_count(
                df, guid, room_name+'_'+guid, export_path)
            cat_analysis = pd.concat([cat_analysis, temp_cat_analysis])
            cat_analysis_occ = pd.concat([cat_analysis_occ, temp_cat_analysis_occ])
        return cat_analysis, cat_analysis_occ

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
        n_persons_df = df['n_persons_rooms_'+guid]

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
                             room_name+'_occupancy')
        return cat_analysis_df, cat_analysis_occ_df

    @staticmethod
    def table_bar_plot_16798(df, export_path, tag=''):
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
        row_sums = df.sum(axis=1)
        # Create a new DataFrame by dividing the original DataFrame by the row
        # sums
        normalized_df = df.div(row_sums, axis=0)
        normalized_df = normalized_df * 100
        fig, ax = plt.subplots(
            figsize=(24, 12))  # Adjust figure size to allow more space

        x_pos = np.arange(len(set(normalized_df.index))) * 0.8
        bar_width = 0.35
        bottom = np.zeros(len(normalized_df.index))

        # Create the bar chart
        for i, col in enumerate(normalized_df.columns):
            ax.bar(normalized_df.index, normalized_df[col], width=-bar_width,
                   label=col, align='edge',
                   bottom=bottom)
            bottom += normalized_df[col]

        # Set consistent font size for all elements
        common_fontsize = 11
        ax.set_ylabel(u'% of hours per category', fontsize=common_fontsize)
        ax.tick_params(axis='y',
                       labelsize=common_fontsize)  # Match font size for y-axis ticks
        ax.tick_params(axis='x', labelrotation=90)
        plt.ylim([0, 100])
        plt.xlim([-bar_width / 2 - 0.5,
                  len(normalized_df.index) - bar_width / 2 - 0.5])
        plt.xticks([])  # Remove x-ticks for table

        formatted_df = normalized_df.applymap(lambda x: f'{x:.0f}')
        cell_text = [formatted_df[column] for column in formatted_df.columns]

        # Create the table
        table = plt.table(cellText=cell_text,
                          rowLabels=formatted_df.columns + u' / %',
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

        for i, key in enumerate(formatted_df.index):
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
        for i, key in enumerate(formatted_df.index):
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
                          ncol=4)  # Adjust legend position

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

            fig, ax = plt.subplots(figsize=(figsize[0]/INCH, figsize[1]/INCH))
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
            calendar = np.empty([ni, 12])#, dtype='S10')
            calendar[:] = np.nan
            calendar[i, j] = data
            return i, j, calendar

        def calendar_heatmap(ax, df, color_only):

            color_schema = ['#0232c2', '#028cc2', '#03ffff',
                            '#02c248', '#bbc202', '#c27f02']
            # Labels and their corresponding indices
            labels = ['-3 to -2', '-2 to -1', '-1 to 0',
                      '0 to 1', '1 to 2', '2 to 3']
            label_indices = np.arange(len(labels)+1) - 3

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
            ax.set_yticks(np.arange(-.5, len(calendar[:,0]), 1), minor=True)

            ax.grid(False)
            # Gridlines based on minor ticks
            ax.grid(which='minor', color='w', linestyle='-', linewidth=0.5)

            # Remove minor ticks
            ax.tick_params(which='minor', bottom=False, left=False)            # ax.get_yaxis().set_ticks(label_indices)
            # ax.get_yaxis().set_ticklabels(labels)

        def label_data(ax, calendar):
            for (i, j), data in np.ndenumerate(calendar):
                if type(data) == str:
                    ax.text(j, i, data, ha='center', va='center')
                elif np.isfinite(data):
                    ax.text(j, i, round(data,1), ha='center', va='center')

        def label_days(ax, dates, i, j, calendar):
            ni, nj = calendar.shape
            day_of_month = np.nan * np.zeros((ni, nj))
            day_of_month[i, j] = [d.day for d in dates]

            yticks = np.arange(31)
            yticklabels = [i+1 for i in yticks]
            ax.set_yticks(yticks)
            ax.set_yticklabels(yticklabels, fontsize=6)
            # ax.set(yticks=yticks,
            #        yticklabels=yticklabels)


        def label_months(ax, dates, i, j, calendar):
            month_labels = np.array(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul',
                                     'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
            months = np.array([d.month for d in dates])
            uniq_months = sorted(set(months))
            # xticks = [i[months == m].mean() for m in uniq_months]
            xticks = [i-1 for i in uniq_months]
            labels = [month_labels[m - 1] for m in uniq_months]
            ax.set(xticks=xticks)
            ax.set_xticklabels(labels, fontsize=6, rotation=90)
            ax.xaxis.tick_top()
        visualize(zone_dict)
