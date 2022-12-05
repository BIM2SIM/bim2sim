import unittest
from collections import Counter
from pathlib import Path

from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.decision.console import ConsoleDecisionHandler
from bim2sim.kernel.aggregation import ConsumerHeatingDistributorModule
from bim2sim.utilities.test import IntegrationBase
from bim2sim.export.modelica import Instance


class IntegrationBaseAixLib(IntegrationBase):
    def tearDown(self):
        Instance.lookup = {}
        super().tearDown()

    def model_path(self) -> Path:
        return Path(__file__).parent.parent.parent / 'test/TestModels/HVAC'


class TestIntegrationAixLib(IntegrationBaseAixLib, unittest.TestCase):

    def test_vereinshaus1_aixlib(self):
        """Run project with
        KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
        project = self.create_project(ifc, 'aixlib')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   '2lU4kSSzH16v7KPrwcL7KZ', '0t2j$jKmf74PQpOI0ZmPCc',
                   # 1x expansion tank and 16x dead end
                   *(True,)*17,
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

    def test_run_b03_heating(self):
        """Run project with 2022_11_21_B03_Heating_ownCells"""
        ifc = '2022_11_21_B03_Heating_ownCells.ifc'
        project = self.create_project(ifc, 'aixlib')
        project.workflow.aggregations = [
            'UnderfloorHeating',
            'Consumer',
            'PipeStrand',
            'ParallelPump',
            # 'ParallelSpaceHeater',
            'ConsumerHeatingDistributorModule',
            # 'GeneratorOneFluid'
        ]
        answers = ('HVAC-Distributor', *('HVAC-ThreeWayValve',) * 2,
                   *('HVAC-Valve',) * 14, *(None,) * 2,
                   *(True,) * 5, 0.75, 50,
                   # rated current, rated height, rated_voltage,
                   # rated_volume_flow for pumps
                    150, 70, 50, 50,
                   # body mass and heat capacity for all space heaters
                   *(1, 500,) * 7)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer

        graph = project.playground.state['graph']
        aggregated = Counter((type(item) for item in graph.element_graph.nodes))
        self.assertIn(ConsumerHeatingDistributorModule, aggregated)
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
