import unittest

import bim2sim

from .base import IntegrationBase

# ------------------------------------------------------------------------------
# WARNING: run only one test per interpreter Instance.
# To use tests uncomment line below und run single test
# ------------------------------------------------------------------------------
# raise unittest.SkipTest("Integration tests not reliable for automated use")


class TestIntegrationHKESIM(IntegrationBase, unittest.TestCase):

    def test_run_vereinshaus1(self):
        """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
        answers = (True, True, *(True,)*14, 50)
        with bim2sim.decision.Decision.debug_answer(answers, multi=True):
            return_code = self.run_project(ifc, 'hkesim')
        self.assertEqual(0, return_code, "Project did not finish successfully.")

    def test_run_vereinshaus2(self):
        """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'
        answers = (True, *(True,)*16, 200)
        with bim2sim.decision.Decision.debug_answer(answers, multi=True):
            return_code = self.run_project(ifc, 'hkesim')
        self.assertEqual(0, return_code, "Project did not finish successfully.")


class TestIntegrationAixLib(unittest.TestCase):

    pass