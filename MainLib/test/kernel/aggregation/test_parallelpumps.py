import unittest
from unittest import mock

from bim2sim.kernel import aggregation
from bim2sim.kernel.element import Element, Port
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph

from test.kernel.aggregation.base import AggregationHelper


class ParallelPumpHelper(AggregationHelper):

    def get_setup_pumps1(self):
        """get consumer circuit made of 6 parallel pumps (one small), space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                elements.PipeFitting, flags=['pumps1'], n_ports=3, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    elements.Pipe, flags=['pumps1'], length=40, diameter=20),
                self.element_generator(
                    elements.Pump, flags=['pumps1'], rated_power=1, rated_height=8, rated_volume_flow=6),
                self.element_generator(
                    elements.Pipe, flags=['pumps1'], length=40, diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    elements.Pipe, flags=['pumps1'], length=40, diameter=20),
                self.element_generator(
                    elements.Pump, flags=['pumps1'], rated_power=1, rated_height=8, rated_volume_flow=6),
                self.element_generator(
                    elements.Pipe, flags=['pumps1'], length=40, diameter=20),
            ]
            fitting2 = self.element_generator(
                elements.PipeFitting, flags=['pumps1'], n_ports=3, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(3)]
            consumer = self.element_generator(
                elements.SpaceHeater)
            con_rl_a = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(6)]

        # connect
        self.connect_strait([*con_vl_a, fitting1])
        self.connect_strait([fitting1, *p_pump1_p, fitting2])
        self.connect_strait(p_pump2_p)
        fitting1.ports[2].connect(p_pump2_p[0].ports[0])
        p_pump2_p[-1].ports[1].connect(fitting2.ports[2])
        self.connect_strait([fitting2, *con_vl_b, consumer, *con_rl_a])

        # full system
        gen_circuit = [
            *con_vl_a, fitting1, *p_pump1_p, *p_pump2_p, fitting2,
            *con_vl_b, consumer, *con_rl_a
        ]

        flags['connect'] = [con_vl_a[0], con_rl_a[-1]]

        graph = HvacGraph(gen_circuit)
        # graph.plot(r'c:\temp')
        return graph, flags

    def get_setup_pumps2(self):
        """get consumer circuit made of 5 parallel pumps (one small), space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                elements.PipeFitting, flags=['pumps', 'normal', 'small'], n_ports=6, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    elements.Pipe, flags=['pumps', 'normal'], length=40, diameter=20),
                self.element_generator(
                    elements.Pump, flags=['pumps', 'normal'], rated_power=1, rated_height=8, rated_volume_flow=6),
                self.element_generator(
                    elements.Pipe, flags=['pumps', 'normal'], length=40, diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    elements.Pipe, flags=['pumps', 'normal'], length=40, diameter=20),
                self.element_generator(
                    elements.Pump, flags=['pumps', 'normal'], rated_power=1, rated_height=8, rated_volume_flow=6),
                self.element_generator(
                    elements.Pipe, flags=['pumps', 'normal'], length=40, diameter=20),
            ]
            p_pump3_p = [
                self.element_generator(
                    elements.Pipe, flags=['pumps', 'normal'], length=40, diameter=20),
                self.element_generator(
                    elements.Pump, flags=['pumps', 'normal'], rated_power=1, rated_height=8, rated_volume_flow=6),
                self.element_generator(
                    elements.Pipe, flags=['pumps', 'normal'], length=40, diameter=20),
            ]
            p_pump4_p = [
                self.element_generator(
                    elements.Pipe, flags=['pumps', 'normal'], length=40, diameter=20),
                self.element_generator(
                    elements.Pump, flags=['pumps', 'normal'], rated_power=1, rated_height=8, rated_volume_flow=6),
                self.element_generator(
                    elements.Pipe, flags=['pumps', 'normal'], length=40, diameter=20),
            ]
            p_pump5_p = [
                self.element_generator(
                    elements.Pipe, flags=['pumps', 'small'], length=40, diameter=15),
                self.element_generator(
                    elements.Pump, flags=['pumps', 'small'], rated_power=0.22, rated_height=8, rated_volume_flow=0.8),
                self.element_generator(
                    elements.Pipe, flags=['pumps', 'small'], length=40, diameter=15),
            ]
            fitting2 = self.element_generator(
                elements.PipeFitting, flags=['pumps', 'normal', 'small'], n_ports=6, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(3)]
            consumer = self.element_generator(
                elements.SpaceHeater)
            con_rl_a = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(6)]

        # connect
        self.connect_strait([*con_vl_a, fitting1])
        self.connect_strait([fitting1, *p_pump1_p, fitting2])
        self.connect_strait(p_pump2_p)
        self.connect_strait(p_pump3_p)
        self.connect_strait(p_pump4_p)
        self.connect_strait(p_pump5_p)
        fitting1.ports[2].connect(p_pump2_p[0].ports[0])
        fitting1.ports[3].connect(p_pump3_p[0].ports[0])
        fitting1.ports[4].connect(p_pump4_p[0].ports[0])
        fitting1.ports[5].connect(p_pump5_p[0].ports[0])
        p_pump2_p[-1].ports[1].connect(fitting2.ports[2])
        p_pump3_p[-1].ports[1].connect(fitting2.ports[3])
        p_pump4_p[-1].ports[1].connect(fitting2.ports[4])
        p_pump5_p[-1].ports[1].connect(fitting2.ports[5])
        self.connect_strait([fitting2, *con_vl_b, consumer, *con_rl_a])

        # full system
        gen_circuit = [
            *con_vl_a, fitting1, *p_pump1_p, *p_pump2_p, *p_pump3_p, *p_pump4_p, *p_pump5_p
            , fitting2, *con_vl_b, consumer, *con_rl_a
        ]

        flags['connect'] = [con_vl_a[0], con_rl_a[-1]]

        graph = HvacGraph(gen_circuit)
        # graph.plot(r'c:\temp')
        return graph, flags

    def get_setup(self):
        """Simple generator system made of boiler, pump, expansion tank, distributor and pipes"""
        graph1, flags1 = super().get_setup()
        graph2, flags2 = self.get_setup_pumps1()

        distributor = flags1['distributor'][0]
        vl, rl = flags2['connect']
        distributor.ports[2].connect(vl.ports[0])
        rl.ports[1].connect(distributor.ports[3])

        ele = graph1.elements + graph2.elements
        graph = HvacGraph(ele)
        return graph, flags1.update(**flags2)


class TestParallelPumps(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = ParallelPumpHelper()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.helper.reset()

    # @classmethod
    # def setUpClass(cls):
    #     pipes = []
    #     fittings = []
    #     pumps = []
    #
    #     with mock.patch.object(Element, '_add_ports', return_value=None):
    #         # pipes
    #         for i in range(10):
    #             # pip instances
    #             pipe = Pipe(cls.ifc)
    #             pipes.append(pipe)
    #             # attributes
    #             pipe.length = 200
    #             pipe.diameter = 20
    #
    #         # fittings
    #         for i in range(3):
    #             # pip instances
    #             fitting = PipeFitting(cls.ifc)
    #             fittings.append(fitting)
    #             # attributes
    #             pipe.length = 200
    #             pipe.diameter = 20
    #
    #         # pumps
    #         for i in range(6):
    #             pump = Pump(cls.ifc)
    #             pumps.append(pump)
    #             # attributes
    #             pump.diameter = 20  # mm
    #             pump.rated_power = .15  # kW
    #             pump.rated_height = 6 if i < 5 else 12  # m
    #             pump.rated_volume_flow = 3  # m³/h
    #
    #     # add ports
    #     for pipe in pipes:
    #         cls.fake_add_ports(pipe)
    #     for fitting in fittings:
    #         cls.fake_add_ports(fitting, 3)
    #     for pump in pumps:
    #         cls.fake_add_ports(pump)

    # @classmethod
    # def tearDownClass(cls) -> None:
    #     super().tearDownClass()
    #
    #     for item in cls.pipes + cls.fittings + cls.pumps:
    #         item.discard()

    # def get_setup1(self):
    #     """
    #      |
    #     -+-
    #     A A
    #     -+-
    #      |
    #     """
    #     p1 = self.pipes[0]
    #     p2 = self.pipes[1]
    #     p3 = self.pipes[2]
    #     p4 = self.pipes[3]
    #     p5 = self.pipes[4]
    #     p6 = self.pipes[5]
    #     f1 = self.fittings[0]
    #     f2 = self.fittings[1]
    #     pump1 = self.pumps[0]
    #     pump2 = self.pumps[1]
    #
    #     setup = list(locals().values())
    #     setup.remove(self)
    #
    #     p1.ports[1].connect(f1.ports[0])
    #     f1.ports[1].connect(p2.ports[0])
    #     f1.ports[2].connect(p3.ports[0])
    #     p2.ports[1].connect(pump1.ports[0])
    #     p3.ports[1].connect(pump2.ports[0])
    #     pump1.ports[1].connect(p4.ports[0])
    #     pump2.ports[1].connect(p5.ports[0])
    #     p4.ports[1].connect(f2.ports[0])
    #     p5.ports[1].connect(f2.ports[1])
    #     f2.ports[2].connect(p6.ports[0])
    #
    #     return setup
    #
    # def get_setup2(self):
    #     """
    #       |
    #     --+
    #     A A
    #     +--
    #     |
    #     """
    #     p1 = self.pipes[0]
    #     p2 = self.pipes[1]
    #     p3 = self.pipes[2]
    #     p4 = self.pipes[3]
    #     p5 = self.pipes[4]
    #     p6 = self.pipes[5]
    #     f1 = self.fittings[0]
    #     f2 = self.fittings[1]
    #     pump1 = self.pumps[0]
    #     pump2 = self.pumps[1]
    #
    #     setup = list(locals().values())
    #     setup.remove(self)
    #
    #     p1.ports[1].connect(f1.ports[0])
    #     f1.ports[1].connect(p2.ports[0])
    #     p2.ports[1].connect(p3.ports[0])
    #     f1.ports[2].connect(pump1.ports[0])
    #     p3.ports[1].connect(pump2.ports[0])
    #     pump1.ports[1].connect(p4.ports[0])
    #     p4.ports[1].connect(p5.ports[0])
    #     p5.ports[1].connect(f2.ports[0])
    #     pump2.ports[1].connect(f2.ports[1])
    #     f2.ports[2].connect(p6.ports[0])
    #
    #     return setup

    def test_pump_setup1(self):
        """Two parallel pumps"""

        graph, flags = self.helper.get_setup_pumps1()
        models = flags['pumps1']
        pumps = [item for item in models if isinstance(item, elements.Pump)]

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
        graph, flags = self.helper.get_setup_pumps2()
        models = flags['normal']
        pumps = [item for item in models if isinstance(item, elements.Pump)]

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
        graph, flags = self.helper.get_setup_pumps2()
        models = flags['pumps']

        with self.assertRaises(Exception):
            agg_pump = aggregation.ParallelPump("Test", models)

    @unittest.skip("Not implemented")
    def test_detection(self):
        pass


if __name__ == '__main__':
    unittest.main()
