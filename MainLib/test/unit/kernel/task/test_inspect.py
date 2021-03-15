import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

import numpy as np

from bim2sim.kernel.element import Root, BasePort, BaseElement, IFCBased
from bim2sim.task import hvac
from bim2sim.task import common
from bim2sim.task.hvac import Inspect
from bim2sim.workflow import PlantSimulation
from bim2sim.project import PROJECT, _Project
from bim2sim import BIM2SIMManager
from bim2sim.decision import Decision


class DummyManager(BIM2SIMManager):

    def run(self):
        self.playground.run_task(hvac.SetIFCTypesHVAC())
        self.playground.run_task(common.LoadIFC())
        self.playground.run_task(hvac.Prepare())
        self.playground.run_task(hvac.Inspect())


sample_root = Path(__file__).parent.parent.parent.parent / 'TestModels'


class TestInspect(unittest.TestCase):
    """Basic scenario for connection tests with HeatExchanger (IfcPipeFitting) and four Pipes (IfcPipeSegment)"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.TemporaryDirectory()
        # PROJECT.root = cls.test_dir.name
        print(cls.test_dir.name)
        PROJECT.create(cls.test_dir.name)

        IFCBased.finder.enabled = False

    @classmethod
    def tearDownClass(cls):
        print('tear down class')
        PROJECT.root = None
        try:
            cls.test_dir.cleanup()
        except PermissionError:
            # for unknown reason the empty folder contend is cleared but folder itself cant be removed --> ignore
            pass
        IFCBased.finder.enabled = True

    def setUp(self):
        workflow = PlantSimulation()
        self.manager = DummyManager(workflow)

    def tearDown(self):
        # clear objects
        for r in Root.objects.copy().values():
            r.discard()

        self.manager = None
        Decision.reset_decisions()

    @patch.object(_Project, 'ifc', sample_root / 'B01_2_HeatExchanger_Pipes.ifc')
    def test_case_1(self):
        """HeatExchange with 4 (semantically) connected pipes"""

        with Decision.debug_answer('IfcHeatPump', validate=True):
            self.manager.run()

        heat_exchanger = Root.objects.get('0qeZDHlQRzcKJYopY4$fEf')
        self.assertEqual(4, len([port for port in heat_exchanger.ports if port.connection]))

    @patch.object(_Project, 'ifc', sample_root / 'B01_3_HeatExchanger_noPorts.ifc')
    def test_case_2(self):
        """HeatExchange and Pipes are exported without ports"""

        with Decision.debug_answer('IfcHeatPump', validate=True):
            self.manager.run()

        heat_exchanger = Root.objects.get('0qeZDHlQRzcKJYopY4$fEf')
        self.assertEqual(0, len([port for port in heat_exchanger.ports if port.connection]))

        # assert warnings ??

    @patch.object(_Project, 'ifc', sample_root / 'B01_4_HeatExchanger_noConnection.ifc')
    def test_case_3(self):
        """No connections but ports are less than 10 mm apart"""

        with Decision.debug_answer('IfcHeatPump', validate=True):
            self.manager.run()

        heat_exchanger = Root.objects.get('3FQzmSvzrgbaIM6zA4FX8S')
        self.assertEqual(4, len([port for port in heat_exchanger.ports if port.connection]))

    @patch.object(_Project, 'ifc', sample_root / 'B01_5_HeatExchanger_mixConnection.ifc')
    def test_case_4(self):
        """Mix of case 1 and 3"""

        with Decision.debug_answer('IfcHeatPump', validate=True):
            self.manager.run()

        heat_exchanger = Root.objects.get('3FQzmSvzrgbaIM6zA4FX8S')
        self.assertEqual(4, len([port for port in heat_exchanger.ports if port.connection]))


class TestInspectMethods(unittest.TestCase):

    def tearDown(self) -> None:
        for item in list(BaseElement.objects.values()):
            item.discard()

        for port in list(BasePort.objects.values()):
            port.discard()

    @staticmethod
    def create_element(positions):
        parent = BaseElement()
        for pos in positions:
            port = BasePort(parent)
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
        connections = Inspect.connections_by_position(parent1.ports + parent2.ports, eps=10)
        self.assertEqual(1, len(connections))
        self.assertSetEqual({parent1.ports[1], parent2.ports[0]}, set(connections[0]))

        # accepted distance
        connections = Inspect.connections_by_position(parent2.ports + parent3.ports, eps=10)
        self.assertEqual(1, len(connections), "One valid connection")
        self.assertSetEqual({parent2.ports[1], parent3.ports[0]}, set(connections[0]))

        # not accepted distance
        connections = Inspect.connections_by_position(parent1.ports + parent3.ports, eps=10)
        self.assertEqual(0, len(connections), "Not accepted distance")

        # no connections within element
        connections = Inspect.connections_by_position(parent4.ports, eps=10)
        self.assertEqual(0, len(connections), "No connections within element")

        # multiple possibilities
        connections = Inspect.connections_by_position(parent1.ports + parent2.ports + parent5.ports, eps=10)
        self.assertEqual(1, len(connections), "Only one connection per port allowed")
        self.assertSetEqual({parent1.ports[1], parent2.ports[0]}, set(connections[0]))
