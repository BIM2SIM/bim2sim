import sys
import unittest
import tempfile
from shutil import copyfile, copytree, rmtree
from pathlib import Path
import epregressions

import os

from epregressions.diffs import math_diff, table_diff
from epregressions.diffs.thresh_dict import ThreshDict

from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase
from bim2sim.project import Project
from bim2sim import workflow
from bim2sim.workflow import LOD


# raise unittest.SkipTest("Integration tests not reliable for automated use")
sample_root = Path(__file__).parent.parent.parent / 'test/TestModels/BPS'
DEBUG_ENERGYPLUS = False


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

    def regression_test(self, workflow):
        """Run regression test comparison for EnergyPlus.

        Requires that simulation was run and not only model was created.

        """
        passed_regression_test = True
        if not workflow.simulated:
            raise AssertionError("Simulation was not run, no regression test "
                                 "possible")
        else:
            # set reference paths for energyplus regression test
            regression_base_path = \
                self.project.paths.assets / 'regression_results' / 'bps'
            ref_results_path = \
                regression_base_path / self.project.name / 'EnergyPlus'
            ref_csv = ref_results_path / str(self.project.name +
                                             '_eplusout.csv')
            ref_htm = ref_results_path / str(self.project.name +
                                             '_eplustbl.htm')
            diff_config = ThreshDict(regression_base_path / 'ep_diff.config')

            # set path to current simulation results
            sim_csv = self.project.paths.export / 'EP-results' / 'eplusout.csv'
            sim_htm = self.project.paths.export / 'EP-results' / 'eplustbl.htm'
            # set directory for regression test results
            regression_results_dir = self.project.paths.root / \
                                     'regression_results' / 'bps' / \
                                     self.project.name / 'EnergyPlus'

            csv_regression = math_diff.math_diff(
                # csv_regression returns diff_type ('All Equal', 'Big Diffs',
                # 'Small Diffs'), num_records (length of validated csv file
                # (#timesteps)), num_big (#big errors),
                # num_small (#small errors)
                diff_config,
                ref_csv.as_posix(),
                sim_csv.as_posix(),
                os.path.join(regression_results_dir, 'abs_diff_math.csv'),
                os.path.join(regression_results_dir, 'rel_diff_math.csv'),
                os.path.join(regression_results_dir, 'math_diff_math.log'),
                os.path.join(regression_results_dir, 'summary_math.csv'),
            )
            if csv_regression[0] == 'Big Diffs':
                passed_regression_test = False  # only passes with small diffs

            htm_regression = table_diff.table_diff(
                # htm_regression returns message, #tables, #big_diff,
                # #small_diff, #equals, #string_diff,
                # #size_diff, #not_in_file1, #not_in_file2
                diff_config,
                ref_htm.as_posix(),
                sim_htm.as_posix(),
                os.path.join(regression_results_dir, 'abs_diff_table.htm'),
                os.path.join(regression_results_dir, 'rel_diff_table.htm'),
                os.path.join(regression_results_dir, 'math_diff_table.log'),
                os.path.join(regression_results_dir, 'summary_table.csv'),
            )
            if htm_regression[2] != 0:
                passed_regression_test = False  # only passes without big diffs

            return passed_regression_test

    def model_domain_path(self) -> str:
        return 'BPS'


class TestEPIntegration(IntegrationBaseEP, unittest.TestCase):
    """
    Integration tests for multiple IFC example files.
    Tested are both original IFC files and files from Eric Fichter's Space Boundary Generation tool.
    """
    @unittest.skip("")
    def test_base_01_FZK_design_day(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = 'AC20-FZK-Haus.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.zoning_setup = LOD.full
        project.workflow.create_external_elements = True
        project.workflow.split_bounds = True
        project.workflow.add_shadings = True
        project.workflow.split_shadings = True
        project.workflow.run_full_simulation = True
        answers = (project.workflow.split_bounds,
                   project.workflow.add_shadings,
                   project.workflow.split_shadings,
                   project.workflow.run_full_simulation)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        passed_regression = self.regression_test(project.workflow)
        self.assertEqual(0, handler.return_value)
        self.assertEqual(True, passed_regression, 'Failed EnergyPlus '
                                                  'Regression Test')

    @unittest.skip("")
    def test_base_02_FZK_full_run(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = 'AC20-FZK-Haus.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.zoning_setup = LOD.full
        project.workflow.create_external_elements = True
        project.workflow.run_full_simulation = True
        answers = ()
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("")
    def test_base_03_FZK_SB_design_day(self):
        """Test IFC File from FZK-Haus (KIT) with generated Space Boundaries"""
        # ifc = 'AC20-FZK-Haus_with_SB44.ifc'
        ifc = 'AC20-FZK-Haus_with_SB55.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.zoning_setup = LOD.full
        project.workflow.create_external_elements = True
        answers = ('Other',)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("")
    def test_base_04_FZK_SB_full_run(self):
        """Test IFC File from FZK-Haus (KIT) with generated Space Boundaries"""
        # ifc = 'AC20-FZK-Haus_with_SB44.ifc'
        ifc = 'AC20-FZK-Haus_with_SB55.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.zoning_setup = LOD.full
        project.workflow.create_external_elements = True
        project.workflow.run_full_simulation = True
        answers = ('Other',)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("")
    def test_base_05_KIT_Inst_design_day(self):
        """Test Original IFC File from Institute (KIT)"""
        ifc = 'AC20-Institute-Var-2.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.zoning_setup = LOD.full
        project.workflow.create_external_elements = True
        answers = (2015,)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip("")
    def test_base_06_KIT_Inst_full_run(self):
        """Test Original IFC File from Institute (KIT)"""
        ifc = 'AC20-Institute-Var-2.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.zoning_setup = LOD.full
        project.workflow.create_external_elements = True
        project.workflow.run_full_simulation = True
        answers = (2015, )
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("Skipped due to performance for CI")
    def test_base_07_KIT_Inst_SB_design_day(self):
        """Test IFC File from Institute (KIT) with generated Space Boundaries"""
        ifc = 'AC20-Institute-Var-2_with_SB-1-0.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.zoning_setup = LOD.full
        project.workflow.create_external_elements = True
        answers = ('Other', 2015)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Skipped due to performance for CI")
    def test_base_08_KIT_Inst_SB_full_run(self):
        """Test IFC File from Institute (KIT) with generated Space Boundaries"""
        ifc = 'AC20-Institute-Var-2_with_SB-1-0.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.zoning_setup = LOD.full
        project.workflow.create_external_elements = True
        project.workflow.run_full_simulation = True
        answers = ('Other', 2015)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("")
    def test_DigitalHub_SB89_regression(self):
        """Test DigitalHub IFC, includes regression test"""
        ifc = 'FM_ARC_DigitalHub_with_SB89.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.zoning_setup = LOD.full
        project.workflow.create_external_elements = True
        project.workflow.cooling = True
        project.workflow.construction_class_windows = \
            'Waermeschutzverglasung, dreifach'
        space_boundary_genenerator = 'Other'
        handle_proxies = (*(None,)*150,)
        construction_year = 2015
        project.workflow.split_bounds = False
        project.workflow.add_shadings = True
        project.workflow.split_shadings = False
        project.workflow.run_full_simulation = False
        answers = (space_boundary_genenerator,
                   *handle_proxies,
                   construction_year,
                   project.workflow.split_bounds,
                   project.workflow.add_shadings,
                   project.workflow.split_shadings,
                   project.workflow.run_full_simulation)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)
        passed_regression = self.regression_test(project.workflow)
        self.assertEqual(True, passed_regression, 'Failed EnergyPlus '
                                                  'Regression Test')


    @unittest.skip("Skipped due to performance for CI")
    def test_base_09_DH_design_day(self):
        """Test DigitalHub IFC"""
        ifc = 'FM_ARC_DigitalHub_fixed002.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.zoning_setup = LOD.full
        project.workflow.create_external_elements = True
        space_boundary_genenerator = 'Other'
        handle_proxies = (*(None,)*150,)
        construction_year = 2015
        project.workflow.split_bounds = True
        project.workflow.add_shadings = True
        project.workflow.split_shadings = True
        project.workflow.run_full_simulation = True
        answers = (space_boundary_genenerator,
                   *handle_proxies,
                   construction_year,
                   project.workflow.split_bounds,
                   project.workflow.add_shadings,
                   project.workflow.split_shadings,
                   project.workflow.run_full_simulation)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    # @unittest.skip("Skipped due to performance for CI")
    def test_base_13_EDC_SB_design_day(self):
        """Test KIT KHH 3 storey IFC with generated Space Boundaries"""
        ifc = 'KIT-EDC_with_SB.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.create_external_elements = True
        project.workflow.zoning_setup = LOD.full
        project.workflow.split_bounds = True
        project.workflow.add_shadings = True
        project.workflow.split_shadings = True
        project.workflow.run_full_simulation = False
        answers = ('Other', 'Other', 2015)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Skipped due to performance for CI")
    def test_base_14_EDC_SB_full_run(self):
        """Test KIT KHH 3 storey IFC with generated Space Boundaries"""
        ifc = 'KIT-EDC_with_SB.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.create_external_elements = True
        project.workflow.zoning_setup = LOD.full
        project.workflow.split_bounds = True
        project.workflow.add_shadings = True
        project.workflow.split_shadings = True
        project.workflow.run_full_simulation = True
        answers = ('Other', 'Other', 2015)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Not fully implemented yet")
    def test_base_17_ERC_design_day(self):
        """Test ERC Main Building"""
        ifc = '26.05space_modified.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.create_external_elements = True
        project.workflow.zoning_setup = LOD.full
        project.workflow.split_bounds = True
        project.workflow.add_shadings = True
        project.workflow.split_shadings = True
        project.workflow.run_full_simulation = False
        answers = ('Autodesk Revit',
                   *('Single office',)*5)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip("Not fully implemented yet")
    def test_base_19_linear_SB_design_day(self):
        """Test Linear Building with generated Space Boundaries"""
        # ifc = 'Office_Building_Architectural_IFC_export_with_SB.ifc'
        ifc = 'Linear_V01.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.create_external_elements = True
        project.workflow.zoning_setup = LOD.full
        project.workflow.split_bounds = True
        project.workflow.add_shadings = True
        project.workflow.split_shadings = True
        project.workflow.run_full_simulation = False
        answers = ('Other', *('Single office',)*71, 2015)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value)

    @unittest.skip("Not fully implemented yet")
    def test_base_20_olabarri_design_day(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = 'Olabarri_49.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.create_external_elements = True
        project.workflow.zoning_setup = LOD.full
        project.workflow.split_bounds = True
        project.workflow.add_shadings = True
        project.workflow.split_shadings = True
        project.workflow.run_full_simulation = False
        answers = ('Other', *("Single office",) * 7, 2015)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip('')
    def test_base_21_graz_einschichtig_full(self):
        """Test Testobjekt_einschichtig.ifc from Graz"""
        ifc = 'Testobjekt_einschichtig.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.create_external_elements = True
        project.workflow.zoning_setup = LOD.full
        project.workflow.split_bounds = True
        project.workflow.add_shadings = True
        project.workflow.split_shadings = True
        project.workflow.run_full_simulation = False
        answers = ('Single office', 2015)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    @unittest.skip('')
    def test_base_22_graz_mehrschichtig_full(self):
        """Test Testobjekt_mehrschichtig.ifc from Graz"""
        ifc = 'Testobjekt_mehrschichtig.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.workflow.create_external_elements = True
        project.workflow.zoning_setup = LOD.full
        project.workflow.split_bounds = True
        project.workflow.add_shadings = True
        project.workflow.split_shadings = True
        project.workflow.run_full_simulation = False
        answers = ('Single office', 2015)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)


if __name__ == '__main__':
    unittest.main()
