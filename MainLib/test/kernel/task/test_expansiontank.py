import unittest

from test.kernel.helper import SetupHelper
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.task.hvac import expansiontanks
from bim2sim import decision
from bim2sim.decision.console import ConsoleFrontEnd as FrontEnd


class GeneratorHelper(SetupHelper):

    def get_setup_circuit_with_expansion_tank(self):
        """Simple circuit with one expansion tank"""
        flags = {}
        with self.flag_manager(flags):
            strand_main = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(5)]
            fitting = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            strand_tank = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            tank = self.element_generator(elements.Storage, n_ports=1)

        self.connect_strait([*strand_main])
        self.connect_strait([*strand_tank])
        strand_main[0].ports[0].connect(fitting.ports[-1])
        fitting.ports[1].connect(strand_tank[0].ports[0])
        strand_tank[-1].ports[-1].connect(tank.ports[0])
        fitting.ports[0].connect(strand_main[-1].ports[-1])

        # full system
        circuit = [
            *strand_main, fitting, *strand_tank, tank]

        return HvacGraph(circuit), flags


class TestExpansionTank(unittest.TestCase):
    frontend = FrontEnd()
    helper = None
    _backup = None

    @classmethod
    def setUpClass(cls):
        cls._backup = decision.Decision.frontend
        decision.Decision.set_frontend(cls.frontend)
        cls.helper = GeneratorHelper()

    @classmethod
    def tearDownClass(cls):
        decision.Decision.set_frontend(cls._backup)

    def tearDown(self):
        decision.Decision.all.clear()
        decision.Decision.stored_decisions.clear()
        self.helper.reset()

    def test_expansion_tank_circuit_forced(self):
        graph, flags = self.helper.get_setup_circuit_with_expansion_tank()
        pot_tanks = \
            expansiontanks.ExpansionTanks.identify_expansion_tanks(graph)
        self.assertEqual(
            1, len(pot_tanks),
            f"There is 1 expansion tank but ony {len(pot_tanks)} was identified."
        )
        graph, n_removed = expansiontanks.ExpansionTanks.delete_expansion_tanks(
                graph, pot_tanks, force=True)

        self.assertEqual(n_removed, 1)

    def test_expansion_tank_circuit_decision(self):
        graph, flags = self.helper.get_setup_circuit_with_expansion_tank()
        pot_tanks = \
            expansiontanks.ExpansionTanks.identify_expansion_tanks(graph)
        self.assertEqual(
            1, len(pot_tanks),
            f"There is 1 expansion tank but ony {len(pot_tanks)} was identified."
        )
        with decision.Decision.debug_answer(True):
            graph, n_removed = \
                expansiontanks.ExpansionTanks.delete_expansion_tanks(
                    graph, pot_tanks, force=False)
        self.assertEqual(n_removed, 1)
