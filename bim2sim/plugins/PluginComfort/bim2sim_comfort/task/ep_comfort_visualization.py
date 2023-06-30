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

import bim2sim
from bim2sim import run_project, ConsoleDecisionHandler, Project

from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from bim2sim.kernel.elements.bps import ThermalZone
from bim2sim.plugins.PluginComfort.bim2sim_comfort.task.ep_load_idf import \
    LoadIdf
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils
from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.task.common import common
import numpy as np
import OCC.Display.SimpleGui
from matplotlib import cm, pyplot as plt

import matplotlib as mpl
mpl.use('TkAgg')


logger = logging.getLogger(__name__)


class ComfortVisualization(ITask):
    """Visualize Comfort Results of an EnergyPlus Simulation.

    Task to Visualize EnergyPlus Comfort Measures.
    """

    reads = ('instances',)

    def __init__(self):
        super().__init__()
        self.idf = None

    def run(self, workflow, instances=None):
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
        for col in pmv_temp_df.columns[1:]:
            self.visualize_calendar(df_ep_res['Date/Time'], pmv_temp_df[col])
        fig = plt.figure(figsize=(10,10))
        for i in range(len(pmv_temp_df.columns)):
            plt.scatter(df_ep_res[df_ep_res.columns[1]], df_ep_res[
                pmv_temp_df.columns[i]], marker='.', s=(72./fig.dpi),
                        label=pmv_temp_df.columns[i])
        plt.legend()
        plt.show()

        spaces = filter_instances(instances, ThermalZone)
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
    def visualize_calendar(datetime, data):
        def visualize():
            df_visualization = pd.DataFrame()
            df_visualization['Date/Time'] = datetime
            df_visualization['data'] = data
            fig, ax = plt.subplots(figsize=(10, 10))
            daily_mean = df_visualization.groupby(df_visualization[
                                               'Date/Time'].dt.date).mean(
                numeric_only=True).reset_index()
            daily_mean['Date/Time'] = pd.to_datetime(daily_mean['Date/Time'])
            calendar_heatmap(ax, daily_mean['Date/Time'], list(daily_mean[
                                                                  daily_mean.columns[1]]))
            plt.show()

        def calendar_array(dates, data):
            i, j = zip(*[(d.day, d.month) for d in dates])
            i = np.array(i) - min(i)
            j = np.array(j) - 1
            ni = max(i) + 1
            calendar = np.nan * np.zeros((ni, 12))
            calendar[i, j] = data
            return i, j, calendar

        def calendar_heatmap(ax, dates, data):
            i, j, calendar = calendar_array(dates, data)
            im = ax.imshow(calendar, aspect='auto', interpolation='none', \
                                                          cmap='cool')
            label_days(ax, dates, i, j, calendar)
            label_data(ax, calendar)
            label_months(ax, dates, i, j, calendar)
            ax.figure.colorbar(im)

        def label_data(ax, calendar):
            for (i, j), data in np.ndenumerate(calendar):
                if np.isfinite(data):
                    ax.text(j, i, round(data,1), ha='center', va='center')

        def label_days(ax, dates, i, j, calendar):
            ni, nj = calendar.shape
            day_of_month = np.nan * np.zeros((ni, nj))
            day_of_month[i, j] = [d.day for d in dates]

            # for (i, j), day in np.ndenumerate(day_of_month):
            #     if np.isfinite(day):
            #         ax.text(j, i, int(day), ha='center', va='center')
            yticks = np.arange(31)
            yticklabels = [i+1 for i in yticks]
            ax.set(yticks=yticks,
                   yticklabels=yticklabels)

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
    project.workflow.ep_install_path = f'C:/EnergyPlusV9-4-0/'
    # set tasks for comfort visualization (loads ifc and idf from project)
    project.default_plugin.default_tasks = [common.LoadIFC,
                                            common.CreateElements,
                                            LoadIdf,
                                            ComfortVisualization]
    # run project based on new default tasks.
    run_project(project, ConsoleDecisionHandler())
