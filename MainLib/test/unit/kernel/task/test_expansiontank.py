import unittest

from test.unit.kernel.helper import SetupHelper
from bim2sim.kernel.elements import hvac
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.task.hvac import expansiontanks
from bim2sim import decision


class GeneratorHelper(SetupHelper):

    def get_setup_circuit_with_expansion_tank(self):
        """Simple circuit with one expansion tank"""
        flags = {}
        with self.flag_manager(flags):
            strand_main = [
                self.element_generator(hvac.Pipe, length=100, diameter=40)
                for i in range(5)]
            fitting = self.element_generator(hvac.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            strand_tank = [
                self.element_generator(hvac.Pipe, length=100, diameter=40)
                for i in range(2)]
            tank = self.element_generator(hvac.Storage, n_ports=1)

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
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = GeneratorHelper()

    def tearDown(self):
        self.helper.reset()

    def test_expansion_tank_circuit_decision(self):
        """Test performs search and remove of the expansion tanks by decision"""

        graph, flags = self.helper.get_setup_circuit_with_expansion_tank()
        pot_tanks = \
            expansiontanks.ExpansionTanks.identify_expansion_tanks(graph)
        self.assertEqual(
            1, len(pot_tanks),
            f"There is 1 expansion tank but ony {len(pot_tanks)} was identified."
        )
        job = expansiontanks.ExpansionTanks.decide_expansion_tanks(
                    graph, pot_tanks)
        try:
            while True:
                decisions = next(job)
                for dec in decisions:
                    dec.value = True
        except StopIteration as result:
            graph, n_removed = result.value
        self.assertEqual(n_removed, 1)

    def test_expansion_tank_circuit_forced(self):
        """Test performs search and remove of the expansion tanks with forced
         deletion
        """

        graph, flags = self.helper.get_setup_circuit_with_expansion_tank()
        pot_tanks = \
            expansiontanks.ExpansionTanks.identify_expansion_tanks(graph)
        self.assertEqual(
            1, len(pot_tanks),
            f"There is 1 expansion tank but ony {len(pot_tanks)} was identified."
        )
        job = expansiontanks.ExpansionTanks.decide_expansion_tanks(
            graph, pot_tanks, force=True)
        try:
            while True:
                dummy = next(job)
        except StopIteration as result:
            graph, n_removed = result.value

        self.assertEqual(n_removed, 1)
