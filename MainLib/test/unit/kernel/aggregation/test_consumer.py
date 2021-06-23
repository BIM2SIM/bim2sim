import unittest

from bim2sim.kernel.elements import hvac
from bim2sim.kernel import aggregation
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph

from bim2sim.kernel.units import ureg

from test.unit.kernel.helper import SetupHelper

import networkx as nx


class ConsumerHelper(SetupHelper):

    def get_setup_consumer1(self):
        """get consumer circuit made of 2 parallel pumps , space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                hvac.PipeFitting, flags=['con1'], n_ports=3, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    hvac.Pipe, flags=['con1'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['con1'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['con1'], length=40, diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    hvac.Pipe, flags=['con1'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['con1'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['con1'], length=40, diameter=20),
            ]
            fitting2 = self.element_generator(
                hvac.PipeFitting, flags=['con2'], n_ports=3, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            consumer = self.element_generator(
                hvac.SpaceHeater, flags=['spaceheater'])
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

    def get_setup_consumer2(self):
        """get consumer circuit made of 2 parallel pumps , underfloorheating and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                hvac.PipeFitting, flags=['con2'], n_ports=3, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    hvac.Pipe, flags=['con2'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['con2'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['con2'], length=40, diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    hvac.Pipe, flags=['con2'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['con2'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['con2'], length=40, diameter=20),
            ]
            fitting2 = self.element_generator(
                hvac.PipeFitting, flags=['con2'], n_ports=3, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            underfloor_pipes = [self.element_generator(
                hvac.Pipe, length=1000, diameter=10) for i in range(3)]
            con_rl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(6)]

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
        consumer = aggregation.UnderfloorHeating(subgraph.element_graph)
        flags['underfloor'] = [consumer]

        graph.merge(
            mapping=consumer.get_replacement_mapping(),
            inner_connections=consumer.inner_connections
        )
        # #ToDO: Workaround.... Hvac Graph.elements haben keine Portverknüpfungen ... vielleicht das problem
        # for port_a, port_b in consumer.get_replacement_mapping().items():
        #     if port_a and port_b:
        #         port_a.connect(port_b)

        return graph, flags

    def get_setup_consumer3(self):
        """get consumer circuit made of 2 parallel pumps , 2x space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            fitting1 = self.element_generator(
                hvac.PipeFitting, flags=['con3'], n_ports=3, diameter=30, length=60)
            p_pump1_p = [
                self.element_generator(
                    hvac.Pipe, flags=['con3'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['con3'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['con3'], length=40, diameter=20),
            ]
            p_pump2_p = [
                self.element_generator(
                    hvac.Pipe, flags=['con3'], length=40, diameter=20),
                self.element_generator(
                    hvac.Pump, flags=['con3'], rated_power=1, rated_height=8,
                    rated_volume_flow=6, diameter=20),
                self.element_generator(
                    hvac.Pipe, flags=['con3'], length=40, diameter=20),
            ]
            fitting2 = self.element_generator(
                hvac.PipeFitting, flags=['con3'], n_ports=3, diameter=30, length=60)
            con_vl_b = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(3)]
            consumer1 = self.element_generator(
                hvac.SpaceHeater, flags=['spaceheater'])
            con_mid = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(6)]
            consumer2 = self.element_generator(
                hvac.SpaceHeater, flags=['spaceheater'])
            con_rl_a = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(6)]

        # connect
        self.connect_strait([*con_vl_a, fitting1])
        self.connect_strait([fitting1, *p_pump1_p, fitting2])
        self.connect_strait(p_pump2_p)
        fitting1.ports[2].connect(p_pump2_p[0].ports[0])
        p_pump2_p[-1].ports[1].connect(fitting2.ports[2])
        self.connect_strait([fitting2, *con_vl_b, consumer1, *con_mid, consumer2, *con_rl_a])

        # full system
        gen_circuit = [
            *con_vl_a, fitting1, *p_pump1_p, *p_pump2_p, fitting2,
            *con_vl_b, consumer1, *con_mid, consumer2, *con_rl_a
        ]

        flags['connect'] = [con_vl_a[0], con_rl_a[-1]]

        graph = HvacGraph(gen_circuit)
        return graph, flags

    def get_setup_system(self):
        """Simple generator system made of boiler, pump, expansion tank, distributor, consumer1(1xSpaceheater),
        consumer2 (1xUnderfloorheating) and pipes"""
        graph1, flags1 = super().get_setup_simple_boiler()
        graph2, flags2 = self.get_setup_consumer1()
        graph3, flags3 = self.get_setup_consumer2()

        distributor = flags1['distributor'][0]
        distributor_ports = self.fake_add_ports(distributor, 4)

        graph = nx.compose(graph3, nx.compose(graph2, graph1))

        vl_p2, rl_p2 = flags3.pop('connect')
        graph.add_edge(rl_p2.ports[1], distributor_ports[3])
        graph.add_edge(distributor_ports[2], vl_p2.ports[0])

        vl_p1, rl_p1 = flags2.pop('connect')
        graph.add_edge(rl_p1.ports[1], distributor_ports[1])
        graph.add_edge(distributor_ports[0], vl_p1.ports[0])

        flags = {**flags1, **flags2, **flags3}
        return graph, flags

    def get_setup_system2(self):
        """Simple generator system made of boiler, pump, expansion tank, distributor consumer3(2xSpaceheater)
        and pipes"""
        graph1, flags1 = super().get_setup_simple_boiler()
        graph2, flags2 = self.get_setup_consumer3()

        distributor = flags1['distributor'][0]
        distributor_ports = self.fake_add_ports(distributor, 2)

        graph = nx.compose(graph2, graph1)

        vl_p1, rl_p1 = flags2.pop('connect')
        graph.add_edge(rl_p1.ports[1], distributor_ports[1])
        graph.add_edge(distributor_ports[0], vl_p1.ports[0])

        flags = {**flags1, **flags2}
        return graph, flags


class TestConsumerAggregation(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = ConsumerHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_detection_system(self):
        """test detection of Consumer Cycle in setup system"""
        graph, flags = self.helper.get_setup_system()

        # graph.plot(r'c:\temp')

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

        # graph.plot(r'c:\temp')

        matches, metas = aggregation.Consumer.find_matches(graph)

        for match, meta in zip(matches, metas):
            consumer = aggregation.Consumer(match, **meta)
            if hvac.SpaceHeater in {type(ele) for ele in consumer.elements}:
                # we only want consumer with SpaceHeater
                break

        graph.merge(
            mapping=consumer.get_replacement_mapping(),
            inner_connections=consumer.inner_connections
        )
        # graph.plot(r'c:\temp')

        self.assertAlmostEqual(consumer.rated_volume_flow, 12 * ureg.meter ** 3 / ureg.hour)
        self.assert_(consumer.has_pump)
        #self.assertAlmostEqual(consumer.temperaure_inlet, 1000) Not Implemented
        #self.assertAlmostEqual(consumer.temperature_outlet, 1000) Not Implemented
        #self.assertAlmostEqual(consumer.volume, 1000) Not Implemented
        #self.assertAlmostEqual(consumer.height, 1000) Not Implemented
        self.assertIn('SpaceHeater', consumer.description)  # list of all aggregated consumers description

    def test_aggregation_consumer2(self):
        """test aggregation of consumercycle no 2"""
        graph, flags = self.helper.get_setup_system()

        matches, metas = aggregation.Consumer.find_matches(graph)

        consumer2 = None

        for e, match in enumerate(matches):
            for ele in flags['con2']:
                if ele in match:
                    consumer2 = aggregation.Consumer(matches[e], **metas[e])
                    break
            if consumer2:
                break
        else:
            self.assertTrue(False, 'Kein Consumerkreis idendifiziert!')

        graph.merge(
            mapping=consumer2.get_replacement_mapping(),
            inner_connections=consumer2.inner_connections
        )

        self.assertAlmostEqual(consumer2.rated_volume_flow, 12 * ureg.meter ** 3 / ureg.hour)
        self.assertTrue(consumer2.has_pump)
        #self.assertAlmostEqual(consumer.temperaure_inlet, 1000) Not Implemented
        #self.assertAlmostEqual(consumer.temperature_outlet, 1000) Not Implemented
        #self.assertAlmostEqual(consumer.volume, 1000) Not Implemented
        #self.assertAlmostEqual(consumer.height, 1000) Not Implemented
        self.assertIn('UnderfloorHeating', consumer2.description)  # list of all aggregated consumers description

    def test_aggregation_consumer3(self):
        """test aggregation of consumercycle no 2"""
        graph, flags = self.helper.get_setup_system2()

        #graph.plot(r'c:\temp')

        matches, metas = aggregation.Consumer.find_matches(graph)

        idx = 0
        # meta = {'outer_connections': flags['connect']}

        consumer = aggregation.Consumer(matches[idx], **metas[idx])

        graph.merge(
            mapping=consumer.get_replacement_mapping(),
            inner_connections=consumer.inner_connections
        )

        #graph.plot(r'c:\temp')

        self.assertAlmostEqual(consumer.rated_volume_flow, 12 * ureg.meter ** 3 / ureg.hour)
        self.assert_(consumer.has_pump)
        #self.assertAlmostEqual(consumer.temperaure_inlet, 1000) Not Implemented
        #self.assertAlmostEqual(consumer.temperature_outlet, 1000) Not Implemented
        #self.assertAlmostEqual(consumer.volume, 1000) Not Implemented
        #self.assertAlmostEqual(consumer.height, 1000) Not Implemented
        self.assertIn('2 x SpaceHeater', consumer.description)  # list of all aggregated consumers description


if __name__ == '__main__':
    unittest.main()
