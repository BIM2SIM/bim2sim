import unittest
from collections import Counter

from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.decision.console import ConsoleDecisionHandler
from bim2sim.kernel.aggregation import ConsumerHeatingDistributorModule
from bim2sim.utilities.test import IntegrationBase
from bim2sim.export.modelica import Instance


class IntegrationBaseAixLib(IntegrationBase):
    def tearDown(self):
        Instance.lookup = {}
        super().tearDown()


class TestIntegrationAixLib(IntegrationBaseAixLib, unittest.TestCase):

    def test_vereinshaus1_aixlib(self):
        """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
        project = self.create_project(ifc, 'aixlib')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   '2lU4kSSzH16v7KPrwcL7KZ', '0t2j$jKmf74PQpOI0ZmPCc',
                   *(True,)*13, 0.75, 150, *(5,)*11)

        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_vereinshaus2_aixlib(self):
        """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'
        project = self.create_project(ifc, 'aixlib')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   '0k0IjzL0z6aOYAX23H_dA5', '1U379nXO902R21a41MGQRw',
                   *(True,)*15, 0.75, 150, *(5,)*11)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_b03_heating_aixlib(self):
        """Run project with B03_Heating.ifc"""
        ifc = 'B03_Heating.ifc'
        project = self.create_project(ifc, 'aixlib')

        answers = (*('HVAC-Valve',)*2, 'HVAC-Distributor',
                   'HVAC-Boiler', 'HVAC-Storage', *('HVAC-Valve',)*14,
                   '2PFOreSeyfWqxUJNMz5nFO', '2YKblmYbhnh4RrfqKcCxPJ',
                   *(True,) * 13, 0.75, 50, 150, 70, *(1, 500,) * 7)
                   # *(True,) * 21, 0.75, 45, 150, 65, 7, *(1,) * 7)

        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer

        graph = project.playground.state['graph']
        aggregated = Counter((type(item) for item in graph.element_graph.nodes))
        self.assertIn(ConsumerHeatingDistributorModule, aggregated)
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
