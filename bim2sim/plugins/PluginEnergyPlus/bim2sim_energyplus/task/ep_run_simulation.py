import re
from pathlib import Path

from geomeppy import IDF

from bim2sim.tasks.base import ITask
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils


class RunEnergyPlusSimulation(ITask):
    """Run EnergyPlus simulation.

    See run function for more details.
    """
    reads = ('idf', 'sim_results_path')

    def run(self, idf: IDF, sim_results_path: Path):
        """Run EneryPlus simulation.

        This function is used to run EnergyPlus. The simulation is performed
        according to the selected simulation settings. The simulation results
        can be found under the simulation result path in the project name
        directory.

        Args:
            idf (IDF): eppy idf, EnergyPlus input file
            sim_results_path (Path): Path to simulation results.

        """
        # subprocess.run(['energyplus', '-x', '-c', '--convert-only', '-d', self.paths.export, idf.idfname])
        export_path = sim_results_path / self.prj_name
        ep_full = self.playground.sim_settings.run_full_simulation
        design_day = False
        if not ep_full:
            design_day = True

        idf.run(output_directory=export_path, readvars=True, annual=ep_full,
                design_day=design_day)
        self.playground.sim_settings.simulated = True
        self.logger.info(f"Simulation successfully finished.")
        if ep_full:
            webtool_df_ep = PostprocessingUtils.export_df_for_webtool(
                csv_name=export_path / 'eplusout.csv')
            self.logger.info(f"Exported dataframe for postprocessing.")
        else:
            self.logger.info(f"No dataframe output for postprocessing "
                             "generated. Please set the workflow setting "
                             "'run_full_simulation' to True to enable the "
                             "postprocessing output.")
        self.logger.info(f"You can find the results under "
                         f"{str(export_path)}")
