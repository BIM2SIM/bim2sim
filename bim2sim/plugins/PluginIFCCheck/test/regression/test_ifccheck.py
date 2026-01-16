"""regession tests for the pluging IFC Check"""
# TODO check needed imports (intialy copied from regression/test_teaser.py)
import logging
import re
import shutil
import unittest
# import filecmp  # compare files, maybe not needed TODO delete ?
from lxml import html
from pathlib import Path

import buildingspy.development.regressiontest as u

import bim2sim
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import RegressionTestBase
from bim2sim.utilities.types import IFCDomain, ZoningCriteria
from bim2sim.plugins.PluginIFCCheck.bim2sim_ifccheck import PluginIFCCheck

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
        # TODO later I put here the difffile/difffolder calls
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
    def test_run_ifc_check_fzk_haus(self):
        """Run IFCCheck regression test with AC20-FZK-Haus.ifc"""

        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, PluginIFCCheck)

        
        # assign an IDS file, which is needed to check the ifc file by ifctester
        project.sim_settings.ids_file_path = (
                Path(bim2sim.__file__).parent /
                'plugins/PluginIFCCheck/bim2sim_ifccheck/ifc_bps.ids'
        )

        # # In the next step we assign this file to the project by setting:
        # project.sim_settings.prj_custom_usages = (Path(
        #     bim2sim.__file__).parent.parent / "test/resources/arch/custom_usages/"
        #         "customUsagesAC20-FZK-Haus.json")

        # project.sim_settings.prj_use_conditions = (Path(
        #     bim2sim.__file__).parent.parent / "test/resources/arch/custom_usages/"
        #         "UseConditionsAC20-FZK-Haus.json")

        # project.sim_settings.setpoints_from_template = True

        answers = ()
        handler = DebugDecisionHandler(answers)

        handler.handle(project.run())

        # for decision, answer in handler.decision_answer_mapping(project.run()):
        #     decision.value = answer

        # project.sim_settings.zoning_criteria = (
        #     ZoningCriteria.combined_single_zone)
        # project.sim_settings.ahu_tz_overwrite = False
        # answers = ()
        # handler = DebugDecisionHandler(answers)
        # for decision, answer in handler.decision_answer_mapping(project.run()):
        #     decision.value = answer
        # orientation_dict = {}
        # elements = project.playground.state['elements']
        # for ele in elements.values():
        #     if hasattr(ele, 'teaser_orientation'):
        #         if ele.teaser_orientation:
        #             orientation_dict[ele] = ele.teaser_orientation
        # self.assertEqual(0, handler.return_value,
        #                  "Project export did not finish successfully.")
        # self.create_regression_setup(tolerance=1E-3, batch_mode=True)
        # reg_test_res = self.run_regression_test()
        # if reg_test_res == 3:
        #     logger.error("Can't run dymola Simulation as no Dymola executable "
        #                  "found")
        # self.assertEqual(0, reg_test_res,
        #                  "Regression test with simulation did not finish"
        #                  " successfully or created deviations.")

        file_result_ifc_tester = self.project.paths.log / "ifc_ids_check.html"
        print(file_result_ifc_tester)
        # file_a = Path(bim2sim.__file__).parent.parent \
        #     / "test/resources/ifc_check/regression_results/test_compare_file.txt"
        # file_b = "/home/cudok/Documents/12_ifc_check_ids/regression_stuff/test_file_reg.txt"
        file_result_ifc_tester_res = "/home/cudok/Documents/12_ifc_check_ids/regression_stuff/ifc_ids_check.html"
        # result = filecmp.cmp(file_result_ifc_tester, file_result_ifc_tester_res, shallow=True)
        # print(result)
        # print('vor DEM TEST')

        # xpaths to elements in html
        xpath = '//div[@class="fail percent"]'

        doc_a = html.fromstring(open(file_result_ifc_tester).read())
        elem_a = doc_a.xpath(xpath)
        elem_a_cont = elem_a[0].text_content().strip()
        print('content of element a: {}'.format(elem_a_cont))

        doc_b = html.fromstring(open(file_result_ifc_tester_res).read())
        elem_b = doc_b.xpath(xpath)
        elem_b_cont = elem_b[0].text_content().strip()
        print('content of element b: {}'.format(elem_b_cont))

        
        self.assertEqual(elem_a_cont, elem_b_cont,
                         "Dummy Test fail")
