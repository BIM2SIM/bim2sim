"""Tests for the ifc check of bim2sim

Based on ifctester and IDS (Information Delivery Specification)
"""

import unittest
import bim2sim.tasks.common.check_ifc_ids as check_ifc_ids
from pathlib import Path


test_rsrc_path = Path(__file__).parent.parent.parent.parent / 'resources'

class TestCheckIFC(unittest.TestCase):

    def test_checkIFC_IDS_fail(self):
        """check ifctester is working correctly by do check with IDS and ifc
        files from the IDS repo

        see:
        https://github.com/buildingSMART/IDS/tree/development/Documentation/ImplementersDocumentation/TestCases/ids
        """

        ifc_file = test_rsrc_path / 'arch/ids/fail-a_minimal_ids_can_check_a_minimal_ifc_1_2.ifc'
        ids_file = test_rsrc_path / 'arch/ids/fail-a_minimal_ids_can_check_a_minimal_ifc_1_2.ids'
        all_checks_passed = check_ifc_ids.run_ids_check_on_ifc(ifc_file, ids_file)
        # dummy code, delete later
        self.assertEqual(all_checks_passed, False, "Should be false")
