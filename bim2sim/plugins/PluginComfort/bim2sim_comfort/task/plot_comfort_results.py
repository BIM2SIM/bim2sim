import json
import matplotlib as mpl
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from bim2sim.tasks.bps import PlotBEPSResults

INCH = 2.54


class PlotComfortResults(PlotBEPSResults):
    reads = ('df_finals', 'sim_results_path', 'ifc_files')
    final = True

    def run(self, df_finals, sim_results_path, ifc_files):
        zone_dict_path = sim_results_path / self.prj_name / 'zone_dict.json'
        with open(zone_dict_path) as j:
            zone_dict = json.load(j)

        for bldg_name, df in df_finals.items():
            export_path = sim_results_path / bldg_name
            cat_analysis = self.apply_en16798_to_all_zones(df, zone_dict,
                                                           export_path)
            self.table_bar_plot_16798(cat_analysis, export_path)

    def apply_en16798_to_all_zones(self, df, zone_dict, export_path):
        """Generate EN 16798 diagrams for all thermal zones.

        """
        cat_analysis = pd.DataFrame()
        for guid, room_name in zone_dict.items():
            temp_cat_analysis = None
            temp_cat_analysis = self.plot_new_en16798_adaptive_count(
                df, guid, room_name, export_path)
            cat_analysis = pd.concat([cat_analysis, temp_cat_analysis])
        return cat_analysis

    @staticmethod
    def plot_new_en16798_adaptive_count(df, guid, room_name, export_path):
        """Plot EN 16798 diagram for thermal comfort categories for a single
        thermal zone.

        """

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

        plt.rcParams.update(mpl.rcParamsDefault)
        plt.rcParams.update({
            "lines.linewidth": 0.4,
            "font.family": "serif",  # use serif/main font for text elements
            "text.usetex": True,  # use inline math for ticks
            "pgf.rcfonts": True,  # don't setup fonts from rc parameters
            "font.size": 8
        })

        lim_min = 10
        lim_max = 30

        ot = df['operative_air_temp_rooms_' + guid]
        out_temp = df['site_outdoor_air_temp']

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
        cat_analysis_dict = {
            'ROOM': room_name,
            'CAT1': len(filtered_df_cat1),
            'CAT2': len(filtered_df_cat2),
            'CAT3': len(filtered_df_cat3),
            'OUT': len(filtered_df_outside)
        }
        cat_analysis_df = pd.DataFrame(cat_analysis_dict, index=[0])

        analysis_file = export_path / 'DIN_EN_16798_analysis.csv'
        cat_analysis_df.to_csv(analysis_file, mode='a+', header=False, sep=';')

        plt.figure(figsize=(13.2 / INCH, 8.3 / INCH))

        plt.scatter(filtered_df_cat1.iloc[:, 0], filtered_df_cat1.iloc[:, 1],
                    s=0.1,
                    color='green', marker=".")
        plt.scatter(filtered_df_cat2.iloc[:, 0], filtered_df_cat2.iloc[:, 1],
                    s=0.1,
                    color='orange', marker=".")
        plt.scatter(filtered_df_cat3.iloc[:, 0], filtered_df_cat3.iloc[:, 1],
                    s=0.1,
                    color='red', marker=".")
        plt.scatter(filtered_df_outside.iloc[:, 0],
                    filtered_df_outside.iloc[:, 1],
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
        plt.xlabel('Running Mean Outdoor Temperature ($^{\circ}C$)',
                   fontsize=8)
        plt.ylabel('Operative Temperature ($^{\circ}C$)', fontsize=8)
        plt.xlim([lim_min, lim_max])
        plt.ylim([16.5, 35.5])
        plt.grid()
        lgnd = plt.legend(loc="upper left", scatterpoints=1, fontsize=8)
        plt.savefig(
            export_path / str('DIN_EN_16798_new_' + room_name + '.pdf'))

        return cat_analysis_df

    @staticmethod
    def table_bar_plot_16798(df, export_path):
        """Create bar plot with a table below for EN 16798 thermal comfort.

        This function creates a bar plot with a table below along with the
        thermal comfort categories according to EN 16798. This table
        considers all hours of the day, not only the occupancy hours.

        """
        # with columns: 'ROOM', 'CAT1', 'CAT2', 'CAT3', 'OUT'

        rename_columns = {
            'CAT1': 'CAT I',
            'CAT2': 'CAT II',
            'CAT3': 'CAT III',
            'OUT': '$>$ CAT III',
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
        fig, ax = plt.subplots(figsize=(13.2 / INCH, 8 / INCH))
        x_pos = np.arange(len(normalized_df.index))
        bar_width = 0.35
        bottom = np.zeros(len(normalized_df.index))

        for i, col in enumerate(normalized_df.columns):
            ax.bar(x_pos, normalized_df[col], width=bar_width, label=col,
                   bottom=bottom)
            bottom += normalized_df[col]

        ax.set_ylabel(r'\% of hours per category')
        # plt.xticks(x_pos, df.index)
        plt.xticks([])
        plt.ylim([0, 100])
        lgnd = plt.legend(framealpha=0.0, ncol=1,
                          prop={'size': 6}, bbox_to_anchor=[0.5, -0.5],
                          loc="center",
                          ncols=4)
        formatted_df = normalized_df.map(lambda x: f'{x:.0f}\%')
        # Create a table below the bar plot with column names as row labels
        cell_text = []
        for column in formatted_df.columns:
            cell_text.append(formatted_df[column])

        # Transpose the DataFrame for the table
        table = plt.table(cellText=cell_text, rowLabels=formatted_df.columns,
                          colLabels=formatted_df.index,
                          cellLoc='center',
                          loc='bottom')
        table.auto_set_font_size(False)
        table.set_fontsize(7)
        table.scale(1.0, 1.2)  # Adjust the table size as needed
        plt.tight_layout()
        plt.savefig(export_path / 'DIN_EN_16798_all_zones_bar_table.pdf',
                    bbox_inches='tight',
                    bbox_extra_artists=(lgnd, table))
