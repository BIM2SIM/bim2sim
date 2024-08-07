import logging
import re
import shutil
import unittest
from pathlib import Path

import buildingspy.development.regressiontest as u

import bim2sim
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.test import RegressionTestBase
from bim2sim.utilities.types import IFCDomain

logger = logging.getLogger(__name__)


class RegressionTestTEASER(RegressionTestBase):
    def setUp(self):
        self.results_src_dir = None
        self.results_dst_dir = None
        self.tester = None
        super().setUp()

    def tearDown(self):
        # clean up buildingspy logs
        # TODO if statement is only needed, because CI discovers more tests
        #  than existing and then fails when trying to access not existing
        #  project
        if self.project:
            reg_dir = self.project.paths.b2sroot / 'bim2sim' / 'plugins' \
                      / 'PluginTEASER' / 'test' / 'regression'
            shutil.rmtree(reg_dir / 'funnel_comp', ignore_errors=True)
            log_files = [
                'comparison-dymola.log',
                'failed-simulator-dymola.log',
                'simulator-dymola.log',
                'unitTests-dymola.log'
            ]
            for log_file in log_files:
                file = reg_dir / log_file
                file.unlink(missing_ok=True)

        super().tearDown()

    def create_regression_setup(
            self,
            tolerance: float = 1E-3,
            batch_mode: bool = False):
        """
        Create a regression test setup based on BuildingsPy regression tests.

        This method uses the BuildingsPy library to create a regression test for
        the currents project TEASER modelica simulation model export.

        Args:
            tolerance: the tolerance in which the regression results will be
                accepted as valid
            batch_mode: in batch mode no input is required and no new results
                can be created

        """
        regex = re.compile("[^a-zA-z0-9]")
        model_export_name = regex.sub("", self.project.name)
        self.ref_results_src_path = Path(bim2sim.__file__).parent.parent \
            / "test/resources/arch/regression_results" \
            / self.project.name / 'TEASER'
        self.ref_results_dst_path = \
            self.project.paths.export / 'TEASER' / 'Model' / \
            model_export_name / 'Resources' / 'ReferenceResults' / \
            'Dymola'
        self.tester = u.Tester(tool='dymola', tol=tolerance,
                               cleanup=True)
        self.tester.pedanticModelica(False)
        self.tester.showGUI(False)
        self.tester.batchMode(batch_mode)
        self.tester.setLibraryRoot(
            self.project.paths.export / 'TEASER' / 'Model' / model_export_name)
        path_aixlib = self.project.paths.b2sroot / 'bim2sim' / 'plugins' / \
                      'AixLib' / 'AixLib' / 'package.mo'
        self.tester.setAdditionalLibResource(str(path_aixlib))
        if list(self.ref_results_src_path.rglob("*.txt")):
            shutil.copytree(self.ref_results_src_path,
                            self.ref_results_dst_path)
        else:
            shutil.rmtree(self.ref_results_src_path.parent, ignore_errors=True)

    def run_regression_test(self):
        if not list(self.ref_results_src_path.rglob("*.txt")):
            logger.error(
                f"No Regression Results found in {self.ref_results_src_path} "
                f"to perform regression test via simulation.")
        reg_test_res = self.tester.run()
        return reg_test_res

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
            shutil.rmtree(self.ref_results_src_path,
                          ignore_errors=True)
            shutil.copytree(self.ref_results_dst_path,
                            self.ref_results_src_path)
            logger.info("Regression results were updated with new results.")
        elif not sim_sucessful:
            logger.error(f"The simulation was not successful, "
                         f"no new regression results were created.")


class TestRegressionTEASER(RegressionTestTEASER, unittest.TestCase):
    def test_run_kitfzkhaus(self):
        """Run TEASER export with AC20-FZK-Haus.ifc and predefined materials
        and one zone model export"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        # FZK Haus as correct IFC types but wrong SB external/internal
        # information
        project.sim_settings.fix_type_mismatches_with_sb = False
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project export did not finish successfully.")
        self.create_regression_setup(tolerance=1E-3, batch_mode=True)
        reg_test_res = self.run_regression_test()
        if reg_test_res == 3:
            logger.error("Can't run dymola Simulation as no Dymola executable "
                         "found")
        self.assertEqual(0, reg_test_res,
                         "Regression test with simulation did not finish"
                         " successfully or created deviations.")
