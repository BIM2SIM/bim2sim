import unittest
from unittest.mock import patch

import networkx as nx

from bim2sim.kernel import element
from bim2sim.kernel.hvac import hvac_graph


def generate_element_strait(number=5, prefix=""):
    """generate 2 port elements an connect them in line"""
    elements = []

    #create elements
    for i in range(number):
        ele = element.BaseElement()
        ele.name = prefix + str(i)
        ele.ports.append(element.BasePort(ele))
        ele.ports.append(element.BasePort(ele))
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
        port_e1 = element.BasePort(element1)
        element1.ports.append(port_e1)

    if free_ports2:
        port_e2 = free_ports2[0]
    else:
        port_e2 = element.BasePort(element2)
        element2.ports.append(port_e2)

    port_e1.connect(port_e2)


@patch.object(element.BaseElement, '__repr__', lambda self: self.name)
class Test_HVACGraph(unittest.TestCase):

    def test_create(self):
        """Instantiatin and basic behaviour"""
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
        mapping = {port:None for ele in to_replace for port in ele.ports}
        mapping[to_replace[0].ports[0]] = replacement.ports[0]
        mapping[to_replace[-1].ports[1]] = replacement.ports[1]

        graph.merge(mapping, [(replacement.ports[0], replacement.ports[1])])

        for ele in graph.elements:
            self.assertNotIn(ele, to_replace)

        path_port = nx.shortest_path(
            graph.graph, strait[0].ports[0], strait[-1].ports[1])
        self.assertIn(replacement.ports[0], path_port)
        self.assertIn(replacement.ports[-1], path_port)

        path_element = nx.shortest_path(
            graph.element_graph, strait[0], strait[-1])
        self.assertIn(replacement, path_element)

    @unittest.skip("Not implemented")
    def test_type_chain(self):
        """test chain detection"""
        pass

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


if __name__ == '__main__':
    unittest.main()
