import os
import re
import shutil
import sys
import unittest
import logging
from pathlib import Path

from energyplus_regressions.diffs import math_diff, table_diff
from energyplus_regressions.diffs.thresh_dict import ThreshDict

import bim2sim
from bim2sim.utilities.types import LOD, IFCDomain
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import RegressionTestBase

logger = logging.getLogger(__name__)


class RegressionTestEnergyPlus(RegressionTestBase):
    """Class to set up and run EnergyPlus regression tests."""
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

    def weather_file_path(self) -> Path:
        return (self.test_resources_path() /
                'weather_files/DEU_NW_Aachen.105010_TMYx.epw')

    def create_regression_setup(self):
        """
        Create a regression test setup for EnergyPlus.

        This method uses the energyplus_regressions library to create a
        regression test for the passed project EnergyPlus simulation model
        export.
        """
        passed_regression_test = False

        regex = re.compile("[^a-zA-z0-9]")
        model_export_name = regex.sub("", self.project.name)
        ref_csv = self.ref_results_src_path / str(self.project.name +
                                         '_eplusout.csv')
        ref_htm = self.ref_results_src_path / str(self.project.name +
                                         '_eplustbl.htm')
        diff_config = ThreshDict(Path(bim2sim.__file__).parent /
            "plugins/PluginEnergyPlus/test/regression/ep_diff.config")
        # set path to current simulation results
        export_path = self.project.paths.export / \
                      'EnergyPlus'/'SimResults'/self.project.name
        sim_csv = export_path / 'eplusout.csv'
        sim_htm = export_path / 'eplustbl.htm'
        # set directory for regression test results
        regression_results_dir = self.project.paths.root / \
                                 'regression_results' / 'bps' / \
                                 self.project.name / 'EnergyPlus'
        if not Path.exists(regression_results_dir):
            Path.mkdir(regression_results_dir, parents=True)
        csv_regression = math_diff.math_diff(
            # csv_regression returns diff_type ('All Equal', 'Big Diffs',
            # 'Small Diffs'), num_records (length of validated csv file
            # (#timesteps)), num_big (#big errors),
            # num_small (#small errors)
            diff_config,
            str(ref_csv),
            str(sim_csv),
            os.path.join(regression_results_dir, 'abs_diff_math.csv'),
            os.path.join(regression_results_dir, 'rel_diff_math.csv'),
            os.path.join(regression_results_dir, 'math_diff_math.log'),
            os.path.join(regression_results_dir, 'summary_math.csv'),
        )
        if csv_regression[0] in ['Small Diffs', 'All Equal']:
            passed_regression_test = True  # only passes with small diffs

        htm_regression = table_diff.table_diff(
            # htm_regression returns message, #tables, #big_diff,
            # #small_diff, #equals, #string_diff,
            # #size_diff, #not_in_file1, #not_in_file2
            diff_config,
            str(ref_htm),
            str(sim_htm),
            os.path.join(regression_results_dir, 'abs_diff_table.htm'),
            os.path.join(regression_results_dir, 'rel_diff_table.htm'),
            os.path.join(regression_results_dir, 'math_diff_table.log'),
            os.path.join(regression_results_dir, 'summary_table.csv'),
        )
        if htm_regression[2] == 0:
            passed_regression_test = True  # only passes without big diffs

        return passed_regression_test

    def run_regression_test(self):
        """Run the EnergyPlus regression test."""
        self.ref_results_src_path = \
            Path(bim2sim.__file__).parent.parent \
            / "test/resources/arch/regression_results" \
            / self.project.name / 'EnergyPlus'
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
    """Regression tests for EnergyPlus."""
    def test_regression_AC20_FZK_Haus(self):
        """Run EnergyPlus regression test with AC20-FZK-Haus.ifc."""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'energyplus')
        project.sim_settings.create_external_elements = True
        project.sim_settings.cooling = True
        project.sim_settings.split_bounds = True
        project.sim_settings.add_shadings = True
        project.sim_settings.split_shadings = True
        project.sim_settings.run_full_simulation = True
        project.sim_settings.use_maintained_illuminance = False
        project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
        handler = DebugDecisionHandler(())
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project export and simulation did not finish "
                         "successfully.")
        self.assertEqual(len(project.playground.elements), 213)
        reg_test_res = self.run_regression_test()
        self.assertEqual(True, reg_test_res,
                         "EnergyPlus Regression test did not finish "
                         "successfully or created deviations.")

    def test_regression_DigitalHub_SB89(self):
        """Test DigitalHub IFC, includes regression test."""
        ifc_names = {IFCDomain.arch: 'FM_ARC_DigitalHub_with_SB89.ifc'}
        project = self.create_project(ifc_names, 'energyplus')
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
        # project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
        space_boundary_genenerator = 'Other'
        handle_proxies = (*(None,) * 12,)
        construction_year = 2015
        project.sim_settings.split_bounds = False
        project.sim_settings.add_shadings = True
        project.sim_settings.split_shadings = False
        project.sim_settings.run_full_simulation = False
        answers = (space_boundary_genenerator,
                   *handle_proxies,
                   construction_year)
        handler = DebugDecisionHandler(answers)
        handler.handle(project.run())
        self.assertEqual(0, handler.return_value,
                         "Project export and simulation did not finish "
                         "successfully.")
        reg_test_res = self.run_regression_test()
        self.assertEqual(True, reg_test_res,
                         "EnergyPlus Regression test did not finish "
                         "successfully or created deviations.")
