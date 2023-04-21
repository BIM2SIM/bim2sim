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
from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.task.common import common
import numpy as np
import OCC.Display.SimpleGui
from matplotlib import cm


logger = logging.getLogger(__name__)


class ComfortVisualization(ITask):
    """Visualize Comfort Results of an EnergyPlus Simulation.

    Task to Visualize EnergyPlus Comfort Measures.
    """

    reads = ('instances',)

    def __init__(self):
        super().__init__()
        self.idf = None

    def run(self, workflow, instances):
        """Execute all methods to visualize comfort results."""
        logger.info("Visualization of Comfort Results started ...")
        df_ep_res = pd.read_csv(self.paths.export / 'EP-results/eplusout.csv')
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
