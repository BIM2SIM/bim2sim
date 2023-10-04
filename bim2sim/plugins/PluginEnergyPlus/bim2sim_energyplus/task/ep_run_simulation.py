from bim2sim.tasks.base import ITask
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils


class RunEnergyPlusSimulation(ITask):
    reads = ('idf', )

    def run(self, idf):
        # subprocess.run(['energyplus', '-x', '-c', '--convert-only', '-d', self.paths.export, idf.idfname])
        ep_full = self.playground.sim_settings.run_full_simulation
        design_day = False
        if not ep_full:
            design_day = True
        output_string = str(self.paths.export / 'EP-results/')
        idf.run(output_directory=output_string, readvars=True, annual=ep_full,
                design_day=design_day)
        self.playground.sim_settings.simulated = True
        self.logger.info(f"Simulation successfully finished.")
        if ep_full:
            webtool_df_ep = PostprocessingUtils.export_df_for_webtool(
                csv_name=self.paths.export / 'EP-results/eplusout.csv')
            self.logger.info(f"Exported dataframe for postprocessing.")
        else:
            self.logger.info(f"No dataframe output for postprocessing "
                             "generated. Please set the workflow setting "
                             "'run_full_simulation' to True to enable the "
                             "postprocessing output.")
