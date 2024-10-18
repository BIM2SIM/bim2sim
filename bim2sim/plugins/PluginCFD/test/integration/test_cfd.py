import os
import unittest
import warnings

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import IFCDomain


class IntegrationBaseCFD(IntegrationBase):
    def tearDown(self):
        super().tearDown()

    def model_domain_path(self) -> str:
        return 'arch'


class TestIntegrationCFD(IntegrationBaseCFD, unittest.TestCase):

    # @unittest.skip("")
    def test_run_kitfzkhaus_spaces_low_layers_low(self):
        """Run project with AC20-FZK-Haus.ifc"""
        if os.name == 'posix':  # only linux
            ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
            project = self.create_project(ifc_names, 'CFD')
            answers = ("--cfd", 8)
            handler = DebugDecisionHandler(answers)
            for decision, answer in handler.decision_answer_mapping(
                    project.run()):
                decision.value = answer
            self.assertEqual(0, handler.return_value,
                             "Project did not finish successfully.")
        else:
            warnings.warn("Current OS not linux. This test will be skipped.")
