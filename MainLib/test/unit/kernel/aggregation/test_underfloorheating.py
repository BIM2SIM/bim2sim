import unittest
import math

from bim2sim.kernel.elements import hvac
from bim2sim.kernel import aggregation
from bim2sim.kernel.elements.hvac import HVACPort
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.kernel.units import ureg

from test.unit.kernel.helper import SetupHelper


class UFHHelper(SetupHelper):

    def get_setup_ufh1(self):
        """Simple underfloorheating"""
        flags = {}

        x_dimension = 5 * ureg.meter
        y_dimension = 4 * ureg.meter
        spacing = 0.19 * ureg.meter
        with self.flag_manager(flags):
            # elements generator
            ny_pipes = math.floor(y_dimension / spacing)
            y_pipes = [self.element_generator(
                hvac.Pipe, length=y_dimension/ny_pipes, diameter=15) for
                i in range(ny_pipes)]
            x_pipes = [self.element_generator(
                hvac.Pipe, length=x_dimension, diameter=15) for
                i in range(ny_pipes + 1)]
        # connect
        ufh_strand = self.connect_ufh(x_pipes, y_pipes, x_dimension, spacing)

        # full system
        gen_circuit = [
            *ufh_strand
        ]
        flags['connect'] = [ufh_strand[0], ufh_strand[-1]]
        graph = HvacGraph(gen_circuit)
        graph.plot(r'c:\temp')
        return graph, flags


class TestUnderfloorHeating(unittest.TestCase):

    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = UFHHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_simple_ufh(self):
        graph, flags = self.helper.get_setup_ufh1()
        ele = graph.elements

        matches, meta = aggregation.UnderfloorHeating.find_matches(graph)
        self.assertEqual(1, len(matches))
        agg = aggregation.UnderfloorHeating(matches[0], **meta[0])

        exp_length = sum([e.length for e in ele])
        self.assertAlmostEqual(exp_length, agg.length)

        self.assertAlmostEqual(19.95 * ureg.meter ** 2, agg.heating_area)
        self.assertAlmostEqual(15 * ureg.millimeter, agg.diameter)
        self.assertAlmostEqual(.19949999 * ureg.meter, agg.y_spacing)
        self.assertAlmostEqual(.23809523 * ureg.meter, agg.x_spacing)

        pass
