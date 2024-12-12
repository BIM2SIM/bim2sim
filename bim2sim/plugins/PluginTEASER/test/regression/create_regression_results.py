"""Create fresh TEASER regression results.

This file holds setups to create new regression results for regression tests.

"""
from pathlib import Path

import bim2sim
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.plugins.PluginTEASER.test.regression.test_teaser\
    import RegressionTestTEASER
from bim2sim.utilities.types import IFCDomain, ZoningCriteria


class CreateRegressionResultsTEASER(RegressionTestTEASER):
    def create_regression_results_fzkhaus(self):
        """Create fresh regression results for the AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = (
            ZoningCriteria.combined_single_zone)
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.create_regression_setup(tolerance=1E-3, batch_mode=False)
        self.create_regression_results()

    def create_regression_results_digitalhub(self):
        """Create fresh regression results for
         FM_ARC_DigitalHub_with_SB_neu.ifc"""
        ifc_names = {IFCDomain.arch:  'FM_ARC_DigitalHub_with_SB_neu.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = (
            ZoningCriteria.combined_single_zone)
        project.sim_settings.prj_use_conditions = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "UseConditionsFM_ARC_DigitalHub.json"
        project.sim_settings.prj_custom_usages = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "customUsagesFM_ARC_DigitalHub_with_SB_neu.json"
        answers = ('Other', *(None,)*12, 2015)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.create_regression_setup(tolerance=1E-3, batch_mode=False)
        self.create_regression_results()


if __name__ == '__main__':
    my_reg = CreateRegressionResultsTEASER()
    my_reg.create_regression_results_fzkhaus()
    my_reg.create_regression_results_digitalhub()
