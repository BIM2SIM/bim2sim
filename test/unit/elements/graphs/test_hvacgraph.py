import unittest

import networkx as nx

from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.hvac_elements import HVACPort
from bim2sim.elements.graphs import hvac_graph
from test.unit.elements.helper import SetupHelperHVAC


class GraphHelper(SetupHelperHVAC):

    def get_system_elements(self):
        """ Simple generator system made of boiler, pump, expansion tank,
            distributor and pipes.
        """
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            boiler = self.element_generator(hvac.Boiler, rated_power=200)
            gen_vl_a = [
                self.element_generator(hvac.Pipe, length=100, diameter=40)
                for i in range(3)]
            h_pump = self.element_generator(
                hvac.Pump, rated_power=2.2, rated_height=12,
                rated_volume_flow=8)
            gen_vl_b = [
                self.element_generator(
                    hvac.Pipe, flags=['strand1'], length=100, diameter=40)
                for i in range(5)]
            distributor = self.element_generator(
                hvac.Distributor, flags=['distributor'])  # , volume=80
            gen_rl_a = [
                self.element_generator(hvac.Pipe, length=100, diameter=40)
                for i in range(4)]
            fitting = self.element_generator(
                hvac.PipeFitting, n_ports=3, diameter=40, length=60)
            gen_rl_b = [
                self.element_generator(hvac.Pipe, length=100, diameter=40)
                for i in range(4)]
            gen_rl_c = [
                self.element_generator(
                    hvac.Pipe, flags=['strand2'], length=(1 + i) * 40,
                    diameter=15)
                for i in range(3)
            ]
            tank = self.element_generator(hvac.Storage, n_ports=1)

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
    """ Generate 2 port elements and connect them in line."""
    elements = []

    # create elements
    for i in range(number):
        ele = hvac.HVACProduct()
        ele.name = prefix + str(i)
        ele.ports.append(hvac.HVACPort(ele))
        ele.ports.append(hvac.HVACPort(ele))
        ele.inner_connections.extend(ele.get_inner_connections())
        elements.append(ele)
        # connect
        if i > 0:
            elements[i - 1].ports[1].connect(elements[i].ports[0])
    return elements


def attach(element1, element2, use_existing=False):
    """ Connect elements.

        If use_existing is True free ports (if any) are used else new ports
        are created.
    """
    if use_existing:
        free_ports1 = [port for port in element1.ports if not port.connection]
        free_ports2 = [port for port in element2.ports if not port.connection]
    else:
        free_ports1 = []
        free_ports2 = []

    if free_ports1:
        port_e1 = free_ports1[0]
    else:
        port_e1 = HVACPort(element1)
        element1.ports.append(port_e1)

    if free_ports2:
        port_e2 = free_ports2[0]
    else:
        port_e2 = HVACPort(element2)
        element2.ports.append(port_e2)

    element1.inner_connections = element1.get_inner_connections()
    element2.inner_connections = element2.get_inner_connections()

    port_e1.connect(port_e2)


# @patch.object(element.BaseElement, '__repr__', lambda self: self.name)
class TestHVACGraph(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = GraphHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_create(self):
        """ Test instantiating and basic behaviour."""
        strait = generate_element_strait()
        single_loop = generate_element_strait()
        attach(single_loop[0], single_loop[-1])

        graph_strait = hvac_graph.HvacGraph(strait)
        self.assertSetEqual(set(strait), set(graph_strait.elements))
        self.assertEqual(len(graph_strait.get_connections()), len(strait) - 1)

        graph_loop = hvac_graph.HvacGraph(single_loop)
        self.assertSetEqual(set(single_loop), set(graph_loop.elements))
        self.assertEqual(len(graph_loop.get_connections()), len(single_loop))

    def test_merge(self):
        """ Test merging elements into simpler representation."""
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
        """ Test chain detection."""
        elements, flags = self.helper.get_system_elements()
        port_graph = hvac_graph.HvacGraph(elements)
        ele_graph = port_graph.element_graph

        wanted = [hvac.Pipe]
        chains = hvac_graph.HvacGraph.get_type_chains(ele_graph, wanted)
        self.assertEqual(5, len(chains), "Unexpected number of chains found!")

        wanted = [hvac.Pipe, hvac.Pump]
        chains2 = hvac_graph.HvacGraph.get_type_chains(ele_graph, wanted)
        self.assertEqual(4, len(chains2), "Unexpected number of chains found!")

    def test_cycles(self):
        """ Test cycle detection."""
        # generate single cycle
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
        # graph2.plot(ports=True)
        # graph2.plot(ports=False)
        cyc2 = graph2.get_cycles()
        self.assertEqual(len(cyc2), 2)
        cyc2_elements = {port.parent for port in cyc2[0] + cyc2[1]}
        ref_elements = set(core_cycle + attached1[:-1])
        self.assertSetEqual(cyc2_elements, ref_elements)

    def test_nodes(self):
        """ Element and port graph nodes."""
        elements, flags = self.helper.get_system_elements()
        all_elements = set(elements)
        all_ports = {port for ele in elements for port in ele.ports}

        port_graph = hvac_graph.HvacGraph(elements)
        self.assertSetEqual(set(port_graph.nodes), all_ports)
        self.assertSetEqual(set(port_graph.elements), all_elements)

        ele_graph = port_graph.element_graph
        self.assertSetEqual(set(ele_graph.nodes), all_elements)

    def test_subgraph_from_elements(self):
        """ Test creating a subgraph of the port_graph with given elements."""
        elements, flags = self.helper.get_system_elements()
        port_graph = hvac_graph.HvacGraph(elements)

        # test subgraph creation
        sub_graph = port_graph.subgraph_from_elements(flags['strand1'])
        self.assertEqual(set(sub_graph.elements), set(flags['strand1']))

        # test if AssertionError is raised if elements are not in port_graph
        classes_to_remove = {hvac.Pipe}
        new_port_graph = hvac_graph.HvacGraph.remove_classes_from(
            port_graph, classes_to_remove)
        with self.assertRaises(AssertionError):
            new_port_graph.subgraph_from_elements(flags['strand1'])

    def test_remove_classes(self):
        """ Test remove elements of given classes from port graph and
            element graph."""
        elements, flags = self.helper.get_system_elements()
        port_graph = hvac_graph.HvacGraph(elements)
        ele_graph = port_graph.element_graph

        classes_to_remove = {hvac.Boiler, hvac.Distributor}
        new_port_graph = hvac_graph.HvacGraph.remove_classes_from(
            port_graph, classes_to_remove)
        new_ele_graph = hvac_graph.HvacGraph.remove_classes_from(
            ele_graph, classes_to_remove
        )

        self.assertFalse(hvac.Boiler and hvac.Distributor
                         in {ele.__class__ for ele in new_port_graph.elements})
        self.assertFalse(hvac.Boiler and hvac.Distributor
                         in {node.__class__ for node in new_ele_graph.nodes})
