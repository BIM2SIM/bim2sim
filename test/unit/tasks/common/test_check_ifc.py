"""Tests for the ifc check of bim2sim

Based on ifctester and IDS (Information Delivery Specification)
"""

import unittest
import bim2sim.tasks.common.check_ifc_ids as check_ifc_ids

# the paths must adapt to be generic
ifc_file = '/home/cudok/Documents/10_Git/bim2sim/test/resources/arch/ifc/AC20-FZK-Haus_with_SB55.ifc'
ids_file = '/home/cudok/Documents/12_ifc_check_ids/ifc_check_spaces(3).ids'

class TestCheckIFC(unittest.TestCase):

    def test_checkIFC_IDS_example(self):
        """check ifctester is working correctly by do check with IDS and ifc
        files from the IDS repo

        see:
        https://github.com/buildingSMART/IDS/tree/development/Documentation/ImplementersDocumentation/TestCases/ids
        """
        all_checks_passed = check_ifc_ids.run_ids_check_on_ifc(ifc_file, ids_file)
        # dummy code, delete later
        self.assertEqual(all_checks_passed, False, "Should be false")
