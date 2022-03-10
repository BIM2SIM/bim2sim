import unittest
from pathlib import Path

from bim2sim import workflow
from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim_teaser.test.integration_test_setup import \
    IntegrationBaseTeaserInteractive

EXAMPLE_PATH = Path(__file__).parent.parent.parent.parent.parent / 'ExampleFiles'
RESULT_PATH = Path(__file__).parent.parent.parent.parent.parent / 'ResultFiles'


class IntegrationBaseTEASER(IntegrationBaseTeaserInteractive, unittest.TestCase):

    def test_ap7_run_kitfzkhaus_spaces_medium_layers_low(self):
        """Run project with AC20-FZK-Haus.ifc with with modified
        materials and one zone aggregation."""
        ifc = EXAMPLE_PATH / 'AC20-FZK-Haus.ifc'
        used_workflow = workflow.BPSMultiZoneAggregatedLayersLowSimulation()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach',
                   'by_all_criteria')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_ap7_run_DigitalHub_spaces_low_layers_low(self):
        """Run project with FM_ARC_DigitalHub_fixed002.ifc with modified
        materials and one zone aggregation."""
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_fixed002.ifc'
        used_workflow = workflow.BPSMultiZoneAggregatedLayersLowSimulation()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = ('ARCHICAD-64', *(None,) * 150, True, True,
                   2015, 'light', 'Waermeschutzverglasung, dreifach')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_ap7_run_DigitalHub_spaces_medium_layers_low(self):
        """Run project with FM_ARC_DigitalHub_fixed002.ifc with modified
        materials and one multizone aggregation."""
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_fixed002.ifc'
        used_workflow = workflow.BPSMultiZoneAggregatedLayersLowSimulation()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = ('ARCHICAD-64', *(None,) * 150, True, True,
                   2015, 'heavy', 'Waermeschutzverglasung, dreifach',
                   'by_all_criteria')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_ap7_run_DigitalHub_spaces_full_layers_low(self):
        """Run project with FM_ARC_DigitalHub_fixed002.ifc with adding
        material enrichment and without zone aggregation."""
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_fixed002.ifc'
        used_workflow = workflow.BPSMultiZoneAggregatedLayersLowSimulation()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = ('ARCHICAD-64', *(None,) * 150, True, True,
                   2015, 'light', 'Waermeschutzverglasung, dreifach')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
