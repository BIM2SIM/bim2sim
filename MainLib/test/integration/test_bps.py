import unittest
import bim2sim
from bim2sim import workflow
from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase


class IntegrationBaseTEASER(IntegrationBase):
    def tearDown(self):
        super().tearDown()


class TestIntegrationTEASER(IntegrationBaseTEASER, unittest.TestCase):

    def test_run_kitfzkhaus_spaces_low_layers_low(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        used_workflow = workflow.BPSOneZoneAggregatedLayersLow()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Kitchen - preparations, storage', 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_kitoffice_spaces_low_layers_low(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc = 'AC20-Institute-Var-2.ifc'
        used_workflow = workflow.BPSOneZoneAggregatedLayersLow()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 2015, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach')
        handler = DebugDecisionHandler(answers)
        handler.handle(project.run())
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_kitfzkhaus_spaces_medium_layers_low(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        used_workflow = workflow.BPSMultiZoneCombinedLayersLow()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Kitchen - preparations, storage',
                   'heavy', 'EnEv', 'by_all_criteria', False)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_kitoffice_spaces_medium_layers_low(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc = 'AC20-Institute-Var-2.ifc'
        used_workflow = workflow.BPSMultiZoneCombinedLayersLow()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 2015, 'heavy', 'EnEv', 'by_all_criteria', False)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_kitfzkhaus_spaces_medium_layers_full(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        used_workflow = workflow.BPSMultiZoneCombinedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Kitchen - preparations, storage', True,
                   'solid_brick_h', True, 'hardwood', True,
                   'Concrete_DK', True, 'Light_Concrete_DK', 'heavy', 1,
                   'Door', 1, 'Brick', 'brick_H', 'EnEv',
                   *(1,) * 8, 'by_all_criteria', False)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_kitoffice_spaces_medium_layers_full(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc = 'AC20-Institute-Var-2.ifc'
        used_workflow = workflow.BPSMultiZoneCombinedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Glas', True, 'glas_generic', 500, 1.5, 0.2,
                   True, 'air_layer', 'sandstone', True, 'belgian_brick',
                   0.1, True, 'Concrete_DK', 2015, 'heavy', 1, 'Beton',
                   'Light_Concrete_DK', 1, 'Beton', 1, 'Door',
                   1, 'Beton', *(1,) * 8, 'by_all_criteria', False)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_kitfzkhaus_spaces_full_layers_full(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Kitchen - preparations, storage', True,
                   'solid_brick_a', True, 'hardwood', True,
                   'Light_Concrete_DK', True, 'Concrete_DK', 'heavy', 1, 'Door',
                   1, 'Brick', 'brick_H', 'EnEv',
                   *(1,) * 8)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_kitoffice_spaces_full_layers_full(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc = 'AC20-Institute-Var-2.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Glas', True, 'glas_generic', 500, 1.5, 0.2, True, 'air_layer', 'sandstone', True, 'belgian_brick',
                   0.1, True, 'Concrete_DK', 2015, 'heavy', 1, 'Beton', 'Light_Concrete_DK', 1, 'Beton', 1, 'Door', 1,
                   'Beton', *(1,) * 8)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")


class TestIntegrationAixLib(unittest.TestCase):
    pass
