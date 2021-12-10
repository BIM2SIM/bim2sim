import unittest
import os

from bim2sim import workflow
from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase


class IntegrationBaseCFD(IntegrationBase):
    def tearDown(self):
        super().tearDown()


class TestIntegrationCFD(IntegrationBaseCFD, unittest.TestCase):

    # @unittest.skip("")
    def test_run_kitfzkhaus_spaces_low_layers_low(self):
        if os.name == 'Linux':
            """Run project with AC20-FZK-Haus.ifc"""
            ifc = 'AC20-FZK-Haus.ifc'
            used_workflow = workflow.CFDWorkflowDummy()
            project = self.create_project(ifc, 'CFD', used_workflow)
            answers = ("--cfd", 8)
            handler = DebugDecisionHandler(answers)
            for decision, answer in handler.decision_answer_mapping(
                    project.run()):
                decision.value = answer
            self.assertEqual(0, handler.return_value,
                             "Project did not finish successfully.")