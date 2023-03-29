import subprocess

from bim2sim.decision import BoolDecision, DecisionBunch
from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import create_plotly_graphs_from_df


class RunEnergyPlusSimulation(ITask):
    reads = ('idf', )

    def run(self, workflow, idf):
        # subprocess.run(['energyplus', '-x', '-c', '--convert-only', '-d', self.paths.export, idf.idfname])
        ep_full = workflow.run_full_simulation
        design_day = False
        if not ep_full:
            design_day = True
        output_string = str(self.paths.export / 'EP-results/')
        idf.run(output_directory=output_string, readvars=True, annual=ep_full,
                design_day=design_day)
        workflow.simulated = True
        self.logger.info(f"Simulation successfully finished.")
        # if ep_full:
        #     PostprocessingUtils._visualize_results(csv_name=self.paths.export / 'EP-results/eplusout.csv')
        df = self.save_to_dataframe()
        create_plotly_graphs_from_df(df)

    def save_to_dataframe(self):
        # todo #497
        df = None
        pass
        return df
