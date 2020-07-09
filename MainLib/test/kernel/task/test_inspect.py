import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

from bim2sim.kernel.element import Root
from bim2sim.task import hvac, common
from bim2sim.task.hvac import Inspect
from bim2sim.workflow import PlantSimulation
from bim2sim.project import PROJECT, _Project
from bim2sim import BIM2SIMManager


class DummyManager(BIM2SIMManager):

    def run(self):
        self.playground.run_task(hvac.SetIFCTypesHVAC())
        self.playground.run_task(common.LoadIFC())
        self.playground.run_task(hvac.Prepare())
        self.playground.run_task(hvac.Inspect())


sample_root = Path(__file__).parent.parent.parent / 'TestModels'


class TestInspect(unittest.TestCase):
    """Basic scenario for connection tests with HeatExchanger (IfcPipeFitting) and four Pipes (IfcPipeSegment)"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.TemporaryDirectory()
        # PROJECT.root = cls.test_dir.name
        print(cls.test_dir.name)
        PROJECT.create(cls.test_dir.name)

    @classmethod
    def tearDownClass(cls):
        print('tear down class')
        PROJECT.root = None
        try:
            cls.test_dir.cleanup()
        except PermissionError:
            # for unknown reason the empty folder contend is cleared but folder itself cant be removed --> ignore
            pass

    def setUp(self):
        workflow = PlantSimulation()
        self.manager = DummyManager(workflow)

    def tearDown(self):
        # clear objects
        for r in Root.objects.copy().values():
            r.discard()

        self.manager = None

    @patch.object(_Project, 'ifc', sample_root / 'B01_2_HeatExchanger_Pipes.ifc')
    def test_case_1(self):
        """HeatExchange with 4 (semantically) connected pipes"""

        self.manager.run()
        self.manager.playground.state

        heat_exchanger = Root.objects.get('0qeZDHlQRzcKJYopY4$fEf')
        self.assertEqual(4, len([port for port in heat_exchanger.ports if port.connection]))

        for port in heat_exchanger.ports:
            print(port.position)

    @patch.object(_Project, 'ifc', sample_root / 'B01_3_HeatExchanger_noPorts.ifc')
    def test_case_2(self):
        """HeatExchange and Pipes are exported without ports"""

        self.manager.run()

        heat_exchanger = Root.objects.get('0qeZDHlQRzcKJYopY4$fEf')
        self.assertEqual(0, len([port for port in heat_exchanger.ports if port.connection]))

        # assert warnings ??

    @patch.object(_Project, 'ifc', sample_root / 'B01_4_HeatExchanger_noConnection.ifc')
    def test_case_3(self):
        """No connections but ports are less than 10 mm apart"""

        self.manager.run()

        heat_exchanger = Root.objects.get('3FQzmSvzrgbaIM6zA4FX8S')
        self.assertEqual(4, len([port for port in heat_exchanger.ports if port.connection]))

    @patch.object(_Project, 'ifc', sample_root / 'B01_5_HeatExchanger_mixConnection.ifc')
    def test_case_4(self):
        """Mix of case 1 and 3"""

        self.manager.run()

        heat_exchanger = Root.objects.get('3FQzmSvzrgbaIM6zA4FX8S')
        self.assertEqual(2, len([port for port in heat_exchanger.ports if port.connection]))
