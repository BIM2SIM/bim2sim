import unittest
from pathlib import Path

import bim2sim
from bim2sim.kernel.decision.console import ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import LOD, IFCDomain, ZoningCriteria


class IntegrationBaseTEASER(IntegrationBase):
    def model_domain_path(self) -> str:
        return 'arch'


class TestIntegrationTEASER(IntegrationBaseTEASER, unittest.TestCase):
    def test_run_kitoffice_spaces_medium_layers_low(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = (2015,)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_kitoffice_spaces_low_layers_low(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc_names = {IFCDomain.arch:  'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        answers = (2015, )
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_DH_spaces_medium_material_low(self):
        """Test DigitalHub IFC"""
        ifc_names = {IFCDomain.arch:  'FM_ARC_DigitalHub_with_SB_neu.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
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
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    # @unittest.skip('Done in regression tests')
    def test_run_kitfzkhaus_spaces_low_layers_low(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.combined_single_zone
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project export did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_ERC_Full(self):
        """Test ERC Main Building"""
        ifc_names = {IFCDomain.arch:  'ERC_Mainbuilding_Arch.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.individual_spaces
        project.sim_settings.layers_and_materials = LOD.full
        answers = ("Kitchen in non-residential buildings",
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

    @unittest.skip('Skip because takes to long in CI')
    def test_ERC_Medium(self):
        """Test ERC Main Building"""
        ifc_names = {IFCDomain.arch:  'ERC_Mainbuilding_Arch.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    # @unittest.skip('Skip because takes to long in CI')
    def test_ERC_Low(self):
        """Test ERC Main Building"""
        ifc_names = {IFCDomain.arch:  'ERC_Mainbuilding_Arch.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('Skip because is covered in Regression tests')
    def test_run_kitfzkhaus_spaces_medium_layers_low(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitfzkhaus_spaces_medium_layers_full(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.layers_and_materials = LOD.full
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = ('vertical_core_brick_700',
                   'solid_brick_h',)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitoffice_spaces_medium_layers_full(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc_names = {IFCDomain.arch:  'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.layers_and_materials = LOD.full
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = (2015, 'concrete_CEM_II_BS325R_wz05', 'clay_brick',
                   'Concrete_DK',)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitfzkhaus_spaces_full_layers_full(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.layers_and_materials = LOD.full
        project.sim_settings.zoningCriteria = ZoningCriteria.individual_spaces
        answers = (True, 'solid_brick_h', True, 'hardwood', True,
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
        ifc_names = {IFCDomain.arch:  'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.individual_spaces
        project.sim_settings.layers_and_materials = LOD.full
        answers = ('Glas', True, 'glas_generic', 500, 1.5, 0.2,
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
        ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus.ifc'}
        # ifc_names = {IFCDomain.arch:  'AC20-Institute-Var-2.ifc'
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.individual_spaces
        # answers = ('Glas', True, 'generic', 500, 1.5, 0.2,
        #            True, 'air_layer_DK', 'sandstone', True, 'lime',
        #            'lime_sandstone_1', True, 'aluminium', 0.1, True,
        #            'Concrete_DK', 2015, "heavy",
        #            1, 'Beton', 'Light_Concrete_DK', 1, 'Door', 1, 'Beton', 1,
        #            'Beton', 1, 'fenster', 'Glas1995_2015AluoderStahlfensterWaer'
        #                                   'meschutzverglasungzweifach', 1,
        #            'Door', 1, 'Beton', 1,
        #            'Beton', *(1,) * 8)
        answers_haus = ('Kitchen - preparations, storage', True,
                        'solid_brick_h', True, 'hard', 'hardwood', True,
                        'DKConcrete_DK', 'light', 'DK', 'heavy', 1, 'Door', 1,
                        'Brick', 'brick_H', 'EnEv', *(1,) * 8)

        ConsoleDecisionHandler().handle(project.run(), project.loaded_decisions)

    @unittest.skip("just with no internet test")
    def test_run_kitfzkhaus_spaces_medium_layers_full_no_translator(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.layers_and_materials = LOD.full
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = ('Kitchen - preparations, storage', True,
                   'solid_brick_h', True, None, 'wood', 'hardwood', 'concrete',
                   True, 'Concrete_DK', 'concrete', True, 'Light_Concrete_DK',
                   "heavy", 1, ' Door', 1, 'Brick', 'brick_H', "EnEv",
                   *(1,) * 8,)
        ConsoleDecisionHandler().handle(project.run(), project.loaded_decisions)

        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
