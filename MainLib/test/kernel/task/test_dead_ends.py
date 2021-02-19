import unittest

from test.kernel.helper import SetupHelper
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.task import dead_ends


class DeadEndHelper(SetupHelper):
    def get_simple_circuit(self):
        """get a simple circuit with a 4 port pipefitting with open ports,
         some connected pipes and dead ends"""
        flags = {}
        with self.flag_manager(flags):
            fitting_4port = self.element_generator(elements.PipeFitting, flags=['fitting_4port'], n_ports=4)
            fitting_3port_1 = self.element_generator(elements.PipeFitting, flags=['fitting_3port_1'], n_ports=3)
            fitting_3port_2 = self.element_generator(elements.PipeFitting, flags=['fitting_3port_2'], n_ports=3)
            pipestrand1 = [self.element_generator(elements.Pipe, length=100, diameter=30, flags=['ps1']) for i in range(1)]
            pipestrand2 = [self.element_generator(elements.Pipe, length=100, diameter=30, flags=['ps2']) for i in range(1)]
            pipestrand3 = [self.element_generator(elements.Pipe, length=100, diameter=30, flags=['ps3']) for i in range(1)]
            pipestrand4 = [self.element_generator(elements.Pipe, length=100, diameter=30, flags=['ps4']) for i in range(1)]
            pipestrand5 = [self.element_generator(elements.Pipe, length=100, diameter=30, flags=['ps5']) for i in range(1)]
            pipestrand6 = [self.element_generator(elements.Pipe, length=100, diameter=30, flags=['ps6']) for i in range(1)]

            self.connect_strait([*pipestrand1])
            self.connect_strait([*pipestrand2])
            self.connect_strait([*pipestrand3])
            self.connect_strait([*pipestrand4])
            self.connect_strait([*pipestrand5])
            self.connect_strait([*pipestrand6])
            fitting_4port.ports[0].connect(pipestrand1[0].ports[0])
            fitting_4port.ports[1].connect(pipestrand2[0].ports[0])
            fitting_4port.ports[2].connect(pipestrand3[0].ports[0])
            pipestrand2[-1].ports[-1].connect(fitting_3port_1.ports[0])
            fitting_3port_1.ports[1].connect(pipestrand4[0].ports[0])
            fitting_3port_1.ports[2].connect(pipestrand5[0].ports[0])
            fitting_3port_2.ports[0].connect(pipestrand4[-1].ports[-1])
            fitting_3port_2.ports[1].connect(pipestrand5[-1].ports[-1])
            fitting_3port_2.ports[2].connect(pipestrand6[0].ports[0])

            circuit = [*pipestrand1, *pipestrand2, *pipestrand3, *pipestrand4, *pipestrand5, *pipestrand6,
                       fitting_4port, fitting_3port_1, fitting_3port_2]

            graph = HvacGraph(circuit)
            return graph, flags


class TestDeadEndIdentification(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = DeadEndHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_dead_end_identification(self):
        graph, flags = self.helper.get_simple_circuit()
        dead_ends_fc = dead_ends.deadEnds.identify_deadends(graph)
        dead_ends_fc_compare = [
            flags['ps1'][0].ports[1],
            flags['ps3'][0].ports[1],
            flags['fitting_4port'][0].ports[3],
            flags['ps6'][0].ports[1],
        ]
        print("Found %s possible dead ends in network." % len(dead_ends_fc))
        self.assertCountEqual(dead_ends_fc_compare, dead_ends_fc)
        graph, n_removed = dead_ends.deadEnds.decide_deadends(graph, dead_ends_fc)
        print("Removed %s ports due to found dead ends." % n_removed)





