import unittest
from collections import Counter

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.export.modelica import ModelicaElement
from bim2sim.elements.aggregation.hvac_aggregations \
    import ConsumerHeatingDistributorModule
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import IFCDomain


class IntegrationBaseHKESIM(IntegrationBase):
    def tearDown(self):
        ModelicaElement.lookup = {}
        super().tearDown()

    def model_domain_path(self) -> str:
        return 'hydraulic'


class TestIntegrationHKESIM(IntegrationBaseHKESIM, unittest.TestCase):

    def test_run_vereinshaus1(self):
        """
        Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc
        """
        ifc_names = {IFCDomain.hydraulic:
                         'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'}
        project = self.create_project(ifc_names, 'hkesim')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   '2lU4kSSzH16v7KPrwcL7KZ', '0t2j$jKmf74PQpOI0ZmPCc',
                   # 1x expansion tank and 17x dead end
                   *(True,) * 18,
                   # boiler efficiency
                   0.9,
                   # boiler power,
                   150,
                   # boiler return temperature
                   70,
                   # volume of junctions
                   *(0.1,) * 35,
                   # 2x pumps: current, height, voltage, volume flow rate
                   *(4, 10, 400, 120,) * 2,
                   # 11x space heater: rated_power, return_temperature
                   *(10, 50) * 11,
                   # diameter of storage
                   1,
                   # height of storage
                   2,
                   # rated_power of heat pump
                   200)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_b03_heating(self):
        """Run project with 2022_11_21_update_B03_Heating_ownCells.ifc"""
        ifc_names = {IFCDomain.hydraulic:
                         '2022_11_21_update_B03_Heating_ownCells.ifc'}
        project = self.create_project(ifc_names, 'hkesim')
        project.sim_settings.aggregations = [
            'UnderfloorHeating',
            'Consumer',
            'PipeStrand',
            'ParallelPump',
            'ConsumerHeatingDistributorModule',
        ]
        answers = (None, 'HVAC-PipeFitting', 'HVAC-Distributor',
                   'HVAC-ThreeWayValve',
                   # 7x dead ends
                   *(True,) * 7,
                   # boiler: efficiency
                   0.9,
                   # boiler: nominal power consumption
                   150,
                   # boiler: nominal output temperature
                   70,
                   # junction: volume
                   1,
                   # pump: rated current
                   4,
                   # pump: rated height
                   10,
                   # pump: rated voltage
                   400,
                   # pump: rated volume flow
                   120)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        graph = project.playground.state['graph']
        aggregated = Counter((type(item) for item in graph.element_graph.nodes))
        self.assertIn(ConsumerHeatingDistributorModule, aggregated)
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_b03_heating_with_all_aggregations(self):
        """Run project with 2022_11_21_update_B03_Heating_ownCells.ifc"""
        ifc_names = {IFCDomain.hydraulic:
                         '2022_11_21_update_B03_Heating_ownCells.ifc'}
        project = self.create_project(ifc_names, 'hkesim')
        answers = (None, 'HVAC-PipeFitting', 'HVAC-Distributor',
                   'HVAC-ThreeWayValve',
                   # 6x dead ends
                   *(True,) * 6,
                   # boiler: nominal flow temperature
                   70,
                   # boiler: rated power consumption
                   150,
                   # boiler: nominal return temperature
                   50)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        graph = project.playground.state['graph']
        aggregated = Counter((type(item) for item in graph.element_graph.nodes))
        self.assertIn(ConsumerHeatingDistributorModule, aggregated)
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
