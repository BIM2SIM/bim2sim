import unittest
from unittest.mock import patch

import networkx as nx

from bim2sim.kernel import element, elements
from bim2sim.kernel.hvac import hvac_graph

from test.unit.kernel.helper import SetupHelper


class GraphHelper(SetupHelper):

    def get_system_elements(self):
        """Simple generator system made of boiler, pump, expansion tank, distributor and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            boiler = self.element_generator(elements.Boiler, rated_power=200)
            gen_vl_a = [self.element_generator(elements.Pipe, length=100, diameter=40) for i in range(3)]
            h_pump = self.element_generator(elements.Pump, rated_power=2.2, rated_height=12, rated_volume_flow=8)
            gen_vl_b = [self.element_generator(elements.Pipe, flags=['strand1'], length=100, diameter=40) for i in
                        range(5)]
            distributor = self.element_generator(elements.Distributor, flags=['distributor'])  # , volume=80
            gen_rl_a = [self.element_generator(elements.Pipe, length=100, diameter=40) for i in range(4)]
            fitting = self.element_generator(elements.PipeFitting, n_ports=3, diameter=40, length=60)
            gen_rl_b = [self.element_generator(elements.Pipe, length=100, diameter=40) for i in range(4)]
            gen_rl_c = [
                self.element_generator(elements.Pipe, flags=['strand2'], length=(1 + i) * 40, diameter=15)
                for i in range(3)
            ]
            tank = self.element_generator(elements.Storage, n_ports=1)

        # connect
        gen_vl = [boiler, *gen_vl_a, h_pump, *gen_vl_b, distributor]
        self.connect_strait(gen_vl)

        self.connect_strait([distributor, *gen_rl_a, fitting])
        self.connect_strait([fitting, *gen_rl_b, boiler])
        self.connect_strait([*gen_rl_c, tank])
        fitting.ports[2].connect(gen_rl_c[0].ports[0])

        # full system
        gen_circuit = [
            boiler, *gen_vl_a, h_pump, *gen_vl_b, distributor,
            *gen_rl_a, fitting, *gen_rl_b, *gen_rl_c, tank
        ]

        return gen_circuit, flags


def generate_element_strait(number=5, prefix=""):
    """generate 2 port elements an connect them in line"""
    elements = []

    #create elements
    for i in range(number):
        ele = element.ProductBased()
        ele.name = prefix + str(i)
        ele.ports.append(element.Port(ele))
        ele.ports.append(element.Port(ele))
        elements.append(ele)
        # connect
        if i > 0:
            elements[i-1].ports[1].connect(elements[i].ports[0])
    return elements


def attach(element1, element2, use_existing=False):
    """Connect elements

    If use_existing=True free ports (if any) are used.
    Else new Ports are created"""
    if use_existing:
        free_ports1 = [port for port in element1.ports if not port.connection]
        free_ports2 = [port for port in element2.ports if not port.connection]
    else:
        free_ports1 = []
        free_ports2 = []

    if free_ports1:
        port_e1 = free_ports1[0]
    else:
        port_e1 = element.Port(element1)
        element1.ports.append(port_e1)

    if free_ports2:
        port_e2 = free_ports2[0]
    else:
        port_e2 = element.Port(element2)
        element2.ports.append(port_e2)

    port_e1.connect(port_e2)


# @patch.object(element.BaseElement, '__repr__', lambda self: self.name)
class Test_HVACGraph(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = GraphHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_create(self):
        """Instantiating and basic behaviour"""
        strait = generate_element_strait()
        single_loop = generate_element_strait()
        attach(single_loop[0], single_loop[-1])

        graph_strait = hvac_graph.HvacGraph(strait)
        self.assertSetEqual(set(strait), set(graph_strait.elements))
        self.assertEqual(len(graph_strait.get_connections()), len(strait)-1)

        graph_loop = hvac_graph.HvacGraph(single_loop)
        self.assertSetEqual(set(single_loop), set(graph_loop.elements))
        self.assertEqual(len(graph_loop.get_connections()), len(single_loop))

    def test_merge(self):
        """merging elements into simpler representation"""
        strait = generate_element_strait(10, "strait")
        to_replace = strait[2:-3]
        replacement = generate_element_strait(1, "replacement")[0]

        graph = hvac_graph.HvacGraph(strait)
        mapping = {port: None for ele in to_replace for port in ele.ports}
        mapping[to_replace[0].ports[0]] = replacement.ports[0]
        mapping[to_replace[-1].ports[1]] = replacement.ports[1]

        graph.merge(mapping, [(replacement.ports[0], replacement.ports[1])])

        for ele in graph.elements:
            self.assertNotIn(ele, to_replace)

        path_port = nx.shortest_path(
            graph, strait[0].ports[0], strait[-1].ports[1])
        self.assertIn(replacement.ports[0], path_port)
        self.assertIn(replacement.ports[-1], path_port)

        path_element = nx.shortest_path(
            graph.element_graph, strait[0], strait[-1])
        self.assertIn(replacement, path_element)

    def test_type_chain(self):
        """test chain detection"""
        eles, flags = self.helper.get_system_elements()
        port_graph = hvac_graph.HvacGraph(eles)
        ele_graph = port_graph.element_graph

        wanted = ['IfcPipeSegment']
        chains = hvac_graph.HvacGraph.get_type_chains(ele_graph, wanted)
        self.assertEqual(5, len(chains), "Unexpected number of chains found!")

        wanted = ['IfcPipeSegment', 'IfcPump']
        chains2 = hvac_graph.HvacGraph.get_type_chains(ele_graph, wanted)
        self.assertEqual(4, len(chains2), "Unexpected number of chains found!")

    def test_cycles(self):
        """cycle detection"""
        # generate singel cycle
        core_cycle = generate_element_strait(10, 'core')
        attach(core_cycle[0], core_cycle[-1], True)

        # test single cycle
        graph1 = hvac_graph.HvacGraph(core_cycle)
        cyc1 = graph1.get_cycles()
        self.assertEqual(len(cyc1), 1)
        self.assertSetEqual(
            set(cyc1[0]),
            {port for ele in core_cycle for port in ele.ports})

        # generate second cycle and attach it with loose end
        attached1 = generate_element_strait(prefix='attached')
        attach(core_cycle[0], attached1[0])
        attach(core_cycle[5], attached1[-2])

        # test double cycle
        graph2 = hvac_graph.HvacGraph(core_cycle + attached1)
        #graph2.plot(ports=True)
        #graph2.plot(ports=False)
        cyc2 = graph2.get_cycles()
        self.assertEqual(len(cyc2), 2)
        cyc2_elements = {port.parent for port in cyc2[0] + cyc2[1]}
        ref_elements = set(core_cycle + attached1[:-1])
        self.assertSetEqual(cyc2_elements, ref_elements)

    def test_nodes(self):
        """element and port graph nodes"""
        eles, flags = self.helper.get_system_elements()
        all_eles = set(eles)
        all_ports = {port for ele in eles for port in ele.ports}

        port_graph = hvac_graph.HvacGraph(eles)
        self.assertSetEqual(set(port_graph.nodes), all_ports)
        self.assertSetEqual(set(port_graph.elements), all_eles)

        ele_graph = port_graph.element_graph
        self.assertSetEqual(set(ele_graph.nodes), all_eles)



