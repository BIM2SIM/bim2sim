import json
import re
from pathlib import Path

from ebcpy import DymolaAPI

import bim2sim
from bim2sim.tasks.base import ITask


class LoadModelicaResults(ITask):
    touches = ('teaser_mat_result_paths', 'sim_results_path', 'tz_mapping')

    def run(self):
        teaser_mat_result_paths = {}
        model_dir = self.paths.export / 'TEASER' / 'Model' / self.prj_name
        sub_dirs = [item for item in model_dir.iterdir() if
                    item.is_dir() and item.name != "Resources"]
        sim_results_path = (self.paths.export / 'TEASER' / 'SimResults' /
                            self.prj_name)
        # load bldg names via directory structure and store as results_paths
        for sub_dir in sub_dirs:
            bldg_name = sub_dir.name
            teaser_mat_result_paths[bldg_name] = (
                    sim_results_path / bldg_name / "resultFile.mat")
        # load tz_mapping from existing project
        with open(self.paths.export / "tz_mapping.json", 'r') as json_file:
            tz_mapping = json.load(json_file)
        return teaser_mat_result_paths, sim_results_path, tz_mapping


