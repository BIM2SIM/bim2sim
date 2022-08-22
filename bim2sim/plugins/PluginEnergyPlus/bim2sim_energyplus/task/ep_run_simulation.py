import subprocess

from bim2sim.decision import BoolDecision, DecisionBunch
from bim2sim.task.base import ITask


class RunEnergyPlusSimulation(ITask):
    reads = ('idf', )

    def run(self, workflow, idf):
        # subprocess.run(['energyplus', '-x', '-c', '--convert-only', '-d', self.paths.export, idf.idfname])
        run_decision = BoolDecision(
            question="Do you want to run the full energyplus simulation"
                     " (annual, readvars)?",
            global_key='EnergyPlus.FullRun')
        yield DecisionBunch([run_decision])
        ep_full = run_decision.value
        design_day = False
        if not ep_full:
            design_day = True
        output_string = str(self.paths.export / 'EP-results/')
        idf.run(output_directory=output_string, readvars=ep_full, annual=ep_full, design_day=design_day)
        workflow.simulated = True
        self.logger.info(f"Simulation successfully finished.")
        # if ep_full:
        #     PostprocessingUtils._visualize_results(csv_name=self.paths.export / 'EP-results/eplusout.csv')