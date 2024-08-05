# TODO
"""Create fresh AixLib regression results.

This file holds setups to create new regression results for regression tests.

"""

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.plugins.PluginTEASER.test.regression.test_teaser\
    import RegressionTestTEASER
from bim2sim.utilities.types import IFCDomain


class CreateRegressionResultsTEASER(RegressionTestTEASER):
    def create_regression_results_FZKHaus(self):
        """Create fresh regression results for the AC20-FZK-Haus.ifc"""
        # TODO
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'AixLib')
        # FZK Haus as correct IFC types but wrong SB external/internal
        # information
        project.sim_settings.fix_type_mismatches_with_sb = False
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.create_regression_setup(tolerance=1E-3, batch_mode=False)
        self.create_regression_results()


if __name__ == '__main__':
    my_reg = CreateRegressionResultsTEASER()
    my_reg.create_regression_results_FZKHaus()
