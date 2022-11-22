import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

import numpy as np

from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.element import Element, Port, ProductBased
from bim2sim.kernel.elements.hvac import HeatExchanger, Pipe, PipeFitting
from bim2sim.task import hvac
from bim2sim.task import common
from bim2sim.task.hvac import ConnectElements
from bim2sim.workflow import PlantSimulation
from bim2sim.project import Project, FolderStructure
from bim2sim.plugins import Plugin


class PluginDummy(Plugin):
    name = 'test'
    default_workflow = PlantSimulation
    elements = {Pipe, PipeFitting, HeatExchanger}
    default_tasks = [
        common.LoadIFC,
        common.CreateElements,
        hvac.ConnectElements
    ]
    #
    # def run(self, playground):
    #     playground.run_task(hvac.SetIFCTypesHVAC())
    #     playground.run_task(common.LoadIFC())
    #     playground.run_task(common.CreateElements())
    #     playground.run_task(hvac.ConnectElements())


sample_root = Path(__file__).parent.parent.parent.parent / 'TestModels'


class TestInspect(unittest.TestCase):
    """Basic scenario for connection tests with HeatExchanger (IfcPipeFitting) and four Pipes (IfcPipeSegment)"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.TemporaryDirectory()
        print(cls.test_dir.name)

        # create initial folder structure
        project = Project.create(cls.test_dir.name, plugin=PluginDummy)
        # deactivate created project
        project.finalize(True)

    @classmethod
    def tearDownClass(cls):
        cls.test_dir.cleanup()

    def setUp(self) -> None:
        self.project = Project(self.test_dir.name, plugin=PluginDummy)

    def tearDown(self):
        self.project.finalize()

    def test_case_1(self):
        """HeatExchange with 4 (semantically) connected pipes"""
        with patch.object(FolderStructure, 'ifc',
                          sample_root / 'B01_2_HeatExchanger_Pipes.ifc'):
            handler = DebugDecisionHandler(["Other", HeatExchanger.key])
            handler.handle(self.project.run(cleanup=False))

        instances = self.project.playground.state['instances']
        heat_exchanger = instances.get('0qeZDHlQRzcKJYopY4$fEf')
        self.assertEqual(4, len([port for port in heat_exchanger.ports if port.connection]))

    def test_case_2(self):
        """HeatExchange and Pipes are exported without ports"""
        with patch.object(FolderStructure, 'ifc',
                          sample_root / 'B01_3_HeatExchanger_noPorts.ifc'):
            handler = DebugDecisionHandler(["Other", HeatExchanger.key])
            handler.handle(self.project.run(cleanup=False))
        instances = self.project.playground.state['instances']
        heat_exchanger = instances.get('0qeZDHlQRzcKJYopY4$fEf')
        self.assertEqual(0, len([port for port in heat_exchanger.ports
                                 if port.connection]))

        # assert warnings ??

    def test_case_3(self):
        """No connections but ports are less than 10 mm apart"""
        with patch.object(FolderStructure, 'ifc',
                          sample_root / 'B01_4_HeatExchanger_noConnection.ifc'):
            handler = DebugDecisionHandler(["Other", HeatExchanger.key])
            handler.handle(self.project.run(cleanup=False))

        instances = self.project.playground.state['instances']
        heat_exchanger = instances.get('3FQzmSvzrgbaIM6zA4FX8S')
        self.assertEqual(4, len([port for port in heat_exchanger.ports
                                 if port.connection]))

    def test_case_4(self):
        """Mix of case 1 and 3"""
        file = 'B01_5_HeatExchanger_mixConnection.ifc'
        with patch.object(FolderStructure, 'ifc', sample_root / file):
            handler = DebugDecisionHandler(["Other", HeatExchanger.key])
            handler.handle(self.project.run(cleanup=False))

        instances = self.project.playground.state['instances']
        heat_exchanger = instances.get('3FQzmSvzrgbaIM6zA4FX8S')
        self.assertEqual(4, len([port for port in heat_exchanger.ports
                                 if port.connection]))


class TestInspectMethods(unittest.TestCase):

    @staticmethod
    def create_element(positions):
        parent = ProductBased()
        for pos in positions:
            port = Port(parent)
            port.calc_position = MagicMock(return_value=np.array(pos))
            parent.ports.append(port)
        return parent

    def test_connect_by_position(self):
        """Test Inspect.connect_by_position by various scenarios"""
        parent1 = self.create_element([[0, 0, 0], [0, 0, 20]])
        parent2 = self.create_element([[0, 0, 20], [0, 0, 40]])
        parent3 = self.create_element([[0, 5, 40], [0, 0, 60]])
        parent4 = self.create_element([[0, 0, 0], [0, 0, 0], [0, 0, 5]])
        parent5 = self.create_element([[0, 0, 25], [0, 20, 0]])

        # no distance
        connections = ConnectElements.connections_by_position(parent1.ports + parent2.ports, eps=10)
        self.assertEqual(1, len(connections))
        self.assertSetEqual({parent1.ports[1], parent2.ports[0]}, set(connections[0]))

        # accepted distance
        connections = ConnectElements.connections_by_position(parent2.ports + parent3.ports, eps=10)
        self.assertEqual(1, len(connections), "One valid connection")
        self.assertSetEqual({parent2.ports[1], parent3.ports[0]}, set(connections[0]))

        # not accepted distance
        connections = ConnectElements.connections_by_position(parent1.ports + parent3.ports, eps=10)
        self.assertEqual(0, len(connections), "Not accepted distance")

        # no connections within element
        connections = ConnectElements.connections_by_position(parent4.ports, eps=10)
        self.assertEqual(0, len(connections), "No connections within element")

        # multiple possibilities
        connections = ConnectElements.connections_by_position(parent1.ports + parent2.ports + parent5.ports, eps=10)
        self.assertEqual(1, len(connections), "Only one connection per port allowed")
        self.assertSetEqual({parent1.ports[1], parent2.ports[0]}, set(connections[0]))
