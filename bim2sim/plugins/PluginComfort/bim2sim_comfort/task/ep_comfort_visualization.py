"""Visualize EnergyPlus Comfort Results.

This module includes all functions for visualization of Comfort
Results. Geometric preprocessing (includes EnergyPlus specific space
boundary enrichment), EnergyPlus Input File export and EnergyPlus simulation
must be executed before this module.
"""
import json
import logging
import os

import pandas as pd
from pathlib import Path

from matplotlib.colors import ListedColormap, Normalize

import bim2sim
from bim2sim import run_project, ConsoleDecisionHandler, Project

from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB

from bim2sim.elements.bps_elements import ThermalZone
from bim2sim.plugins.PluginComfort.bim2sim_comfort.task.ep_load_idf import \
    LoadIdf
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils
from bim2sim.tasks import common
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
import numpy as np
import OCC.Display.SimpleGui
from matplotlib import cm, pyplot as plt

import matplotlib as mpl
mpl.use('Agg')

PLOT_PATH = Path(r'C:\Users\richter\sciebo\03-Paperdrafts'
                 r'\MDPI_SpecialIssue_Comfort_Climate\img'
                 r'\generated_plots')
INCH = 2.54
logger = logging.getLogger(__name__)


class ComfortVisualization(ITask):
    """Visualize Comfort Results of an EnergyPlus Simulation.

    Task to Visualize EnergyPlus Comfort Measures.
    """

    reads = ('elements',)

    def __init__(self, playground):
        super().__init__(playground)
        self.idf = None

    def run(self, elements=None):
        """Execute all methods to visualize comfort results."""
        logger.info("Visualization of Comfort Results started ...")
        df_ep_res = pd.read_csv(self.paths.export / 'EP-results/eplusout.csv')
        # convert to date time index
        df_ep_res["Date/Time"] = df_ep_res["Date/Time"].apply(
            PostprocessingUtils._string_to_datetime)
        op_temp_cols = [col for col in df_ep_res.columns if
                        'Operative Temperature'
                        in col]
        op_temp_df = df_ep_res[op_temp_cols].round(2)
        mean_temp_df = df_ep_res[[col for col in df_ep_res.columns
                                  if 'Mean Air Temperature' in col]]
        pmv_temp_df = df_ep_res[[col for col in df_ep_res.columns
                                   if 'Fanger Model PMV' in col]]
        ppd_temp_df = df_ep_res[[col for col in df_ep_res.columns
                                   if 'Fanger Model PPD' in col]]
        pmv_temp_df = pmv_temp_df.set_index(df_ep_res['Date/Time'])

        for col in pmv_temp_df.columns:
            self.visualize_calendar(pd.DataFrame(pmv_temp_df[col]))
        # fig = plt.figure(figsize=(10/INCH,10/INCH))
        # for i in range(len(pmv_temp_df.columns)):
        #     plt.scatter(df_ep_res[df_ep_res.columns[1]], df_ep_res[
        #         pmv_temp_df.columns[i]], marker='.', s=(72./fig.dpi),
        #                 label=pmv_temp_df.columns[i])
        # plt.legend()
        # plt.draw()
        # plt.close()
        spaces = filter_elements(elements, ThermalZone)
        space_shapes = [shp.space_shape for shp in spaces]
        # VisualizationUtils.display_occ_shapes(space_shapes)
        self.visualize_comfort(spaces, pmv_temp_df.mean())
        self.visualize_comfort(spaces, ppd_temp_df.mean())
        self.visualize_comfort(spaces, op_temp_df.mean())
        self.visualize_comfort(spaces, mean_temp_df.mean())

    @staticmethod
    def visualize_comfort(spaces, mean_temp_df):
        # Create a list to store the spaces and their corresponding temperature
        # values
        spaces_and_temps = []

        # Iterate over the spaces
        for space in spaces:
            # Get the name of the space
            name = space.guid
            # If the space has a name and a corresponding temperature value,
            # add it to the list
            if any(name.upper() in k.upper() for k in mean_temp_df.keys()):
                key = [k for k in mean_temp_df.keys() if name.upper() in
                       k.upper()]
                spaces_and_temps.append((space.space_shape, mean_temp_df[
                    key].values.sum(), space.space_center))

        # Create a display window
        display, start_display, add_menu, add_function_to_menu = \
            OCC.Display.SimpleGui.init_display()
        # Create the color map
        cmap = cm.get_cmap('viridis')
        legend_max_temp = max([float(temp) for space, temp, center
                               in spaces_and_temps])
        legend_min_temp = min([float(temp) for space, temp, center
                               in spaces_and_temps])


        # Assign the colors to the objects
        # Iterate over the spaces and temperature values and add them to the
        # display
        for space, temp, center in spaces_and_temps:
            # Set the color of the space based on the temperature value
            # Normalize the values to the range of 0 to 1
            normalized_value = (float(temp) - legend_min_temp) / (
                        legend_max_temp - legend_min_temp)
            color = cmap(normalized_value)
            color = Quantity_Color(*color[:-1],
                                   Quantity_TOC_RGB)
            display.DisplayShape(space, color=color, transparency=0.7)
            # display the rounded temperature value at the space center
            display.DisplayMessage(center, str(np.round(temp, 3)),
                                   message_color=(0., 0., 0.))

        display.FitAll()
        start_display()

        # # Add a legend for the temperature values
        # legend_num_steps = 10
        # legend_step_size = (legend_max_temp - legend_min_temp) / legend_num_steps
        # legend_x_pos = 0.1
        # legend_y_pos = 0.9
        # legend_box_width = 0.01
        # legend_box_height = 0.1
        # for i in range(legend_num_steps + 1):
        #     temp = legend_min_temp + i * legend_step_size
        #     color = (1.0, (100 - temp) / 100.0, (100 - temp) / 100.0)
        #     display.DisplayShape(
        #         OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(
        #             gp_Pnt(legend_x_pos, legend_y_pos, 0.0), gp_Pnt(
        #                 legend_x_pos+legend_box_width, legend_y_pos+legend_box_height,
        #                 0.0), color=color))
        # display.FitAll()
        # start_display()

    @staticmethod
    def visualize_calendar(df, year='', color_only=False, save_as='',
                           construction='', skip_legend=False,
                           add_title=False):
        def visualize():
            plt.rcParams.update(mpl.rcParamsDefault)
            plt.rcParams.update({
                "lines.linewidth": 0.4,
                "font.family": "serif",  # use serif/main font for text elements
                "text.usetex": True,     # use inline math for ticks
                "pgf.rcfonts": True,     # don't setup fonts from rc parameters
                "font.size": 8
            })

            fig, ax = plt.subplots(figsize=(7.6/INCH, 8/INCH))
            daily_mean = df.resample('D').mean()
            calendar_heatmap(ax, daily_mean, color_only)
            if add_title:
                plt.title(str(year) + ' - ' + df.columns[0])
            if save_as:
                plt.savefig(PLOT_PATH / str(construction + save_as +
                                            df.columns[0] + '.pdf'),
                            bbox_inches='tight')
                if skip_legend:
                    plt.savefig(PLOT_PATH / 'subplots' / str(construction +
                                                        save_as + df.columns[0]
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
            ax.set_xticklabels(labels, rotation=90)
            ax.xaxis.tick_top()
        visualize()


if __name__ == "__main__":
    """Execute comfort visualization on existing project. Loads existing 
    .ifc and .idf files for visualization purposes. """

    # set path to existing bim2sim project directory
    project_path = Path(f'E:/bim2sim_temp/bim2sim_comfort/')

    # existing ifc_file is loaded from project directory (ifc_path=None)
    project = Project.create(project_folder=project_path, ifc_path=None,
                             plugin='comfort')
    # set EnergyPlus installation path (version should match idf version)
    project.sim_settings.ep_install_path = f'C:/EnergyPlusV9-4-0/'
    # set tasks for comfort visualization (loads ifc and idf from project)
    project.default_plugin.default_tasks = [common.LoadIFC,
                                            common.CreateElementsOnIfcTypes,
                                            LoadIdf,
                                            ComfortVisualization]
    # run project based on new default tasks.
    run_project(project, ConsoleDecisionHandler())
