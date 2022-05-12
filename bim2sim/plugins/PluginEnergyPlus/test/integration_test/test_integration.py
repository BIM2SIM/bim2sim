import sys
import unittest
import tempfile
from shutil import copyfile, copytree, rmtree
from pathlib import Path

import os

from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase
from bim2sim.project import Project
from bim2sim import workflow


# raise unittest.SkipTest("Integration tests not reliable for automated use")

EXAMPLE_PATH = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent.parent / 'ExampleFiles'
RESULT_PATH = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent.parent / 'ResultFiles'
DEBUG_ENERGYPLUS = True


class IntegrationBaseEP(IntegrationBase):
    # HACK: We have to remember stderr because eppy resets it currently.
    def setUp(self):
        self.old_stderr = sys.stderr
        self.working_dir = os.getcwd()
        super().setUp()

    def tearDown(self):
        if DEBUG_ENERGYPLUS: # copy EP-results to home directory for further debugging.
            if not os.path.exists(Path.home() / 'idf'):
                os.mkdir(Path.home() / 'idf')
            ifc_name = str(os.listdir(self.project.paths.ifc)[0].split('.ifc')[0])
            temp_dir = Path(self.project.paths.export) / "EP-results/"
            debug_dir = Path.home() / 'idf' / Path(ifc_name + '_EP-results/')
            if os.path.exists(debug_dir):
                rmtree(debug_dir)
            copytree(temp_dir, debug_dir)
            try:
                copyfile(Path(self.project.paths.export)
                         / Path(ifc_name + "_combined_STL.stl"),
                         str(debug_dir) + '/' + str(ifc_name) + "_combined_STL.stl")
                copyfile(Path(self.project.paths.export)
                         / Path(ifc_name + "_space_combined_STL.stl"),
                         str(debug_dir) + '/' + str(ifc_name) + "_space_combined_STL.stl")
            except:
                print('No STL for CFD found. ')
            copyfile(str(debug_dir) + "/eplusout.expidf",
                     str(debug_dir) + "/eplusout.idf")
        os.chdir(self.working_dir)
        sys.stderr = self.old_stderr
        super().tearDown()

    def create_project(self, ifc_path: str, plugin: str, workflow: workflow.Workflow = None):
        """create project in temporary directory which is cleaned automatically after test.

        :param plugin: Project plugin e.g. 'hkesim', 'aixlib', ...
        :param ifc: name of ifc file located in dir TestModels"""

        # path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        # ifc_path = os.path.normpath(os.path.join(path_base, rel_ifc_path))
        self.project = Project.create(tempfile.TemporaryDirectory(prefix='bim2sim_').name, ifc_path=ifc_path,
                                      plugin=plugin, workflow=workflow)
        return self.project


class TestEPIntegration(IntegrationBaseEP, unittest.TestCase):
    """
    Integration tests for multiple IFC example files.
    Tested are both original IFC files and files from Eric Fichter's Space Boundary Generation tool.
    """

    # @unittest.skip("")
    def test_base_01_FZK_design_day(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = EXAMPLE_PATH / 'AC20-FZK-Haus.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = (True, True, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, False)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value)
        #todo: fix virtual bounds (assigned to be outdoors for some reason)

    @unittest.skip("")
    def test_base_01full_FZK_design_day(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = EXAMPLE_PATH / 'AC20-FZK-Haus.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedEPfull()
        project = self.create_project(ifc, 'energyplus', used_workflow)
        answers = (True, True, True,
                   'solid_brick_a', True, 'hardwood', True,
                   'Light_Concrete_DK', True, 'Concrete_DK', "heavy", 1, 'Door',
                   1, 'Brick', 'brick_H', "EnEv", *(1,) * 8, True, True, True, False)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value)

    @unittest.skip("")
    def test_base_02_FZK_full_run(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = EXAMPLE_PATH / 'AC20-FZK-Haus.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = (True, True, 'Kitchen - preparations, storage', 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("")
    def test_base_02full_FZK_full_run(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = EXAMPLE_PATH / 'AC20-FZK-Haus.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedEPfull()
        project = self.create_project(ifc, 'energyplus', used_workflow)
        answers = (True, True, 'Kitchen - preparations, storage', True,
                   'solid_brick_a', True, 'hardwood', True,
                   'Light_Concrete_DK', True, 'Concrete_DK', "heavy", 1, 'Door',
                   1, 'Brick', 'brick_H', "EnEv", *(1,) * 8, True, True, True, True)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value)

    # @unittest.skip("")
    def test_base_03_FZK_SB_design_day(self):
        """Test IFC File from FZK-Haus (KIT) with generated Space Boundaries"""
        # ifc = RESULT_PATH / 'AC20-FZK-Haus_with_SB44.ifc'
        ifc = RESULT_PATH / 'AC20-FZK-Haus_with_SB55.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('ARCHICAD-64', True, True, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach',
                   True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("")
    def test_base_04_FZK_SB_full_run(self):
        """Test IFC File from FZK-Haus (KIT) with generated Space Boundaries"""
        # ifc = RESULT_PATH / 'AC20-FZK-Haus_with_SB44.ifc'
        ifc = RESULT_PATH / 'AC20-FZK-Haus_with_SB55.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('ARCHICAD-64', True, True, 'Single office', 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("")
    def test_base_05_KIT_Inst_design_day(self):
        """Test Original IFC File from Institute (KIT)"""

        ifc = EXAMPLE_PATH / 'AC20-Institute-Var-2.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = (True, True,  2015, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("")
    def test_base_05full_KIT_Inst_design_day(self):
        """Test Original IFC File from Institute (KIT)"""

        ifc = EXAMPLE_PATH / 'AC20-Institute-Var-2.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedEPfull()
        project = self.create_project(ifc, 'energyplus', used_workflow)
        answers = (True, True, 'Glas', True, 'glas_generic', 500, 1.5, 0.2,
                   True, 'air_layer', 'sandstone', True, 'lime_sandstone_1',
                   True, 'aluminium', 0.1, True, 'Concrete_DK', 2015, "heavy",
                   1, 'Beton', 'Light_Concrete_DK', 1, 'Beton', 1, 'Beton',
                   1, 'Door', 1, 'Beton', 1, 'Beton', *(1,) * 8, True, True, True,
                   False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("")
    def test_base_06_KIT_Inst_full_run(self):
        """Test Original IFC File from Institute (KIT)"""

        ifc = EXAMPLE_PATH / 'AC20-Institute-Var-2.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = (True, True,  2015, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("Skipped due to performance for CI")
    def test_base_07_KIT_Inst_SB_design_day(self):
        """Test IFC File from Institute (KIT) with generated Space Boundaries"""

        ifc = RESULT_PATH / 'AC20-Institute-Var-2_with_SB-1-0.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('ARCHICAD-64', True, True, 2015, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Skipped due to performance for CI")
    def test_base_08_KIT_Inst_SB_full_run(self):
        """Test IFC File from Institute (KIT) with generated Space Boundaries"""

        ifc = RESULT_PATH / 'AC20-Institute-Var-2_with_SB-1-0.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('ARCHICAD-64', True, True,  'Single office', 2015, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("Skipped due to performance for CI")
    def test_base_09_DH_design_day(self):
        """Test DigitalHub IFC"""
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_with_SB_neu.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('Autodesk Revit 2020 (DEU)', *(None,)*150, True, True, 2015, 'heavy',
                   'Waermeschutzverglasung, dreifach',
                   True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Debug Answers need to be fixed")
    def test_base_09a_DH_design_day(self): # todo: fix
        """Test DigitalHub IFC"""
        ifc = str(RESULT_PATH / 'DigitalHub_Architektur2_2020_Achse_tragend_V2.ifc')
        project = self.create_project(ifc, 'energyplus')
        answers = (*(None,)*143, True, True,
                   *('Stock, technical equipment, archives',)*8,
                   'Kitchen in non-residential buildings',
                   'Foyer (theater and event venues)',
                   *('Stock, technical equipment, archives',)*4, 'Foyer (theater and event venues)',
                   *('Stock, technical equipment, archives',)*6,
                   2015,
                   'light', 'Holzfenster, zweifach', True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Debug Answers need to be fixed")
    def test_base_09b_DH_design_day(self): # todo: fix
        """Test DigitalHub IFC"""
        ifc = str(RESULT_PATH / 'DigitalHub_Architektur2_2020_Achse_tragend_V2.ifc')
        used_workflow = workflow.BPSMultiZoneSeparatedEPfull()
        project = self.create_project(ifc, 'energyplus', used_workflow)
        answers = (*(None,)*143, True, True,
                   *('Stock, technical equipment, archives',) * 8,
                   'Kitchen in non-residential buildings',
                   'Foyer (theater and event venues)',
                   *('Stock, technical equipment, archives',) * 4, 'Foyer (theater and event venues)',
                   *('Stock, technical equipment, archives',) * 6,
                   'synthetic_resin_plaster', True, True, 'cellulose_insulation', True,
                    'air_layer', True, 'Insulation_060_DK', True,
                   'perlite_with_bitumen_280', True, 'Roofing_DK', True, True,
                   'Light_Concrete_DK', True,
                   'lightweight_concrete_Vermiculit_1100', True,
                   'natural_sand_mixed_1660', 'wool', True, 'rock_wool_100',
                   True, 'plasterboard', True, 'Insulation_036_DK', True,
                   'Concrete_DK', 'perlite', True, 'concrete', True,
                   'slag_and_GGBFS_concrete_1400', 2015, 0.8133875106928999,
                   *(0.6151880307319045,) * 4, 0.8133875106928999,
                   *(0.6634801569995639,) * 8, 0.8133875106928999,
                   0.6634801569995639, *(0.6634801569995639,) * 3,
                   *(0.6151880307319045,) * 2, 0.8133875106928999,
                   *(0.6634801569995639,) * 4, *(0.6151880307319045,) * 2,
                   'light', 'Holzfenster, zweifach', 1, 'concrete',
                   'Light_Concrete_DK',  *(1, 'concrete',)*3, *(1,)*8, True, True, True, False)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        # return_code = handler.handle(project.run())
        # self.assertEqual(0, return_code)
        self.assertEqual(0, handler.return_value)

    @unittest.skip("Skipped due to performance for CI")
    def test_base_10a_DH_low_full_run(self):
        """Test DigitalHub IFC"""
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_with_SB.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedEP()
        project = self.create_project(ifc, 'energyplus', used_workflow)
        answers = ('ARCHICAD-64', *(None,) * 150, True, True, 'Single office',
                   2015, 'light', 'Holzfenster, zweifach', True, True, True, True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Skipped due to performance for CI")
    def test_base_10b_DH_full_full_run(self):
        """Test DigitalHub IFC"""
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_with_SB.ifc'
        used_workflow = workflow.BPSMultiZoneSeparatedEPfull()
        project = self.create_project(ifc, 'energyplus', used_workflow)
        answers = ('ARCHICAD-64', *(None,) * 150, True, True,
                   *('Stock, technical equipment, archives',) * 2,
                   'Single office',
                   *('Stock, technical equipment, archives',) * 2,
                   'Kitchen in non-residential buildings',
                   'Foyer (theater and event venues)',
                   *('Stock, technical equipment, archives',) * 3,
                   True, 'synthetic_resin_plaster', True,
                   'cellulose_insulation', True, 'air_layer',
                   True, 'Insulation_036_DK', 0.5,
                   True, 'perlite_with_bitumen_280', True, 'Roofing_DK', True,
                   True, 'lightweight_concrete_Vermiculit_1100', True,
                   'Light_Concrete_DK', True,
                   'natural_pumice', 0.93, 'rock_wool_100', True,
                   True, 'plasterboard', True,
                   'Insulation_060_DK',
                   'Concrete_DK', True, 'Concrete_DK', 'Trittschall', True, 2015,
                   *(0.689655172413793,) * 8, 'light', 'Holzfenster, zweifach', 1,
                   'concrete', 'Light_Concrete_DK', 1, 0.5,
                   'concrete', 1, 'concrete', 1, 'concrete',
                   *(0.7,) * 4,
                   0.13, 0.1, 0.1, 0.04, True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Skipped, issue with inner loop algorithm") # todo: find bug related to inner_loop_remover
    def test_base_11_KHH_design_day(self):
        """Test KIT KHH 3 storey IFC"""
        ifc = EXAMPLE_PATH / 'KIT-EDC.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('ARCHICAD-64', True, True, *('Single office',)*12, 2015,'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Skipped due to performance for CI")
    def test_base_12_KHH_full_run(self):
        """Test KIT KHH 3 storey IFC"""
        ifc = EXAMPLE_PATH / 'KIT-EDC.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('ARCHICAD-64', True, True, *('Single office',)*12, 2015,'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("Skipped due to performance for CI")
    def test_base_13_EDC_SB_design_day(self):
        """Test KIT KHH 3 storey IFC with generated Space Boundaries"""
        ifc = RESULT_PATH / 'KIT-EDC_with_SB.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('ARCHICAD-64', 'ARCHICAD-64', True, True, 2015, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach',
                   True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Skipped due to performance for CI")
    def test_base_14_EDC_SB_full_run(self):
        """Test KIT KHH 3 storey IFC with generated Space Boundaries"""
        ifc = RESULT_PATH / 'KIT-EDC_with_SB.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('ARCHICAD-64', True, True, 'Single office', 2015, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Not fully implemented yet")
    def test_base_17_ERC_design_day(self):
        """Test ERC Main Building"""
        ifc = EXAMPLE_PATH / '26.05space_modified.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('Autodesk Revit 2020 (DEU)', True, True, *('Single office',)*5, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Not fully implemented yet")
    def test_base_19_linear_SB_design_day(self):
        """Test Linear Building with generated Space Boundaries"""
        # ifc = RESULT_PATH / 'Office_Building_Architectural_IFC_export_with_SB.ifc'
        ifc = RESULT_PATH / 'Linear_V01.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('Autodesk Revit 2020 (DEU)', 'Autodesk Revit 2020 (DEU)', True, True, *('Single office',)*71, 2015, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', True, True, True, False)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value)

    @unittest.skip("Not fully implemented yet")
    def test_base_20_olabarri_design_day(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = EXAMPLE_PATH / 'Olabarri_49.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('Other', True, True, *("Single office",) * 7, 2015, 'heavy',
                   'Alu- oder Stahlfenster, Isolierverglasung', True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip('')
    def test_base_21_graz_einschichtig_full(self):
        """Test Testobjekt_einschichtig.ifc from Graz"""
        ifc = EXAMPLE_PATH / 'Testobjekt_einschichtig.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('Autodesk Revit 2020 (DEU)', True, True, 'Single office', 2015, 'heavy',
                   'Alu- oder Stahlfenster, Isolierverglasung', True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip('')
    def test_base_22_graz_mehrschichtig_full(self):
        """Test Testobjekt_mehrschichtig.ifc from Graz"""
        ifc = EXAMPLE_PATH / 'Testobjekt_mehrschichtig.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('Autodesk Revit 2020 (DEU)', True, True, 'Single office', 2015, 'heavy',
                   'Alu- oder Stahlfenster, Isolierverglasung', True, True, True, False)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)


if __name__ == '__main__':
    unittest.main()
