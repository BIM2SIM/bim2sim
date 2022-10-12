"""Create fresh TEASER regression results.

This file holds setups to create new regression results for regression tests.

"""

from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.plugins.PluginTEASER.test.regression_test.test_regression\
    import RegressionTestTEASER
from bim2sim import workflow


class CreateRegressionResultsTEASER(RegressionTestTEASER):
    def create_regression_results_FZKHaus(self):
        """Create fresh regression results for the AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus_2.ifc'
        used_workflow = workflow.BPSOneZoneAggregatedLayersLow()
        used_workflow.dymola_simulation = False
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.create_regression_setup(tolerance=1E-3, batch_mode=False)
        self.create_regression_results()


if __name__ == '__main__':
    my_reg = CreateRegressionResultsTEASER()
    my_reg.create_regression_results_FZKHaus()
