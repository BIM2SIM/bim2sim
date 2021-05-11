import unittest

import bim2sim
from bim2sim.decision.frontend import DebugFrontend

from bim2sim.utilities.test import IntegrationBase


class TestIntegrationHKESIM(IntegrationBase, unittest.TestCase):

    def test_run_vereinshaus1(self):
        """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
        project = self.create_project(ifc, 'hkesim')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   '2lU4kSSzH16v7KPrwcL7KZ', '0t2j$jKmf74PQpOI0ZmPCc',
                   True, True, *(True,)*14, 50)
        frontend = DebugFrontend(answers)
        for decision, answer in frontend.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, frontend.return_value,
                         "Project did not finish successfully.")

    def test_run_vereinshaus2(self):
        """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'
        project = self.create_project(ifc, 'hkesim')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   *(True,)*16, 200)
        frontend = DebugFrontend(answers)
        for decision, answer in frontend.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, frontend.return_value,
                         "Project did not finish successfully.")


class TestIntegrationAixLib(unittest.TestCase):

    pass