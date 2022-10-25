import os
import re
import shutil
import sys
import unittest
import logging
from pathlib import Path

from epregressions.diffs import math_diff, table_diff
from epregressions.diffs.thresh_dict import ThreshDict

from bim2sim import workflow
from bim2sim.workflow import LOD
from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import RegressionTestBase

logger = logging.getLogger(__name__)

RESULT_PATH = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent.parent.parent.parent / 'ResultFiles'


class RegressionTestEnergyPlus(RegressionTestBase):
    def setUp(self):
        self.old_stderr = sys.stderr
        self.working_dir = os.getcwd()
        self.ref_results_src_path = None
        self.results_src_dir = None
        self.results_dst_dir = None
        self.tester = None
        super().setUp()

    def tearDown(self):
        os.chdir(self.working_dir)
        sys.stderr = self.old_stderr
        super().tearDown()

    def create_regression_setup(self):
        """
        Create a regression test setup for EnergyPlus based on epregressions
        regression tests.

        This method uses the epregressions library to create a regression test
        for the passed project EnergyPlus simulation model export.
        """
        passed_regression_test = True

        regex = re.compile("[^a-zA-z0-9]")
        model_export_name = regex.sub("", self.project.name)
        self.regression_base_path = \
            self.project.paths.assets / 'regression_results' / 'bps'
        self.ref_results_src_path = \
            self.regression_base_path / self.project.name / 'EnergyPlus'
        ref_csv = self.ref_results_src_path / str(self.project.name +
                                         '_eplusout.csv')
        ref_htm = self.ref_results_src_path / str(self.project.name +
                                         '_eplustbl.htm')
        diff_config = ThreshDict(self.regression_base_path / 'ep_diff.config')

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

    def run_regression_test(self):
        self.regression_base_path = \
            self.project.paths.assets / 'regression_results' / 'bps'
        self.ref_results_src_path = \
            self.regression_base_path / self.project.name / 'EnergyPlus'
        if not (list(self.ref_results_src_path.rglob("*.htm")) and list(
                self.ref_results_src_path.rglob("*.csv"))):
            logger.error(
                f"No Regression Results found in {self.ref_results_src_path} "
                f"to perform regression test via simulation.")
        passed_regression = self.create_regression_setup()
        return passed_regression

    def create_regression_results(self):
        """Creates regression results based on simulation model.

        If simulation is successful and regression results differ from
        new simulation results, the user is asked if the results should be
        overwritten.
        If simulation  is successful and simulation results are same with
        regression results nothing happens.
        If simulation is not successful nothing happens.
        """
        self.tester.run()
        sim_sucessful = self.tester._comp_info[0]['simulation']['success']
        comp_sucessful = self.tester._comp_info[0]['comparison']['test_passed']

        # sim and comparison
        if sim_sucessful and all(comp_sucessful):
            logger.info("No differences between simulation and regression "
                        "results. No fresh results created.")
        # sim successful but comparison not (new results were created based if
        # user decided to simulate
        elif sim_sucessful and not all(comp_sucessful):
            # copy updated ref results to assets
            shutil.rmtree(self.ref_results_src_path.parent,
                          ignore_errors=True)
            shutil.copytree(self.ref_results_dst_path,
                            self.ref_results_src_path)
            logger.info("Regression results were updated with new results.")
        elif not sim_sucessful:
            logger.error(f"The simulation was not successful, "
                         f"no new regression results were created.")


class TestRegressionEnergyPlus(RegressionTestEnergyPlus, unittest.TestCase):
    def test_regression_AC20_FZK_Haus(self):
        """Run EnergyPlus export with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        project = self.create_project(ifc, 'energyplus')
        project.create_external_elements = True
        project.zoning_setup = LOD.full
        cooling = True
        heating = True
        split_non_convex_bounds = True
        add_shadings = True
        split_non_convex_shadings = True
        run_full_simulation = True
        answers = (cooling,
                   heating,
                   split_non_convex_bounds,
                   add_shadings,
                   split_non_convex_shadings,
                   run_full_simulation)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project export and simulation did not finish "
                         "successfully.")
        reg_test_res = self.run_regression_test()
        self.assertEqual(True, reg_test_res,
                         "EnergyPlus Regression test did not finish "
                         "successfully or created deviations.")


    def test_DigitalHub_SB89_regression(self):
        """Test DigitalHub IFC, includes regression test"""
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_with_SB89.ifc'
        used_workflow = workflow.BuildingSimulation()
        used_workflow.create_external_elements = True
        used_workflow.zoning_setup = LOD.full
        project = self.create_project(ifc, 'energyplus', used_workflow)
        space_boundary_genenerator = 'Autodesk Revit 2020 (DEU)'
        handle_proxies = (*(None,) * 150,)
        construction_year = 2015
        split_non_convex_bounds = False
        add_shadings = True
        split_non_convex_shadings = False
        run_full_simulation = False
        answers = (space_boundary_genenerator,
                   *handle_proxies,
                   construction_year,
                   split_non_convex_bounds,
                   add_shadings,
                   split_non_convex_shadings,
                   run_full_simulation)
        handler = DebugDecisionHandler(answers)
        handler.handle(project.run())
        self.assertEqual(0, handler.return_value,
                         "Project export and simulation did not finish "
                         "successfully.")
        reg_test_res = self.run_regression_test()
        self.assertEqual(True, reg_test_res,
                         "EnergyPlus Regression test did not finish "
                         "successfully or created deviations.")