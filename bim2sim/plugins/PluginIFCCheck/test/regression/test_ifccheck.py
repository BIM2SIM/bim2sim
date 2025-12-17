"""regession tests for the pluging IFC Check"""
# TODO check needed imports (intialy copied from regression/test_teaser.py)
import logging
import re
import shutil
import unittest
from pathlib import Path

import buildingspy.development.regressiontest as u

import bim2sim
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import RegressionTestBase
from bim2sim.utilities.types import IFCDomain, ZoningCriteria

logger = logging.getLogger(__name__)


class RegressionTestIFCCheck(RegressionTestBase):
    """Class to setup up nad run regression test of PluginIFCCheck"""
    def setUp(self):
        self.results_src_dir = None
        self.results_dst_dir = None
        super().setUp()

    def tearDown(self):

        super().tearDown()

    def create_regression_setup(self):
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
        passed_regression_test = False
        return passed_regression_test

    def run_regression_test(self):
        print("run reg test")
        reg_test_res = False
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
        # TODO put something in
        pass

class TestRegressionIFCCheck(RegressionTestIFCCheck, unittest.TestCase):
    def test_run_kitfzkhaus(self):
        """Run TEASER regression test with AC20-FZK-Haus.ifc and one zone model
         export"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = (
            ZoningCriteria.combined_single_zone)
        project.sim_settings.ahu_tz_overwrite = False
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        orientation_dict = {}
        elements = project.playground.state['elements']
        for ele in elements.values():
            if hasattr(ele, 'teaser_orientation'):
                if ele.teaser_orientation:
                    orientation_dict[ele] = ele.teaser_orientation
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
