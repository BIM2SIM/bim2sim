import unittest
from bim2sim import workflow
from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase
from bim2sim.decision.console import ConsoleDecisionHandler


class IntegrationBaseTEASER(IntegrationBase):
    def tearDown(self):
        super().tearDown()


class TestIntegrationTEASER(IntegrationBaseTEASER, unittest.TestCase):

    @unittest.skip('skip layers_full test until new answers are created')
    def test_ERC_Full(self):
        """Test ERC Main Building"""
        ifc = 'ERC_Mainbuilding_Arch.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = ('Autodesk Revit 2020 (DEU)', True, True,
                   "Kitchen in non-residential buildings",
                   "Library - reading room",
                   "MultiUseComputerRoom",
                   "Laboratory",
                   "Parking garages (office and private usage)",
                   "Stock, technical equipment, archives", True,
                   "Air_layer_DK", "perlite", True, "heavy", 1,
                   "beton", "Concrete_DK", "EnEv", 1, 0.3,
                   "beton", 1, "beton", 1, "beton", *(1,) * 8)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_ERC_Medium(self):
        """Test ERC Main Building"""
        ifc = 'ERC_Mainbuilding_Arch.ifc'
        used_workflow = workflow.BPSMultiZoneAggregatedLayersLow()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = ('Autodesk Revit 2020 (DEU)', True, True,
                   "Kitchen in non-residential buildings",
                   "Library - reading room",
                   "Library - reading room",
                   "Laboratory",
                   "Parking garages (office and private usage)",
                   "Stock, technical equipment, archives",
                   'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach',
                   'by_all_criteria')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_ERC_Low(self):
        """Test ERC Main Building"""
        ifc = 'ERC_Mainbuilding_Arch.ifc'
        used_workflow = workflow.BPSOneZoneAggregatedLayersLow()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = ('Autodesk Revit 2020 (DEU)', True, True,
                   "Kitchen in non-residential buildings",
                   "Library - reading room",
                   "Library - reading room",
                   "Laboratory",
                   "Parking garages (office and private usage)",
                   "Stock, technical equipment, archives",
                   'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

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

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitfzkhaus_spaces_medium_layers_full(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        used_workflow = workflow.BPSMultiZoneCombinedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Kitchen - preparations, storage', True,
                   'solid_brick_h', True, 'hardwood', True,
                   'Concrete_DK', True, 'Light_Concrete_DK',
                   'heavy', 1, 'Door', 1, 'Brick', 'solid_brick_h', *(1,) * 8,
                   'EnEv', 'by_all_criteria')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitoffice_spaces_medium_layers_full(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc = 'AC20-Institute-Var-2.ifc'
        used_workflow = workflow.BPSMultiZoneCombinedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Glas', True, 'glas_generic', 500, 1.5, 0.2,
                   True, 'air_layer', 'sandstone', True, 'lime_sandstone_1',
                   True, 'aluminium', 0.1, True, 'Concrete_DK', 2015,
                   "heavy", 1, 'Beton', 'Light_Concrete_DK', 1, 'Door', 1,
                   'Beton', 1, 'Beton', 1, 'fenster', 'Glas1995_2015Aluoder'
                   'StahlfensterWaermeschutzverglasungzweifach', 1, 'Door',
                   1, 'Beton', 1, 'Beton', *(1,) * 8, 'by_all_criteria')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitfzkhaus_spaces_full_layers_full(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Kitchen - preparations, storage', True,
                   'solid_brick_h', True, 'hardwood', True,
                   'Concrete_DK', True, 'Light_Concrete_DK',
                   'heavy', 1, 'Door', 1, 'Brick', 'solid_brick_h', 'EnEv',
                   *(1,) * 8)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitoffice_spaces_full_layers_full(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc = 'AC20-Institute-Var-2.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Glas', True, 'glas_generic', 500, 1.5, 0.2,
                   True, 'air_layer', 'sandstone', True, 'lime_sandstone_1',
                   True, 'aluminium', 0.1, True, 'Concrete_DK', 2015,
                   "heavy", 1, 'Beton', 'Light_Concrete_DK', 1, 'Door', 1,
                   'Beton', 1, 'Beton', 1, 'fenster', 'Glas1995_2015Aluoder'
                   'StahlfensterWaermeschutzverglasungzweifach', 1, 'Door',
                   1, 'Beton', 1, 'Beton', *(1,) * 8)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('just available to console test')
    def test_live_decisions(self):
        ifc = 'AC20-FZK-Haus.ifc'
        # ifc = 'AC20-Institute-Var-2.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Glas', True, 'generic', 500, 1.5, 0.2,
                   True, 'air_layer_DK', 'sandstone', True, 'lime',
                   'lime_sandstone_1', True, 'aluminium', 0.1, True,
                   'Concrete_DK', 2015, "heavy",
                   1, 'Beton', 'Light_Concrete_DK', 1, 'Door', 1, 'Beton', 1,
                   'Beton', 1, 'fenster', 'Glas1995_2015AluoderStahlfensterWaer'
                                          'meschutzverglasungzweifach', 1,
                   'Door', 1, 'Beton', 1,
                   'Beton', *(1,) * 8)
        answers_haus = (True, True, 'Kitchen - preparations, storage', True,
                        'solid_brick_h', True, 'hard', 'hardwood', True, 'DK'
                                                                         'Concrete_DK',
                        'light', 'DK', 'heavy', 1, 'Door', 1,
                        'Brick', 'brick_H', 'EnEv', *(1,) * 8)

        ConsoleDecisionHandler().handle(project.run(), project.loaded_decisions)

    @unittest.skip("just with no internet test")
    def test_run_kitfzkhaus_spaces_medium_layers_full_no_translator(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        used_workflow = workflow.BPSMultiZoneCombinedLayersFull()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Kitchen - preparations, storage', True,
                   'solid_brick_h', True, None, 'wood', 'hardwood', 'concrete',
                   True, 'Concrete_DK', 'concrete', True, 'Light_Concrete_DK',
                   "heavy", 1, ' Door', 1, 'Brick', 'brick_H', "EnEv",
                   *(1,) * 8, 'by_all_criteria')
        ConsoleDecisionHandler().handle(project.run(), project.loaded_decisions)

        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_proxy_kitfzkhaus_spaces_low_layers_low(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'proxy_test6_PSet_Colors.ifc'
        used_workflow = workflow.BPSOneZoneAggregatedLayersLow()
        project = self.create_project(ifc, 'TEASER', used_workflow)
        answers = (True, True, 'Kitchen - preparations, storage', 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

class TestIntegrationAixLib(unittest.TestCase):
    pass
