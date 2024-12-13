import sys
import unittest
from shutil import copyfile, copytree, rmtree
from pathlib import Path

import os

import bim2sim
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import IFCDomain

# raise unittest.SkipTest("Integration tests not reliable for automated use")
sample_root = Path(__file__).parent.parent.parent / 'test/resources/arch/ifc'
DEBUG_COMFORT = False


class IntegrationBaseComfort(IntegrationBase):
    # HACK: We have to remember stderr because eppy resets it currently.
    def setUp(self):
        self.old_stderr = sys.stderr
        self.working_dir = os.getcwd()
        super().setUp()

    def tearDown(self):
        if DEBUG_COMFORT: # copy EP-results to home directory for further
            # debugging.
            if not os.path.exists(Path.home() / 'idf'):
                os.mkdir(Path.home() / 'idf')
            ifc_name = str(os.listdir(self.project.paths.ifc)[0].split('.ifc')[0])
            temp_dir = Path(self.project.paths.export) / 'EnergyPlus'/\
                       'SimResults'/self.project.name
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


    def model_domain_path(self) -> str:
        return 'arch'

    def weather_file_path(self) -> Path:
        return (self.test_resources_path() /
                'weather_files/DEU_NW_Aachen.105010_TMYx.epw')


class TestComfortIntegration(IntegrationBaseComfort, unittest.TestCase):
    """
    Integration tests for multiple IFC example files.
    Tested are both original IFC files and files from Eric Fichter's Space Boundary Generation tool.
    """
    # @unittest.skip("")
    def test_base_01_FZK_full_run(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.create_external_elements = True
        project.sim_settings.split_bounds = True
        project.sim_settings.add_shadings = True
        project.sim_settings.split_shadings = True
        project.sim_settings.run_full_simulation = True
        project.sim_settings.rename_plot_keys = True
        project.sim_settings.create_plots = True
        # project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value)

    @unittest.skip("")
    def test_base_02_FZK_design_day(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.run_full_simulation = False
        # project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
        answers = ()
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("")
    def test_base_03_FZK_SB_design_day(self):
        """Test IFC File from FZK-Haus (KIT) with generated Space Boundaries"""
        # ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus_with_SB44.ifc'}
        ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus_with_SB55.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.create_external_elements = True
        project.sim_settings.prj_custom_usages = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "customUsagesAC20-FZK-Haus_with_SB55.json"
        # project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
        answers = ('Other',)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("")
    def test_base_04_FZK_SB_full_run(self):
        """Test IFC File from FZK-Haus (KIT) with generated Space Boundaries"""
        # ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus_with_SB44.ifc'}
        ifc_names = {IFCDomain.arch:  'AC20-FZK-Haus_with_SB55.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.create_external_elements = True
        project.sim_settings.run_full_simulation = True
        project.sim_settings.prj_use_conditions = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "UseConditionsAC20-FZK-Haus_with_SB55.json"
        project.sim_settings.prj_custom_usages = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "customUsagesAC20-FZK-Haus_with_SB55.json"
        answers = ('Other',)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("")
    def test_base_05_KIT_Inst_design_day(self):
        """Test Original IFC File from Institute (KIT)"""
        ifc_names = {IFCDomain.arch:  'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.create_external_elements = True
        answers = (2015,)
        # project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip("")
    def test_base_06_KIT_Inst_full_run(self):
        """Test Original IFC File from Institute (KIT)"""
        ifc_names = {IFCDomain.arch:  'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.create_external_elements = True
        project.sim_settings.run_full_simulation = True
        answers = (2015, )
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Skipped due to performance for CI")
    def test_base_07_KIT_Inst_SB_design_day(self):
        """Test IFC File from Institute (KIT) with generated Space Boundaries"""
        ifc_names = {IFCDomain.arch:  'AC20-Institute-Var-2_with_SB-1-0.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.create_external_elements = True
        # project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
        project.sim_settings.prj_custom_usages = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "customUsagesAC20-Institute-Var-2_with_SB-1-0.json"
        answers = ('Other', 2015)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Skipped due to performance for CI")
    def test_base_08_KIT_Inst_SB_full_run(self):
        """Test IFC File from Institute (KIT) with generated Space Boundaries"""
        ifc_names = {IFCDomain.arch:  'AC20-Institute-Var-2_with_SB-1-0.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.create_external_elements = True
        project.sim_settings.run_full_simulation = True
        project.sim_settings.prj_custom_usages = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "customUsagesAC20-Institute-Var-2_with_SB-1-0.json"
        answers = ('Other', 2015)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("")
    def test_DigitalHub_SB89(self):
        """Test DigitalHub IFC, includes regression test"""
        ifc_names = {IFCDomain.arch:  'FM_ARC_DigitalHub_with_SB89.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.create_external_elements = True
        project.sim_settings.cooling = True
        project.sim_settings.construction_class_windows = \
            'Waermeschutzverglasung, dreifach'
        project.sim_settings.prj_use_conditions = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "UseConditionsFM_ARC_DigitalHub.json"
        project.sim_settings.prj_custom_usages = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "customUsagesFM_ARC_DigitalHub_with_SB89.json"
        space_boundary_genenerator = 'Other'
        handle_proxies = (*(None,)*12,)
        construction_year = 2015
        project.sim_settings.split_bounds = False
        project.sim_settings.add_shadings = True
        project.sim_settings.split_shadings = False
        project.sim_settings.run_full_simulation = False
        answers = (space_boundary_genenerator,
                   *handle_proxies,
                   construction_year,
                   project.sim_settings.split_bounds,
                   project.sim_settings.add_shadings,
                   project.sim_settings.split_shadings,
                   project.sim_settings.run_full_simulation)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Skipped due to performance for CI")
    def test_base_09_DH_design_day(self):
        """Test DigitalHub IFC"""
        ifc_names = {IFCDomain.arch:  'FM_ARC_DigitalHub_fixed002.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.create_external_elements = True
        project.sim_settings.prj_use_conditions = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "UseConditionsFM_ARC_DigitalHub.json"
        project.sim_settings.prj_custom_usages = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "customUsagesFM_ARC_DigitalHub_fixed002.json"
        space_boundary_genenerator = 'Other'
        handle_proxies = (*(None,)*12,)
        construction_year = 2015
        project.sim_settings.split_bounds = True
        project.sim_settings.add_shadings = True
        project.sim_settings.split_shadings = True
        project.sim_settings.run_full_simulation = True
        answers = (space_boundary_genenerator,
                   *handle_proxies,
                   construction_year,
                   project.sim_settings.split_bounds,
                   project.sim_settings.add_shadings,
                   project.sim_settings.split_shadings,
                   project.sim_settings.run_full_simulation)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("Skipped due to performance for CI")
    def test_base_13_EDC_SB_design_day(self):
        """Test KIT KHH 3 storey IFC with generated Space Boundaries"""
        ifc_names = {IFCDomain.arch:  'KIT-EDC_with_SB.ifc'}
        project = self.create_project(ifc_names, 'comfort')
        project.sim_settings.create_external_elements = True
        project.sim_settings.split_bounds = True
        project.sim_settings.add_shadings = True
        project.sim_settings.split_shadings = True
        project.sim_settings.run_full_simulation = False
        # project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'

        project.sim_settings.prj_custom_usages = Path(
            bim2sim.__file__).parent.parent / \
            "test/resources/arch/custom_usages/" \
            "customUsagesKIT-EDC_with_SB.json"
        answers = ('Other', 'Other', 2015)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)



if __name__ == '__main__':
    unittest.main()
