import unittest
from unittest import mock

from bim2sim.kernel import aggregation
from bim2sim.kernel.element import Element, Port
from bim2sim.kernel.elements import Pipe, Pump, PipeFitting

from .base import TestAggregation


class TestParallelPumps(TestAggregation):

    pipes = []
    fittings = []
    pumps = []

    @classmethod
    def setUpClass(cls):

        with mock.patch.object(Element, '_add_ports', return_value=None):
            # pipes
            for i in range(10):
                # pip instances
                pipe = Pipe(cls.ifc)
                cls.pipes.append(pipe)
                # attributes
                pipe.length = 200
                pipe.diameter = 20

            # fittings
            for i in range(3):
                # pip instances
                fitting = PipeFitting(cls.ifc)
                cls.fittings.append(fitting)
                # attributes
                pipe.length = 200
                pipe.diameter = 20

            # pumps
            for i in range(6):
                pump = Pump(cls.ifc)
                cls.pumps.append(pump)
                # attributes
                pump.diameter = 20  # mm
                pump.rated_power = .15  # kW
                pump.rated_height = 6 if i < 5 else 12  # m
                pump.rated_volume_flow = 3  # m³/h

        # add ports
        for pipe in cls.pipes:
            cls.fake_add_ports(pipe)
        for fitting in cls.fittings:
            cls.fake_add_ports(fitting, 3)
        for pump in cls.pumps:
            cls.fake_add_ports(pump)

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()

        for item in cls.pipes + cls.fittings + cls.pumps:
            item.discard()

    def get_setup1(self):
        """
         |
        -+-
        A A
        -+-
         |
        """
        p1 = self.pipes[0]
        p2 = self.pipes[1]
        p3 = self.pipes[2]
        p4 = self.pipes[3]
        p5 = self.pipes[4]
        p6 = self.pipes[5]
        f1 = self.fittings[0]
        f2 = self.fittings[1]
        pump1 = self.pumps[0]
        pump2 = self.pumps[1]

        setup = list(locals().values())
        setup.remove(self)

        p1.ports[1].connect(f1.ports[0])
        f1.ports[1].connect(p2.ports[0])
        f1.ports[2].connect(p3.ports[0])
        p2.ports[1].connect(pump1.ports[0])
        p3.ports[1].connect(pump2.ports[0])
        pump1.ports[1].connect(p4.ports[0])
        pump2.ports[1].connect(p5.ports[0])
        p4.ports[1].connect(f2.ports[0])
        p5.ports[1].connect(f2.ports[1])
        f2.ports[2].connect(p6.ports[0])

        return setup

    def get_setup2(self):
        """
          |
        --+
        A A
        +--
        |
        """
        p1 = self.pipes[0]
        p2 = self.pipes[1]
        p3 = self.pipes[2]
        p4 = self.pipes[3]
        p5 = self.pipes[4]
        p6 = self.pipes[5]
        f1 = self.fittings[0]
        f2 = self.fittings[1]
        pump1 = self.pumps[0]
        pump2 = self.pumps[1]

        setup = list(locals().values())
        setup.remove(self)

        p1.ports[1].connect(f1.ports[0])
        f1.ports[1].connect(p2.ports[0])
        p2.ports[1].connect(p3.ports[0])
        f1.ports[2].connect(pump1.ports[0])
        p3.ports[1].connect(pump2.ports[0])
        pump1.ports[1].connect(p4.ports[0])
        p4.ports[1].connect(p5.ports[0])
        p5.ports[1].connect(f2.ports[0])
        pump2.ports[1].connect(f2.ports[1])
        f2.ports[2].connect(p6.ports[0])

        return setup

    def test_pump_setup1(self):
        """Two parallel pumps v1"""
        models = self.get_setup1()
        pumps = [item for item in models if isinstance(item, Pump)]

        agg_pump = aggregation.ParallelPump("Test", models)

        expected_power = sum([p.rated_power for p in pumps])
        expected_height = sum([p.rated_height for p in pumps]) / len(pumps)  # only for same size pumps
        expected_volume_flow = sum([p.rated_volume_flow for p in pumps])

        self.assertAlmostEqual(agg_pump.rated_volume_flow, expected_volume_flow)
        self.assertAlmostEqual(agg_pump.rated_height, expected_height)
        self.assertAlmostEqual(agg_pump.rated_power, expected_power)

        self.assertAlmostEqual(agg_pump.diameter, 20)

        mapping = agg_pump.get_replacement_mapping()

        self.assertIs(agg_pump.ports[0], mapping[models[0].ports[0]])
        self.assertIs(agg_pump.ports[1], mapping[models[-1].ports[1]])

    def test_pump_setup2(self):
        """Two parallel pumps v2"""
        models = self.get_setup2()
        pumps = [item for item in models if isinstance(item, Pump)]

        agg_pump = aggregation.ParallelPump("Test", models)

        expected_power = sum([p.rated_power for p in pumps])
        expected_height = sum([p.rated_height for p in pumps]) / len(pumps)  # only for same size pumps
        expected_volume_flow = sum([p.rated_volume_flow for p in pumps])

        self.assertAlmostEqual(agg_pump.rated_volume_flow, expected_volume_flow)
        self.assertAlmostEqual(agg_pump.rated_height, expected_height)
        self.assertAlmostEqual(agg_pump.rated_power, expected_power)

        self.assertAlmostEqual(agg_pump.diameter, 20)

        mapping = agg_pump.get_replacement_mapping()

        self.assertIs(agg_pump.ports[0], mapping[models[0].ports[0]])
        self.assertIs(agg_pump.ports[1], mapping[models[-1].ports[1]])

    def test_pump_same_size(self):
        """ParallelPumps only for same sized pumps"""
        pumps = self.pumps[-2:-1]

        with self.assertRaises(Exception):
            agg_pump = aggregation.ParallelPump("Test", pumps)

    @unittest.skip("Not implemented")
    def test_detection(self):
        pass


if __name__ == '__main__':
    unittest.main()
