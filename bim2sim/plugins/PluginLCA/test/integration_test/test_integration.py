import unittest
from pathlib import Path

from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase


class IntegrationBaseLCA(IntegrationBase):
    def model_domain_path(self) -> str:
        return 'BPS'


class TestIntegrationLCA(IntegrationBaseLCA, unittest.TestCase):
    def test_run_kitinstitute_lca(self):
        """Run project with AC20-Institute-Var-2..ifc"""
        ifc = 'AC20-Institute-Var-2.ifc'
        project = self.create_project(ifc, 'LCA')
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_ERC_lca(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'ERC_Mainbuilding_Arch.ifc'
        project = self.create_project(ifc, 'LCA')
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
