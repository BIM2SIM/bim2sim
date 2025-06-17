"""Tests for the ifc check of bim2sim

Based on ifctester and IDS (Information Delivery Specification), but also checks not
based on ifctester (some requirements are not able to check with IDS v10)
"""

import unittest
import tempfile
from pathlib import Path

import bim2sim.tasks.common.load_ifc
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.elements.base_elements import ProductBased
from bim2sim.plugins import Plugin
from bim2sim.project import Project
from bim2sim.sim_settings import BaseSimSettings
from bim2sim.utilities.types import IFCDomain

from bim2sim.tasks.common.check_ifc_ids import CheckIfc

class PluginDummy(Plugin):
    name = 'test'
    sim_settings = BaseSimSettings
    default_tasks = [
        bim2sim.tasks.common.load_ifc.LoadIFC,
    ]

test_rsrc_path = Path(__file__).parent.parent.parent.parent / 'resources'


class TestCheckIFC(unittest.TestCase):
    """Tests for function checking IFC files, which are self made (these needed
       features are not included in the library ifctester respectifly in IDS
       standard

    """

    def tearDown(self):
        self.project.finalize(True)
        self.test_dir.cleanup()

    def weather_file_path(self) -> Path:
        return (test_rsrc_path /
                'weather_files/DEU_NW_Aachen.105010_TMYx.epw')

    def test_checkIFC_guid_unique_pass(self):
        """test the boolean of the GUID uniqueness check, check pass
           the following represent a project using the DummyPlugin
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file_guid_ok = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55.ifc'

        self.test_dir = tempfile.TemporaryDirectory()
        ifc_paths = {
            IFCDomain.arch:
                Path(bim2sim.__file__).parent.parent /
                'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
        }
        self.project = Project.create(self.test_dir.name, ifc_paths,
                                 plugin=PluginDummy, )
        # weather data path is mandatory and "mocking" is not working
        # so use a central defintion of weather file
        self.project.sim_settings.weather_file_path = self.weather_file_path()
        # put project.run into DebugDecisionHandler is need, otherwise the
        # playground.state() is empty and ifc_files are not available
        handler = DebugDecisionHandler([ProductBased.key])
        handler.handle(self.project.run(cleanup=False))

        ifc_files = self.project.playground.state['ifc_files']

        for ifc_file in ifc_files:
            # self.run_check_guid_unique(ifc_file)
            all_guids_checks_passed, non_unique_guids = CheckIfc.run_check_guid_unique(self, ifc_file)
            self.assertEqual(all_guids_checks_passed, True, "Should be True")


class TestCheckIFCSelfMade(unittest.TestCase):
    """Tests for function checking IFC files, which are self made (these needed
       features are not included in the library ifctester respectifly in IDS
       standard

    """
# TODO Maybe seperate test cases: 1. with IDS/ifc_tester (without task ifc
# load), 2. selfmade check (with task ifc load)
# TODO bring some tests to class TestCheckIFC
    @classmethod
    def setUpClass(cls) -> None:
        print("run setUpClass")

    # def test_checkIFC_guid_unique_pass(self):
    #     """test the boolean of the GUID uniqueness check, check pass
    #     """
    #     # TODO move test ifc file into resources and adapt path
    #     ifc_file_guid_ok = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55.ifc'
    #     all_guids_checks_passed, non_unique_guids = check_ifc_ids.run_check_guid_unique(ifc_file_guid_ok)
    #     self.assertEqual(all_guids_checks_passed, True, "Should be True")

    def test_checkIFC_guid_unique_fail(self):
        """test the boolean of the GUID uniqueness check, check fails
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file_guid_error = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55_NoneAndDoubleGUID.ifc'
        all_guids_checks_passed, non_unique_guids = check_ifc_ids.run_check_guid_unique(ifc_file_guid_error)
        self.assertEqual(all_guids_checks_passed, False, "Should be false")

    def test_checkIFC_guid_unique_specifc_guid_return(self):
        """test the guid return of a failed GUID uniqueness check
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file_guid_error = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55_NoneAndDoubleGUID.ifc'
        all_guids_checks_passed, non_unique_guids = check_ifc_ids.run_check_guid_unique(ifc_file_guid_error)
        list_guids_non_unique = list(non_unique_guids.keys())

        predicted_result = ['25OWQvmXj5BPgyergP43tY', '1Oms875aH3Wg$9l65H2ZGw']
        self.assertEqual(list_guids_non_unique, predicted_result, "Should be a list of 2 GUIDs")

    def test_run_check_guid_empty_fail(self):
        """test the boolean of all GUIDs has a value check, check fails
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file_guid_error = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55_NoneAndDoubleGUID.ifc'
        all_guids_filled_passed, non_unique_guids = check_ifc_ids.run_check_guid_empty(ifc_file_guid_error)
        self.assertEqual(all_guids_filled_passed, False, "Should be false")

    def test_run_check_guid_empty_pass(self):
        """test the boolean of all GUIDs has a value check, check pass
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file_guid_ok = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55.ifc'
        all_guids_filled_passed, non_unique_guids = check_ifc_ids.run_check_guid_empty(ifc_file_guid_ok)
        self.assertEqual(all_guids_filled_passed, True, "Should be true")


class TestCheckIFCIfctester(unittest.TestCase):
    """Tests for function checking IFC files, which are based on IDS file
       respectifly the library ifctester

    """
    def test_checkIFC_IDS_examples_minimal_fail(self):
        """check ifctester is working correctly by do check with IDS and ifc
        files from the IDS repo

        see:
        https://github.com/buildingSMART/IDS/tree/development/Documentation/ImplementersDocumentation/TestCases/ids
        """

        ifc_file = test_rsrc_path / 'ids/fail-a_minimal_ids_can_check_a_minimal_ifc_1_2.ifc'
        ids_file = test_rsrc_path / 'ids/fail-a_minimal_ids_can_check_a_minimal_ifc_1_2.ids'
        all_checks_passed = check_ifc_ids.run_ids_check_on_ifc(ifc_file, ids_file)
        self.assertEqual(all_checks_passed, False, "Should be false")

    def test_checkIFC_IDS_examples_required_specifications_fail(self):
        """check ifctester is working correctly by do check with IDS and ifc
        files from the IDS repo

        see:
        https://github.com/buildingSMART/IDS/tree/development/Documentation/ImplementersDocumentation/TestCases/ids
        """

        ifc_file = test_rsrc_path / 'ids/fail-required_specifications_need_at_least_one_applicable_entity_2_2.ifc'
        ids_file = test_rsrc_path / 'ids/fail-required_specifications_need_at_least_one_applicable_entity_2_2.ids'
        all_checks_passed = check_ifc_ids.run_ids_check_on_ifc(ifc_file, ids_file)
        self.assertEqual(all_checks_passed, False, "Should be false")

    def test_checkIFC_IDS_examples_a_specification_pass(self):
        """check ifctester is working correctly by do check with IDS and ifc
        files from the IDS repo

        see:
        https://github.com/buildingSMART/IDS/tree/development/Documentation/ImplementersDocumentation/TestCases/ids
        """

        ifc_file = test_rsrc_path / 'ids/pass-a_specification_passes_only_if_all_requirements_pass_2_2.ifc'
        ids_file = test_rsrc_path / 'ids/pass-a_specification_passes_only_if_all_requirements_pass_2_2.ids'
        all_checks_passed = check_ifc_ids.run_ids_check_on_ifc(ifc_file, ids_file)
        self.assertEqual(all_checks_passed, True, "Should be true")


    def test_checkIFC_IDS_examples_specification_optionality_pass(self):
        """check ifctester is working correctly by do check with IDS and ifc
        files from the IDS repo

        see:
        https://github.com/buildingSMART/IDS/tree/development/Documentation/ImplementersDocumentation/TestCases/ids

        date: 2025-03-12
        this test fail, because there is an issue in ifcTester, see
        https://github.com/IfcOpenShell/IfcOpenShell/issues/6323
        remove this passage, when fixed
        """

        ifc_file = test_rsrc_path / 'ids/pass-specification_optionality_and_facet_optionality_can_be_combined.ifc'
        ids_file = test_rsrc_path / 'ids/pass-specification_optionality_and_facet_optionality_can_be_combined.ids'
        all_checks_passed = check_ifc_ids.run_ids_check_on_ifc(ifc_file, ids_file)
        self.assertEqual(all_checks_passed, True, "Should be true, fails because of issue in ifcTester, 2025-03-12")


    def test_checkIFC_IDS_guid_length_22_pass(self):
        """check ifctester for use case guid/GlobalID length = 22 character
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55.ifc'
        ids_file = '/home/cudok/Documents/12_ifc_check_ids/check_guid_length_equals_22_character.ids'
        all_checks_passed = check_ifc_ids.run_ids_check_on_ifc(ifc_file, ids_file)
        self.assertEqual(all_checks_passed, True, "Should be true")

    def test_checkIFC_IDS_guid_length_22_fail(self):
        """check ifctester for use case guid/GlobalID length = 22 character
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55_NoneAndDoubleGUID.ifc'
        ids_file = '/home/cudok/Documents/12_ifc_check_ids/check_guid_length_equals_22_character.ids'
        all_checks_passed = check_ifc_ids.run_ids_check_on_ifc(ifc_file, ids_file)
        self.assertEqual(all_checks_passed, False, "Should be true")

    def test_checkIFC_IDS_2LSB_pass(self):
        """check ifctester for use case 2nd Level Space Boundarys
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55.ifc'
        ids_file = '/home/cudok/Documents/12_ifc_check_ids/check_2LSB.ids'
        all_checks_passed = check_ifc_ids.run_ids_check_on_ifc(ifc_file, ids_file)
        self.assertEqual(all_checks_passed, True, "Should be true")

    def test_checkIFC_IDS_2LSB_fail(self):
        """check ifctester for use case 2nd Level Space Boundarys
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus.ifc'
        ids_file = '/home/cudok/Documents/12_ifc_check_ids/check_2LSB.ids'
        all_checks_passed = check_ifc_ids.run_ids_check_on_ifc(ifc_file, ids_file)
        self.assertEqual(all_checks_passed, False, "Should be false")


if __name__ == "__main__":
    unittest.main()
