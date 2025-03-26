"""Tests for the ifc check of bim2sim

Based on ifctester and IDS (Information Delivery Specification)
"""

import unittest
import bim2sim.tasks.common.check_ifc_ids as check_ifc_ids
from pathlib import Path


test_rsrc_path = Path(__file__).parent.parent.parent.parent / 'resources'

class TestCheckIFC(unittest.TestCase):

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

    def test_checkIFC_guid_unique_fail(self):
        """test the boolean of the GUID uniqueness check
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file_guid_error = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55_NoneAndDoubleGUID.ifc'
        all_guids_checks_passed, non_unique_guids = check_ifc_ids.run_check_guid_unique(ifc_file_guid_error)
        self.assertEqual(all_guids_checks_passed, False, "Should be false")

    def test_checkIFC_guid_unique_specifc_guid_return(self):
        """test the guid return of the GUID uniqueness check
        """
        # TODO move test ifc file into resources and adapt path
        ifc_file_guid_error = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55_NoneAndDoubleGUID.ifc'
        all_guids_checks_passed, non_unique_guids = check_ifc_ids.run_check_guid_unique(ifc_file_guid_error)
        list_guids_non_unique = list(non_unique_guids.keys())

        predicted_result = ['25OWQvmXj5BPgyergP43tY', '1Oms875aH3Wg$9l65H2ZGw']
        self.assertEqual(list_guids_non_unique, predicted_result, "Should be a list of 2 GUIDs")
