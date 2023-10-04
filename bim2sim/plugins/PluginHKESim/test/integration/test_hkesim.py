import unittest
from collections import Counter

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.export.modelica import Instance
from bim2sim.elements.aggregation.hvac_aggregations \
    import ConsumerHeatingDistributorModule
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import IFCDomain


class IntegrationBaseHKESIM(IntegrationBase):
    def tearDown(self):
        Instance.lookup = {}
        super().tearDown()

    def model_domain_path(self) -> str:
        return 'hydraulic'


class TestIntegrationHKESIM(IntegrationBaseHKESIM, unittest.TestCase):

    def test_run_vereinshaus1(self):
        """Run project with
        KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc"""
        ifc_names = {IFCDomain.hydraulic:
                         'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'}
        project = self.create_project(ifc_names, 'hkesim')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   '2lU4kSSzH16v7KPrwcL7KZ', '0t2j$jKmf74PQpOI0ZmPCc',
                   *(True,)*18,
                   # boiler efficiency
                   0.9,
                   # boiler power
                   150,
                   # current, height, voltage, vol_flow of pump
                   *(2, 5, 230, 1) * 2,
                   # power of space heaters
                   *(1,) * 11)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    # def test_run_vereinshaus2(self):
    #     """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc"""
    #     ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'
    #     project = self.create_project(ifc, 'hkesim')
    #     answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
    #                '0k0IjzL0z6aOYAX23H_dA5', '1U379nXO902R21a41MGQRw',
    #                *(True,)*13,
    #                200, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5)
    #     handler = DebugDecisionHandler(answers)
    #     for decision, answer in handler.decision_answer_mapping(project.run()):
    #         decision.value = answer
    #     self.assertEqual(0, handler.return_value,
    #                      "Project did not finish successfully.")

    def test_run_b03_heating(self):
        """Run project with B03_Heating.ifc"""
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
        default_logging_setup()
        answers = (None, 'HVAC-PipeFitting', 'HVAC-Distributor',
                   'HVAC-ThreeWayValve',
                   # 7 dead ends
                   *(True,) * 7, 0.75, 50, 150, 70, *(1, 500,) * 7)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        graph = project.playground.state['graph']
        aggregated = Counter((type(item) for item in graph.element_graph.nodes))
        self.assertIn(ConsumerHeatingDistributorModule, aggregated)
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
