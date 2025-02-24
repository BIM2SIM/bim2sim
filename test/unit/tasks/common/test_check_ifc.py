"""Tests for the ifc check of bim2sim

Based on ifctester and IDS (Information Delivery Specification)
"""

import unittest

class TestCheckIFC(unittest.TestCase):

    def test_checkIFC_IDS_example(self):
        """check ifctester is working correctly by do check with IDS and ifc
        files from the IDS repo

        see:
        https://github.com/buildingSMART/IDS/tree/development/Documentation/ImplementersDocumentation/TestCases/ids
        """

        # dummy code, delete later
        self.assertEqual(sum([1, 2, 3]), 8, "Should be 6")
