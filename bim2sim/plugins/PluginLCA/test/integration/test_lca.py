import unittest

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import IFCDomain


class IntegrationBaseLCA(IntegrationBase):
    def model_domain_path(self) -> str:
        return 'arch'

    def set_test_weather_file(self):
        """Set the weather file path."""
        self.project.sim_settings.weather_file_path_modelica = (
                self.test_resources_path() /
                'weather_files/DEU_NW_Aachen.105010_TMYx.mos')

class TestIntegrationLCA(IntegrationBaseLCA, unittest.TestCase):
    def test_run_kitinstitute_lca(self):
        """Run project with AC20-Institute-Var-2..ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'LCA')
        answers = (2005,)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_ERC_lca(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'ERC_Mainbuilding_Arch.ifc'}
        project = self.create_project(ifc_names, 'LCA')
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
