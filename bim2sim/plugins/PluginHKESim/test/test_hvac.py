import unittest
from collections import Counter

from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.decision.console import ConsoleDecisionHandler
from bim2sim.kernel.aggregation import ConsumerHeatingDistributorModule

from bim2sim.utilities.test import IntegrationBase


class TestIntegrationHKESIM(IntegrationBase, unittest.TestCase):

    def test_run_vereinshaus1(self):
        """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
        project = self.create_project(ifc, 'hkesim')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   '2lU4kSSzH16v7KPrwcL7KZ', '0t2j$jKmf74PQpOI0ZmPCc',
                   *(True,)*11,
                   200, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_vereinshaus2(self):
        """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'
        project = self.create_project(ifc, 'hkesim')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   '0k0IjzL0z6aOYAX23H_dA5', '1U379nXO902R21a41MGQRw',
                   *(True,)*13,
                   200, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_b03_heating(self):
        """Run project with B03_Heating.ifc"""
        ifc = 'B03_Heating_ownCells.ifc'
        project = self.create_project(ifc, 'hkesim')
        handler = ConsoleDecisionHandler()
        handler.handle(project.run())
        # answers = (*('HVAC-Valve',) * 2, 'HVAC-Distributor',
        #            'HVAC-Boiler', 'HVAC-Storage', *('HVAC-Valve',) * 14,
        #            '2PFOreSeyfWqxUJNMz5nFO', '2YKblmYbhnh4RrfqKcCxPJ',
        #            *(True,) * 13, 0.75, 50, 150, 70, *(1, 500,) * 7)
        answers = (*('HVAC-Valve',) * 2, 'HVAC-Distributor', *('HVAC-ThreeWayValve',) * 2, 'HVAC-Boiler',
                   'HVAC-Storage', *('HVAC-Valve',) * 14, *('HVAC-SpaceHeater',) * 7, 'HVAC-PipeFitting',
                   '2PFOreSeyfWqxUJNMz5nFO', '2YKblmYbhnh4RrfqKcCxPJ',
                   *(True,) * 11, 0.75, 50, 150, 70, *(1, 500,) * 7)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer

        graph = project.playground.state['graph']
        aggregated = Counter((type(item) for item in graph.element_graph.nodes))
        self.assertIn(ConsumerHeatingDistributorModule, aggregated)
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")


class TestIntegrationAixLib(unittest.TestCase):
    pass
