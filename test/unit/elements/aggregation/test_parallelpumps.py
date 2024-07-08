import unittest

import networkx as nx

import bim2sim.elements.aggregation.hvac_aggregations
from bim2sim.elements import aggregation
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from test.unit.elements.helper import SetupHelperHVAC


class ParallelPumpHelper(SetupHelperHVAC):

    def get_setup_pumps1(self):
        """get consumer circuit made of 2 parallel pumps (equal size),
         space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                hvac.PipeFitting, flags=['pumps1'], n_ports=3, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps1'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps1'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps1'], length=40, diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps1'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps1'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps1'], length=40, diameter=20),
            ]
            fitting2 = self.element_generator(
                hvac.PipeFitting, flags=['pumps1'], n_ports=3, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            consumer = self.element_generator(
                hvac.SpaceHeater)
            con_rl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(6)]

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
        return graph, flags

    def get_setup_pumps2(self):
        """get consumer circuit made of 5 parallel pumps (one small),
        space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                hvac.PipeFitting, flags=['pumps2', 'normal', 'small'],
                n_ports=6, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1,
                    rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1,
                    rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
            ]
            p_pump3_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1,
                    rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
            ]
            p_pump4_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1,
                    rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
            ]
            p_pump5_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'small'], length=40,
                    diameter=15),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'small'], rated_power=0.22,
                    rated_height=8,
                    rated_volume_flow=0.8, diameter=15),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'small'], length=40,
                    diameter=15),
            ]
            fitting2 = self.element_generator(
                hvac.PipeFitting, flags=['pumps2', 'normal', 'small'],
                n_ports=6, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            consumer = self.element_generator(
                hvac.SpaceHeater)
            con_rl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(6)]

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
            *con_vl_a, fitting1, *p_pump1_p, *p_pump2_p, *p_pump3_p, *p_pump4_p,
            *p_pump5_p, fitting2, *con_vl_b, consumer, *con_rl_a
        ]

        flags['connect'] = [con_vl_a[0], con_rl_a[-1]]

        graph = HvacGraph(gen_circuit)
        return graph, flags

    def get_setup_pumps3(self):
        """get consumer circuit made of 5 parallel pumps (one small), bypass,
        space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                hvac.PipeFitting, flags=['pumps2', 'normal', 'small'],
                n_ports=7, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40, diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40, diameter=20),
            ]
            p_pump3_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40, diameter=20),
            ]
            p_pump4_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40, diameter=20),
            ]
            p_pump5_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'small'], length=40, diameter=15),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'small'], rated_power=0.22, rated_height=8,
                    rated_volume_flow=0.8, diameter=15),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'small'], length=40, diameter=15),
            ]
            fitting2 = self.element_generator(
                hvac.PipeFitting, flags=['pumps2', 'normal', 'small'],
                n_ports=7, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            consumer = self.element_generator(
                hvac.SpaceHeater)
            con_rl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(6)]
            bypass = [self.element_generator(
                hvac.Pipe, flags=['bypass'], length=60, diameter=30) for
                i in range(3)]

        # connect
        self.connect_strait([*con_vl_a, fitting1])
        self.connect_strait([fitting1, *p_pump1_p, fitting2])
        self.connect_strait(p_pump2_p)
        self.connect_strait(p_pump3_p)
        self.connect_strait(p_pump4_p)
        self.connect_strait(p_pump5_p)
        self.connect_strait([*bypass])
        fitting1.ports[2].connect(p_pump2_p[0].ports[0])
        fitting1.ports[3].connect(p_pump3_p[0].ports[0])
        fitting1.ports[4].connect(p_pump4_p[0].ports[0])
        fitting1.ports[5].connect(p_pump5_p[0].ports[0])
        fitting1.ports[6].connect(bypass[0].ports[0])
        p_pump2_p[-1].ports[1].connect(fitting2.ports[2])
        p_pump3_p[-1].ports[1].connect(fitting2.ports[3])
        p_pump4_p[-1].ports[1].connect(fitting2.ports[4])
        p_pump5_p[-1].ports[1].connect(fitting2.ports[5])
        bypass[-1].ports[1].connect(fitting2.ports[6])
        self.connect_strait([fitting2, *con_vl_b, consumer, *con_rl_a])

        # full system
        gen_circuit = [
            *con_vl_a, fitting1, *p_pump1_p, *p_pump2_p, *p_pump3_p, *p_pump4_p, *p_pump5_p
            , fitting2, *con_vl_b, consumer, *con_rl_a, *bypass
        ]

        flags['connect'] = [con_vl_a[0], con_rl_a[-1]]

        graph = HvacGraph(gen_circuit)
        return graph, flags

    def get_setup_pumps4(self):
        """get consumer circuit made of 4 parallel pumps (one small) with
        pipefittings in between, bypass, space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                hvac.PipeFitting, flags=['pumps4', 'normal'],
                n_ports=5, diameter=30, length=60)
            fitting2 = self.element_generator(
                hvac.PipeFitting, flags=['pumps4', 'normal', 'add'],
                n_ports=3, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps4', 'normal'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps4', 'normal'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps4', 'normal'], length=40, diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps4', 'normal'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps4', 'normal'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps4', 'normal'], length=40, diameter=20),
            ]
            p_pump3_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps4', 'small'], length=40,
                    diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps4', 'small'], rated_power=0.6,
                    rated_height=6,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps4', 'small'], length=40,
                    diameter=20),
            ]
            p_pump4_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps4', 'normal', 'add'],
                    length=40,
                    diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps4', 'normal', 'add'],
                    rated_power=1, rated_height=8, rated_volume_flow=6,
                    diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps4', 'normal', 'add'],
                    length=40, diameter=20),
            ]
            fitting3 = self.element_generator(
                hvac.PipeFitting, flags=['pumps4', 'normal'],
                n_ports=5, diameter=30, length=60)
            fitting4 = self.element_generator(
                hvac.PipeFitting, flags=['pumps4', 'normal', 'add'],
                n_ports=3, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            consumer = self.element_generator(
                hvac.SpaceHeater)
            con_rl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(6)]
            bypass = [self.element_generator(
                hvac.Pipe, flags=['bypass'], length=60, diameter=30) for
                i in range(3)]
        # connect
        # parallel pumps connections VL
        self.connect_strait([*con_vl_a, fitting1])
        self.connect_strait([fitting1, *p_pump1_p, fitting3])
        self.connect_strait([fitting3, *con_vl_b, consumer, *con_rl_a])
        self.connect_strait(bypass)
        self.connect_strait(p_pump2_p)
        self.connect_strait(p_pump3_p)
        self.connect_strait(p_pump4_p)
        fitting1.ports[2].connect(p_pump2_p[0].ports[0])
        fitting1.ports[3].connect(p_pump3_p[0].ports[0])
        # bypass connection VL
        fitting1.ports[4].connect(fitting2.ports[0])
        fitting2.ports[1].connect(p_pump4_p[0].ports[0])
        fitting2.ports[2].connect(bypass[0].ports[0])
        # parallel pumps connection RL
        p_pump2_p[-1].ports[1].connect(fitting3.ports[2])
        p_pump3_p[-1].ports[1].connect(fitting3.ports[3])

        # bypass connection RL
        p_pump4_p[-1].ports[1].connect(fitting4.ports[0])
        fitting4.ports[1].connect(fitting3.ports[4])
        bypass[-1].ports[1].connect(fitting4.ports[2])

        # full system
        gen_circuit = [
            *con_vl_a, fitting1, *p_pump1_p, *p_pump2_p, *p_pump3_p, *p_pump4_p,
            *bypass, fitting2, fitting3, fitting4, *con_vl_b, consumer,
            *con_rl_a
        ]

        flags['connect'] = [con_vl_a[0], con_rl_a[-1]]

        graph = HvacGraph(gen_circuit)
        return graph, flags

    def get_setup_pumps5(self):
        """get consumer circuit made of 5 parallel pumps (one small) with
        additional connection at one edge port that isn't connected to other
        edge port, space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                hvac.PipeFitting, flags=['pumps2', 'normal', 'small'],
                n_ports=7, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1,
                    rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1,
                    rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
            ]
            p_pump3_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1,
                    rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
            ]
            p_pump4_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'normal'], rated_power=1,
                    rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'normal'], length=40,
                    diameter=20),
            ]
            p_pump5_p = [
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'small'], length=40,
                    diameter=15),
                self.element_generator(
                    hvac.Pump, flags=['pumps2', 'small'], rated_power=0.22,
                    rated_height=8,
                    rated_volume_flow=0.8, diameter=15),
                self.element_generator(
                    hvac.Pipe, flags=['pumps2', 'small'], length=40,
                    diameter=15),
            ]
            fitting2 = self.element_generator(
                hvac.PipeFitting, flags=['pumps2', 'normal', 'small'],
                n_ports=6, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            consumer = self.element_generator(
                hvac.SpaceHeater)
            con_rl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(6)]
            add_con = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]

        # connect
        self.connect_strait([*con_vl_a, fitting1])
        self.connect_strait([fitting1, *p_pump1_p, fitting2])
        self.connect_strait(add_con)
        self.connect_strait(p_pump2_p)
        self.connect_strait(p_pump3_p)
        self.connect_strait(p_pump4_p)
        self.connect_strait(p_pump5_p)
        fitting1.ports[2].connect(p_pump2_p[0].ports[0])
        fitting1.ports[3].connect(p_pump3_p[0].ports[0])
        fitting1.ports[4].connect(p_pump4_p[0].ports[0])
        fitting1.ports[5].connect(p_pump5_p[0].ports[0])
        fitting1.ports[6].connect(add_con[0].ports[0])
        p_pump2_p[-1].ports[1].connect(fitting2.ports[2])
        p_pump3_p[-1].ports[1].connect(fitting2.ports[3])
        p_pump4_p[-1].ports[1].connect(fitting2.ports[4])
        p_pump5_p[-1].ports[1].connect(fitting2.ports[5])
        self.connect_strait([fitting2, *con_vl_b, consumer, *con_rl_a])

        # full system
        gen_circuit = [
            *con_vl_a, fitting1, *p_pump1_p, *p_pump2_p, *p_pump3_p, *p_pump4_p,
            *p_pump5_p
            , fitting2, *con_vl_b, consumer, *con_rl_a
        ]

        flags['connect'] = [con_vl_a[0], con_rl_a[-1]]

        graph = HvacGraph(gen_circuit)
        return graph, flags

    def get_setup_system(self):
        """ Simple generator system made of boiler, pump, expansion tank,
            distributor and pipes."""
        graph1, flags1 = super().get_setup_simple_boiler()
        graph2, flags2 = self.get_setup_pumps1()
        graph3, flags3 = self.get_setup_pumps2()

        distributor = flags1['distributor'][0]
        distributor_ports = self.fake_add_ports(distributor, 4)

        vl_p1, rl_p1 = flags2.pop('connect')
        distributor_ports[0].connect(vl_p1.ports[0])
        rl_p1.ports[1].connect(distributor_ports[1])

        vl_p2, rl_p2 = flags3.pop('connect')
        distributor_ports[2].connect(vl_p2.ports[0])
        rl_p2.ports[1].connect(distributor_ports[3])

        ele = graph1.elements + graph2.elements + graph3.elements
        graph = HvacGraph(ele)
        flags = {**flags1, **flags2, **flags3}
        return graph, flags


class TestParallelPumps(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = ParallelPumpHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_pump_setup1(self):
        """ Two parallel pumps."""
        graph, flags = self.helper.get_setup_pumps1()
        models = flags['pumps1']
        pumps = [item for item in models if isinstance(item, hvac.Pump)]
        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump.find_matches(graph)
        self.assertEqual(len(matches), 1)
        agg_pump = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump(graph, matches[0], **meta[0])
        expected_power = sum([p.rated_power for p in pumps])
        expected_height = sum([p.rated_height for p in pumps]) / len(pumps)
        expected_volume_flow = sum([p.rated_volume_flow for p in pumps])
        expected_diamter = sum([p.diameter**2 for p in pumps])**.5

        self.assertAlmostEqual(agg_pump.rated_volume_flow, expected_volume_flow)
        self.assertAlmostEqual(agg_pump.rated_height, expected_height)
        self.assertAlmostEqual(agg_pump.rated_power, expected_power)
        self.assertAlmostEqual(agg_pump.diameter, expected_diamter)

        mapping = agg_pump.get_replacement_mapping()
        graph.merge(
            mapping=agg_pump.get_replacement_mapping(),
            inner_connections=agg_pump.inner_connections,
        )
        self.assertCountEqual([agg_pump.ports[0], agg_pump.ports[1]],
                              [mapping[models[0].ports[0]],
                               mapping[models[-1].ports[1]]])

    def test_pump_setup2(self):
        """ Five parallel pumps."""
        graph, flags = self.helper.get_setup_pumps2()
        models = flags['normal']
        small = flags['small']
        pumps = [item for item in models if isinstance(item, hvac.Pump)]
        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump.find_matches(graph)

        self.assertEqual(len(matches), 1)
        agg_pump = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump(graph, matches[0], **meta[0])
        # TODO: before merge check units
        expected_power = sum([p.rated_power for p in pumps])
        expected_height = sum([p.rated_height for p in pumps]) / len(pumps)  # only for same size pumps
        expected_volume_flow = sum([p.rated_volume_flow for p in pumps])
        expected_diameter = sum([p.diameter**2 for p in pumps])**.5

        self.assertAlmostEqual(agg_pump.rated_volume_flow, expected_volume_flow)
        self.assertAlmostEqual(agg_pump.rated_height, expected_height)
        self.assertAlmostEqual(agg_pump.rated_power, expected_power)
        self.assertAlmostEqual(agg_pump.diameter, expected_diameter)

        graph.merge(
            mapping=agg_pump.get_replacement_mapping(),
            inner_connections=agg_pump.inner_connections,
        )
        remaining_pumps = [node for node in graph.element_graph.nodes if
                           node.__class__.__name__ == 'Pump']
        small_pumps = [item for item in small if item.__class__.__name__ ==
                       'Pump']
        unconnected_nodes = list(nx.isolates(graph))

        # check of small pump still in graph
        self.assertCountEqual(remaining_pumps, small_pumps)
        # check for unconnected nodes
        self.assertCountEqual(unconnected_nodes, [])

    def test_pump_setup4(self):
        """Four parallel pumps, one small with bypass."""
        graph, flags = self.helper.get_setup_pumps4()
        models = flags['normal']
        small = flags['small']
        pumps = [item for item in models if isinstance(item, hvac.Pump)]
        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump.find_matches(graph)

        self.assertEqual(len(matches), 1)
        agg_pump = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump(graph, matches[0], **meta[0])
        # TODO: before merge check units
        expected_power = sum([p.rated_power for p in pumps])
        expected_height = sum([p.rated_height for p in pumps]) / len(pumps)  # only for same size pumps
        expected_volume_flow = sum([p.rated_volume_flow for p in pumps])
        expected_diameter = sum([p.diameter**2 for p in pumps])**.5

        self.assertAlmostEqual(agg_pump.rated_volume_flow, expected_volume_flow)
        self.assertAlmostEqual(agg_pump.rated_height, expected_height)
        self.assertAlmostEqual(agg_pump.rated_power, expected_power)
        self.assertAlmostEqual(agg_pump.diameter, expected_diameter)

        graph.merge(
            mapping=agg_pump.get_replacement_mapping(),
            inner_connections=agg_pump.inner_connections,
        )
        remaining_pumps = [node for node in graph.element_graph.nodes if
                           node.__class__.__name__ == 'Pump']
        small_pumps = [item for item in small if item.__class__.__name__ ==
                       'Pump']
        unconnected_nodes = list(nx.isolates(graph))

        # check of small pump still in graph
        self.assertCountEqual(remaining_pumps, small_pumps)
        # check for unconnected nodes
        self.assertCountEqual(unconnected_nodes, [])

    def test_pump_setup5(self):
        """Five parallel pumps, one smaller, additional connections."""
        graph, flags = self.helper.get_setup_pumps5()

        models = flags['normal']
        small = flags['small']
        pumps = [item for item in models if isinstance(item, hvac.Pump)]
        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump.find_matches(graph)

        self.assertEqual(len(matches), 1)
        agg_pump = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump(graph, matches[0], **meta[0])
        # todo before merge check units
        expected_power = sum([p.rated_power for p in pumps])
        expected_height = sum([p.rated_height for p in pumps]) / len(pumps)  # only for same size pumps
        expected_volume_flow = sum([p.rated_volume_flow for p in pumps])
        expected_diamter = sum([p.diameter**2 for p in pumps])**.5
        pumps_in_aggr = [item for item in agg_pump.elements if
                         isinstance(item, hvac.Pump)]
        self.assertAlmostEqual(agg_pump.rated_volume_flow, expected_volume_flow)
        self.assertAlmostEqual(agg_pump.rated_height, expected_height)
        self.assertAlmostEqual(agg_pump.rated_power, expected_power)
        self.assertAlmostEqual(agg_pump.diameter, expected_diamter)
        self.assertCountEqual(pumps_in_aggr, pumps)

        graph.merge(
            mapping=agg_pump.get_replacement_mapping(),
            inner_connections=agg_pump.inner_connections,
        )

        remaining_pumps = [node for node in graph.element_graph.nodes if
                           node.__class__.__name__ == 'Pump']
        small_pumps = [item for item in small if item.__class__.__name__ ==
                       'Pump']
        unconnected_nodes = list(nx.isolates(graph))

        # check of small pump still in graph
        self.assertCountEqual(remaining_pumps, small_pumps)
        # check for unconnected nodes
        self.assertCountEqual(unconnected_nodes, [])

    def test_basics(self):
        graph, flags = self.helper.get_setup_pumps1()

        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump.find_matches(graph)
        self.assertEqual(len(matches), 1)

        agg = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump(graph, matches[0], **meta[0])
        self.assertTrue(self.helper.elements_in_agg(agg))

    def test_detection_pumps1(self):
        """test detection of ParallelPumps in setup pumps1"""
        graph, flags = self.helper.get_setup_pumps1()

        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump.find_matches(graph)

        self.assertEqual(
            len(matches), 1,
            "There are 1 cases for ParallelPumps but 'find_matches' returned %d"
            % len(matches)
        )

    def test_detection_pumps2(self):
        """test detection of ParallelPumps in setup pumps2"""
        graph, flags = self.helper.get_setup_pumps2()

        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump.find_matches(graph)

        self.assertEqual(
            len(matches), 1,
            "There are 1 cases for ParallelPumps but 'find_matches' returned %d" % len(matches)
        )

    def test_detection_pumps3(self):
        """test detection of ParallelPumps in setup pumps2"""
        graph, flags = self.helper.get_setup_pumps3()

        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump.find_matches(graph)

        self.assertEqual(
            len(matches), 1,
            "There are 1 cases for ParallelPumps but 'find_matches' returned %d" % len(matches)
        )

    def test_detection_pumps4(self):
        """test detection of ParallelPumps in setup pumps4"""
        graph, flags = self.helper.get_setup_pumps4()

        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump.find_matches(graph)

        self.assertEqual(
            len(matches), 1,
            "There are 1 cases for ParallelPumps but 'find_matches' returned %d" % len(matches)
        )

    def test_detection_system(self):
        """test detection of ParallelPumps in setup system"""
        graph, flags = self.helper.get_setup_system()

        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.ParallelPump.find_matches(graph)
        self.assertEqual(
            len(matches), 2,
            "There are 2 cases for ParallelPumps but 'find_matches' returned %d"
            % len(matches)
        )

        n_pumps1 = len([item for item in flags['pumps1']
                        if isinstance(item, hvac.Pump)])
        n_pumps2 = len([item for item in flags['normal']
                        if isinstance(item, hvac.Pump)])

        match_pumps = []
        for match in matches:
            match_pumps.append([ele for ele in match.elements
                                if isinstance(ele, hvac.Pump)])

        target_pumps = {n_pumps1, n_pumps2}
        actual_pumps = {len(mp) for mp in match_pumps}
        self.assertSetEqual(
            target_pumps, actual_pumps,
            "{} and {} pumps expected but the finder found {} and {} "
            "pumps.".format(*target_pumps, *actual_pumps))


if __name__ == '__main__':
    unittest.main()
