import unittest

from test.unit.kernel.helper import SetupHelper
from bim2sim.decision import Decision
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.task.hvac import dead_ends
from bim2sim import decision
from bim2sim.decision.console import ConsoleFrontEnd as FrontEnd


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


class TestOnlyDeadEnds(unittest.TestCase):
    """ Test with a small circuit with 10 dead ends and no open ports for
     consumers."""
    
    frontend = FrontEnd()
    helper = None
    _backup = None

    @classmethod
    def setUpClass(cls):
        cls._backup = decision.Decision.frontend
        decision.Decision.set_frontend(cls.frontend)
        cls.helper = DeadEndHelper()

    @classmethod
    def tearDownClass(cls):
        decision.Decision.set_frontend(cls._backup)

    def tearDown(self):
        decision.Decision.all.clear()
        decision.Decision.stored_decisions.clear()
        self.helper.reset()

    def test_dead_end_identification_decision(self):
        """Test performs search and remove of the dead ends by decision"""
        
        graph, flags = self.helper.get_simple_circuit()
        pot_dead_ends = dead_ends.DeadEnds.identify_deadends(graph)
        pot_dead_ends_compare = [
            flags['ps1'][0].ports[1],
            flags['ps3'][0].ports[1],
            flags['fitting_4port'][0].ports[3],
            flags['ps6'][0].ports[1],
        ]
        self.assertCountEqual(pot_dead_ends_compare, pot_dead_ends)
        with Decision.debug_answer(True):
            graph, n_removed = dead_ends.DeadEnds.decide_deadends(
                graph, pot_dead_ends, False)
        self.assertEqual(10, n_removed)

    def test_dead_end_identification_forced(self):
        """Test performs search and remove of the dead ends with forced deletion
        """

        graph, flags = self.helper.get_simple_circuit()
        pot_dead_ends = dead_ends.DeadEnds.identify_deadends(graph)
        pot_dead_ends_compare = [
            flags['ps1'][0].ports[1],
            flags['ps3'][0].ports[1],
            flags['fitting_4port'][0].ports[3],
            flags['ps6'][0].ports[1],
        ]
        self.assertCountEqual(pot_dead_ends_compare, pot_dead_ends)
        graph, n_removed = dead_ends.DeadEnds.decide_deadends(
                graph, pot_dead_ends, True)
        self.assertEqual(10, n_removed)
