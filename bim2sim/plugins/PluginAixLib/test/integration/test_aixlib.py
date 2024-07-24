import unittest
from collections import Counter

from bim2sim import ConsoleDecisionHandler, run_project
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.export.modelica import Instance
from bim2sim.elements.aggregation.hvac_aggregations import \
    ConsumerHeatingDistributorModule
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import IFCDomain


class IntegrationBaseAixLib(IntegrationBase):
    def tearDown(self):
        Instance.lookup = {}
        super().tearDown()

    def model_domain_path(self) -> str:
        return 'hydraulic'


class TestIntegrationAixLib(IntegrationBaseAixLib, unittest.TestCase):

    def test_vereinshaus1_aixlib(self):
        """Run project with
        KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc"""
        ifc_names = {IFCDomain.hydraulic: 
                         'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'}
        project = self.create_project(ifc_names, 'aixlib')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   '2lU4kSSzH16v7KPrwcL7KZ', '0t2j$jKmf74PQpOI0ZmPCc',
                   # 1x expansion tank and 17x dead end
                   *(True,) * 18,
                   # boiler efficiency
                   0.9,
                   # boiler flow temperature
                   50,
                   # boiler nominal consumption
                   150,
                   # boiler return temperature
                   70,
                   # volume of junctions
                   *(0.1,) * 35,
                   # 2x pumps: pressure difference, volume flow rate
                   *(1e5, 120) * 2,
                   # 11x space heater: flow temperature, rated_power,
                   # return temperature
                   *(70, 10, 50) * 11,
                   # storage: diameter
                   1,
                   # storage: height
                   2)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_b03_heating(self):
        """Run project with 2022_11_21_update_B03_Heating_ownCells"""
        ifc_names = {IFCDomain.hydraulic:
                         '2022_11_21_update_B03_Heating_ownCells.ifc'}
        project = self.create_project(ifc_names, 'aixlib')
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
                   # boiler: flow temperature
                   50,
                   # boiler: power consumption
                   150,
                   # boiler: return temperature
                   70,
                   # junction: volume
                   0.1,
                   # pump: rated pressure difference
                   1e5,
                   # pump: rated volume flow
                   120,
                   # 7x space heater: heat capacity
                   *(10,) * 7,
                   # three-way valve: nominal mass flow rate
                   30,
                   # three-way valve: nominal pressure difference
                   250)
        # handler = ConsoleDecisionHandler()
        # run_project(project, handler)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        graph = project.playground.state['graph']
        aggregated = Counter((type(item) for item in graph.element_graph.nodes))
        self.assertIn(ConsumerHeatingDistributorModule, aggregated)
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_b03_heating_with_all_aggregations(self):
        """Run project with 2022_11_21_update_B03_Heating_ownCells"""
        ifc_names = {IFCDomain.hydraulic: 
                         '2022_11_21_update_B03_Heating_ownCells.ifc'}
        project = self.create_project(ifc_names, 'aixlib')
        answers = (None, 'HVAC-PipeFitting', 'HVAC-Distributor',
                   'HVAC-ThreeWayValve',
                   # 6x dead ends
                   *(True,) * 6,
                   # boiler: efficiency
                   0.9,
                   # boiler: flow temperature
                   50,
                   # boiler: power consumption
                   150,
                   # boiler: return temperature
                   70,
                   # 7x space heater: heat capacity
                   *(10,) * 7)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        graph = project.playground.state['graph']
        aggregated = Counter((type(item) for item in graph.element_graph.nodes))
        # TODO check generator
        self.assertIn(ConsumerHeatingDistributorModule, aggregated)
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    # def test_run_digitalhub_hvac(self):
    #     """Run project with FM_HZG_DigitalHub.ifc"""
    #     ifc_names = {IFCDomain.hydraulic: 
    #                      'FM_HZG_DigitalHub.ifc'}
    #     project = self.create_project(ifc_names, 'aixlib')
    #     answers = (('HVAC-ThreeWayValve')*3, ('HVAC-PipeFitting')*19,   *(None,)*100,)
    #     handler = DebugDecisionHandler(answers)
    #     project.workflow.fuzzy_threshold = 0.5
    #     for decision, answer in handler.decision_answer_mapping(project.run()):
    #         decision.value = answer
    #     print('test')
