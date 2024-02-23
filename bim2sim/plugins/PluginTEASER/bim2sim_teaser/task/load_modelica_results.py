import json
import re
from pathlib import Path

from ebcpy import DymolaAPI

import bim2sim
from bim2sim.tasks.base import ITask


class LoadModelicaResults(ITask):
    """Load existing results, run() method holds detailed information."""
    touches = ('bldg_names', 'sim_results_path')

    def run(self):
        """Loads existing Modelica results from a previous simulation.

        The .mat file from a previous simulation is loaded and stored in the
        playground state. The intended behaviour is that for the following
        tasks with post-processing and plotting there should be no difference
        if a total bim2sim plugin run is performed or the existing results are
        loaded.

        Returns:
            bldg_names: list of building names
            sim_results_path: path where to store the plots
        """
        teaser_mat_result_paths = {}
        regex = re.compile("[^a-zA-z0-9]")
        model_export_name = regex.sub("", self.prj_name)
        model_dir = self.paths.export / 'TEASER' / 'Model' / model_export_name
        sub_dirs = [item for item in model_dir.iterdir() if
                    item.is_dir() and item.name != "Resources"]
        sim_results_path = (self.paths.export / 'TEASER' / 'SimResults' /
                            model_export_name)
        # load bldg names via directory structure and store them
        bldg_names = [sub_dir.name for sub_dir in sub_dirs]
        return bldg_names, sim_results_path
