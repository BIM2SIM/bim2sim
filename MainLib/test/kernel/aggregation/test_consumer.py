import unittest

from bim2sim.kernel import aggregation
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph

from bim2sim.kernel.units import ureg

from test.kernel.helper import SetupHelper

import networkx as nx


class ConsumerHelper(SetupHelper):

    def get_setup_consumer1(self):
        """get consumer circuit made of 6 parallel pumps (one small), space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                elements.PipeFitting, flags=['con1'], n_ports=3, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    elements.Pipe, flags=['con1'], length=40, diameter=20),
                self.element_generator(
                    elements.Pump, flags=['con1'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    elements.Pipe, flags=['con1'], length=40, diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    elements.Pipe, flags=['con1'], length=40, diameter=20),
                self.element_generator(
                    elements.Pump, flags=['con1'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    elements.Pipe, flags=['con1'], length=40, diameter=20),
            ]
            fitting2 = self.element_generator(
                elements.PipeFitting, flags=['con1'], n_ports=3, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(3)]
            consumer = self.element_generator(
                elements.SpaceHeater, flags=['spaceheater'])
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
        #graph.plot(r'c:\temp')
        return graph, flags

    def get_setup_consumer2(self):
        """get consumer circuit made of 6 parallel pumps (one small), space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                elements.PipeFitting, flags=['con2'], n_ports=3, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    elements.Pipe, flags=['con2'], length=40, diameter=20),
                self.element_generator(
                    elements.Pump, flags=['con2'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    elements.Pipe, flags=['con2'], length=40, diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    elements.Pipe, flags=['con2'], length=40, diameter=20),
                self.element_generator(
                    elements.Pump, flags=['con2'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    elements.Pipe, flags=['con1'], length=40, diameter=20),
            ]
            fitting2 = self.element_generator(
                elements.PipeFitting, flags=['con1'], n_ports=3, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(3)]
            underfloor_pipes = [self.element_generator(
                elements.Pipe, length=1000, diameter=10) for i in range(3)]
            con_rl_a = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(6)]

        # connect
        self.connect_strait([*con_vl_a, fitting1])
        self.connect_strait([fitting1, *p_pump1_p, fitting2])
        self.connect_strait(p_pump2_p)
        fitting1.ports[2].connect(p_pump2_p[0].ports[0])
        p_pump2_p[-1].ports[1].connect(fitting2.ports[2])
        self.connect_strait([fitting2, *con_vl_b, *underfloor_pipes, *con_rl_a])

        # full system
        gen_circuit = [
            *con_vl_a, fitting1, *p_pump1_p, *p_pump2_p, fitting2,
            *con_vl_b, *underfloor_pipes, *con_rl_a
        ]

        flags['connect'] = [con_vl_a[0], con_rl_a[-1]]

        graph = HvacGraph(gen_circuit)

        uf_ports = (port for pipe in underfloor_pipes for port in pipe.ports)
        subgraph = graph.subgraph(uf_ports)
        consumer = aggregation.UnderfloorHeating('Underfloor1', subgraph.element_graph)
        flags['underfloor'] = [consumer]

        graph.merge(
            mapping=consumer.get_replacement_mapping(),
            inner_connections=consumer.get_inner_connections()
        )
        # #ToDO: Workaround.... Hvac Graph.elements haben keine Portverknüpfungen ... vielleicht das problem
        # for port_a, port_b in consumer.get_replacement_mapping().items():
        #     if port_a and port_b:
        #         port_a.connect(port_b)

        return graph, flags

    def get_setup_system(self):
        """Simple generator system made of boiler, pump, expansion tank, distributor and pipes"""
        graph1, flags1 = super().get_setup_simple_boiler()
        graph2, flags2 = self.get_setup_consumer1()
        graph3, flags3 = self.get_setup_consumer2()

        distributor = flags1['distributor'][0]
        distributor_ports = self.fake_add_ports(distributor, 4)

        # vl_p1, rl_p1 = flags2.pop('connect')
        # distributor_ports[0].connect(vl_p1.ports[0])
        # rl_p1.ports[1].connect(distributor_ports[1])
        #
        # vl_p2, rl_p2 = flags3.pop('connect')
        # distributor_ports[2].connect(vl_p2.ports[0])
        # rl_p2.ports[1].connect(distributor_ports[3])

        #ele = graph1.elements + graph2.elements + graph3.elements
        #graph = HvacGraph(ele)

        graph = nx.compose(graph3, nx.compose(graph2, graph1))

        vl_p2, rl_p2 = flags3.pop('connect')
        graph.add_edge(rl_p2.ports[1], distributor_ports[3])
        graph.add_edge(distributor_ports[2], vl_p2.ports[0])

        vl_p1, rl_p1 = flags2.pop('connect')
        graph.add_edge(rl_p1.ports[1], distributor_ports[1])
        graph.add_edge(distributor_ports[0], vl_p1.ports[0])

        # graph.plot(r'c:\temp')
        flags = {**flags1, **flags2, **flags3}
        return graph, flags


class TestConsumerAggregation(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = ConsumerHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    @unittest.skip("Not Implemented")
    def test_pump_setup1(self):
        """Two parallel pumps"""

        graph, flags = self.helper.get_setup_consumer1()
        models = flags['pumps1']
        pumps = [item for item in models if isinstance(item, elements.Pump)]

        matches, meta = aggregation.ParallelPump.find_matches(graph)
        self.assertEqual(len(matches), 1)
        agg_pump = aggregation.ParallelPump("Test", matches[0], **meta[0])

        expected_power = sum([p.rated_power for p in pumps])
        expected_height = sum([p.rated_height for p in pumps]) / len(pumps)  # only for same size pumps
        expected_volume_flow = sum([p.rated_volume_flow for p in pumps])

        self.assertAlmostEqual(agg_pump.rated_volume_flow, expected_volume_flow)
        self.assertAlmostEqual(agg_pump.rated_height, expected_height)
        self.assertAlmostEqual(agg_pump.rated_power, expected_power)

        #self.assertAlmostEqual(agg_pump.diameter, 20)

        mapping = agg_pump.get_replacement_mapping()

        self.assertIs(agg_pump.ports[0], mapping[models[0].ports[0]])
        self.assertIs(agg_pump.ports[1], mapping[models[-1].ports[1]])

    @unittest.skip("Not Implemented")
    def test_pump_setup2(self):
        """Five parallel pumps"""
        graph, flags = self.helper.get_setup_consumer2()
        models = flags['normal']
        pumps = [item for item in models if isinstance(item, elements.Pump)]

        matches, meta = aggregation.ParallelPump.find_matches(graph)
        self.assertEqual(len(matches), 1)
        agg_pump = aggregation.ParallelPump("Test", matches[0], **meta[0])

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

    @unittest.skip("Not Implemented")
    def test_basics(self):
        graph, flags = self.helper.get_setup_consumer1()

        matches, meta = aggregation.ParallelPump.find_matches(graph)
        self.assertEqual(len(matches), 1)

        agg = aggregation.ParallelPump("Test basics", matches[0], **meta[0])

        self.assertTrue(self.helper.elements_in_agg(agg))


    @unittest.skip("Not Implemented")
    def test_detection_pumps1(self):
        """test detection of ParallelPumps in setup pumps1"""
        graph, flags = self.helper.get_setup_consumer1()

        matches, meta = aggregation.ParallelPump.find_matches(graph)

        self.assertEqual(
            len(matches), 1,
            "There are 1 cases for ParallelPumps but 'find_matches' returned %d" % len(matches)
        )

    def test_detection_system(self):
        """test detection of Consumer Cycle in setup system"""
        graph, flags = self.helper.get_setup_system()

        graph.plot(r'c:\temp')

        matches, meta = aggregation.Consumer.find_matches(graph)

        self.assertEqual(
            len(matches), 2,
            "There are 2 cases for Consumer Cycles but 'find_matches' returned %d" % len(matches)
        )

        consumer = [item for item in flags['spaceheater']+flags['underfloor']]
        all = sum((list(match.nodes) for match in matches), [])
        for item in consumer:
            self.assertIn(item, all)

    def test_aggregation_consumer1(self):
        """test aggregation of consumercycle no 1"""
        graph, flags = self.helper.get_setup_system()

        graph.plot(r'c:\temp')

        matches, metas = aggregation.Consumer.find_matches(graph)

        idx = 0
        # meta = {'outer_connections': flags['connect']}

        consumer1 = aggregation.Consumer("Test basics", matches[idx], **metas[idx])

        graph.merge(
            mapping=consumer1.get_replacement_mapping(),
            inner_connections=consumer1.get_inner_connections()
        )

        #graph.plot(r'c:\temp')

        self.assertAlmostEqual(consumer1.rated_volume_flow, 12 * ureg.meter ** 3 / ureg.hour)
        #self.assertAlmostEqual(consumer.temperaure_inlet, 1000)
        #self.assertAlmostEqual(consumer.temperature_outlet, 1000)
        #self.assertAlmostEqual(consumer.volume, 1000)
        #self.assertAlmostEqual(consumer.height, 1000)
        self.assertIn('SpaceHeater', consumer1.description)  # list of all aggregated consumers description

    def test_aggregation_consumer2(self):
        """test aggregation of consumercycle no 2"""
        graph, flags = self.helper.get_setup_system()

        #graph.plot(r'c:\temp')

        matches, metas = aggregation.Consumer.find_matches(graph)

        idx = 1
        # meta = {'outer_connections': flags['connect']}

        consumer2 = aggregation.Consumer("Test basics", matches[idx], **metas[idx])

        graph.merge(
            mapping=consumer2.get_replacement_mapping(),
            inner_connections=consumer2.get_inner_connections()
        )

        #graph.plot(r'c:\temp')

        self.assertAlmostEqual(consumer2.rated_volume_flow, 12 * ureg.meter ** 3 / ureg.hour)
        #self.assertAlmostEqual(consumer.temperaure_inlet, 1000)
        #self.assertAlmostEqual(consumer.temperature_outlet, 1000)
        #self.assertAlmostEqual(consumer.volume, 1000)
        #self.assertAlmostEqual(consumer.height, 1000)
        self.assertIn('Underfloorheating', consumer2.description)  # list of all aggregated consumers description



if __name__ == '__main__':
    unittest.main()
