import json
import re
from pathlib import Path

from geomeppy import IDF

import bim2sim
from bim2sim.tasks.base import ITask


class LoadEnergyPlusResults(ITask):
    """Load existing results, run() method holds detailed information."""
    touches = ('sim_results_path', 'idf')

    def run(self):
        """Loads existing EnergyPlus results from a previous simulation.

        The idf file from a previous simulation is loaded and stored in the
        playground state. The intended behaviour is that for the following
        tasks with post-processing and plotting there should be no difference
        if a total bim2sim plugin run is performed or the existing results are
        loaded.

        Returns:
            sim_results_path: path where to store the plots
            idf: loaded EnergyPlus input file
        """
        model_export_name = self.prj_name
        sim_results_path = (self.paths.export / 'EnergyPlus' / 'SimResults')
        # load bldg names via directory structure and store them
        ep_install_path = self.playground.sim_settings.ep_install_path
        # set the plugin path of the PluginEnergyPlus within the BIM2SIM Tool
        # set Energy+.idd as base for new idf
        IDF.setiddname(ep_install_path / 'Energy+.idd')
        idf = IDF(sim_results_path.as_posix() + f"/{model_export_name}"
                                                f"/{model_export_name}.idf")
        return sim_results_path, idf
