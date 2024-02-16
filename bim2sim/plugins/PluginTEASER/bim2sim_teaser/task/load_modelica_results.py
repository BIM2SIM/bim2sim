import json
import re
from pathlib import Path

from ebcpy import DymolaAPI

import bim2sim
from bim2sim.tasks.base import ITask


class LoadModelicaResults(ITask):
    """Load existing results, run() method holds detailed information."""
    touches = ('teaser_mat_result_paths', 'sim_results_path', 'tz_mapping')

    def run(self):
        """Loads existing Modelica results from a previous simulation.

        The .mat file from a previous simulation is loaded and stored in the
        playground state. The intended behaviour is that for the following
        tasks with post-processing and plotting there should be no difference
        if a total bim2sim plugin run is performed or the existing results are
        loaded. Therefore, we load the additional information like what space
        are aggregated from the tz_mapping.json file.

        Returns:
            teaser_mat_result_paths: path to simulation result file
            sim_results_path: path where to store the plots (currently with
          simulation results, maybe change this? #TODO
            tz_mapping: dict["Building_"<space_guid>": space information] that
                is needed for later plotting
        """
        teaser_mat_result_paths = {}
        regex = re.compile("[^a-zA-z0-9]")
        model_export_name = regex.sub("", self.prj_name)
        model_dir = self.paths.export / 'TEASER' / 'Model' / model_export_name
        sub_dirs = [item for item in model_dir.iterdir() if
                    item.is_dir() and item.name != "Resources"]
        sim_results_path = (self.paths.export / 'TEASER' / 'SimResults' /
                            model_export_name)
        # load bldg names via directory structure and store as results_paths
        for sub_dir in sub_dirs:
            bldg_name = sub_dir.name
            teaser_mat_result_paths[bldg_name] = (
                    sim_results_path / bldg_name / "resultFile.mat")
        # TODO remove this and docstring when deserilization is completed
        # load tz_mapping from existing project
        with open(self.paths.export / "tz_mapping.json", 'r') as json_file:
            tz_mapping = json.load(json_file)
        return teaser_mat_result_paths, sim_results_path, tz_mapping
