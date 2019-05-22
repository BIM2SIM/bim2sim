import unittest
from unittest.mock import patch

import networkx as nx

from bim2sim.ifc2python import element
from bim2sim.ifc2python.hvac import hvac_graph


def generate_element_strait(n=5, suffix=""):
    elements = []
    with patch.object(element.Element, '_add_ports', return_value = None) as mock_add_ports:

        #create elements
        for i in range(n):
            ele = element.BaseElement()
            ele.ports.append(element.BasePort(ele))
            ele.ports.append(element.BasePort(ele))
            elements.append(ele)
            # connect
            if i > 0:
                elements[i-1].ports[0].connect(elements[i].ports[1])
    return elements

def attach(element1, element2, use_existing=False):
    """Connect elements
    
    If use_existing=True free ports (if any) are used. 
    Else new Prots are created"""
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

    if free_ports2:
        port_e2 = free_ports2[0]
    else:
        port_e2 = element.BasePort(element2)
        element2.ports.append(port_e2)

    port_e1.connect(port_e2)


class Test_HVACGraph(unittest.TestCase):

    def test_create(self):
        strait = generate_element_strait(suffix="strait")
        single_loop = generate_element_strait(suffix="loop")
        attach(single_loop[0], single_loop[-1])

        graph_strait = hvac_graph.HvacGraph(strait)
        self.assertSetEqual(set(strait), set(graph_strait.elements))
        self.assertEqual(len(graph_strait.get_connections()), len(strait)-1)

        graph_loop = hvac_graph.HvacGraph(single_loop)
        self.assertSetEqual(set(single_loop), set(graph_loop.elements))
        self.assertEqual(len(graph_loop.get_connections()), len(single_loop))

    def test_replace(self):
        strait = generate_element_strait(10)
        to_replace = strait[2:-3]
        replacement = generate_element_strait(1, "rep")[0]

        graph = hvac_graph.HvacGraph(strait)
        graph.replace(to_replace, replacement)

        for ele in graph.elements:
            self.assertNotIn(ele, to_replace)

        graph_reproduced = hvac_graph.HvacGraph(graph.elements)
        diff = nx.difference(graph.graph, graph_reproduced.graph)
        self.assertEqual(diff.number_of_edges(), 0)

if __name__ == '__main__':
    unittest.main()
