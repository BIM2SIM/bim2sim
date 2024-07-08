import math
import unittest

import numpy as np

import bim2sim.elements.aggregation.hvac_aggregations
from bim2sim.elements import aggregation
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.elements.mapping.units import ureg
from test.unit.elements.helper import SetupHelperHVAC


class UFHHelper(SetupHelperHVAC):

    def get_setup_ufh1(self):
        """
        Simple underfloorheating
        """
        flags = {}

        x_dimension = 5 * ureg.meter
        y_dimension = 4 * ureg.meter
        spacing = 0.19 * ureg.meter
        with self.flag_manager(flags):
            # elements generator
            ny_pipes = math.floor(y_dimension / spacing)
            y_pipes = [self.element_generator(
                hvac.Pipe, length=y_dimension / ny_pipes, diameter=15) for
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
        return graph, flags

    @classmethod
    def connect_ufh(cls, x_pipes, y_pipes, x_dimension, spacing):
        """
        Function to connect an UFH taking into account the number of pipes
        laid in x and y, the pipes spacing and the room dimension in x
        Args:
            x_pipes: UFH Pipes laid parallel to x-axis
            y_pipes: UFH Pipes laid parallel to y-axis
            x_dimension: Dimension of the room parallel to x-axis
            spacing: spacing of the UFH parallel to y-axis

        Returns:
            ufh_strand: resultant connected ufh strand

        """
        position = np.array([0.0, 0.0, 0.0])
        n = 0
        for item in x_pipes:
            item.position = position.copy()
            port_position = position.copy()
            if n % 2:
                port_position[0] += x_dimension.m / 2
                item.ports[0].position = port_position.copy()
                port_position[0] -= x_dimension.m
                item.ports[1].position = port_position.copy()
            else:
                port_position[0] -= x_dimension.m / 2
                item.ports[0].position = port_position.copy()
                port_position[0] += x_dimension.m
                item.ports[1].position = port_position.copy()
            position[1] += spacing.m
            n += 1
        position = np.array([x_dimension.m / 2, spacing.m / 2, 0.0])
        n = 0
        for item in y_pipes:
            port_position = position.copy()
            item.position = position.copy()
            port_position[1] -= spacing.m / 2
            item.ports[0].position = port_position.copy()
            port_position[1] += spacing.m
            item.ports[1].position = port_position.copy()
            position[1] += spacing.m
            if n % 2:
                position[0] += x_dimension.m
            else:
                position[0] -= x_dimension.m
            n += 1
        ufh_strand = [None] * (len(x_pipes) + len(y_pipes))
        ufh_strand[::2] = x_pipes
        ufh_strand[1::2] = y_pipes
        cls.connect_strait(ufh_strand)
        return ufh_strand


class TestUnderfloorHeating(unittest.TestCase):

    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = UFHHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_simple_ufh(self):
        """ Test aggregation of underfloor heating no. 1."""
        graph, flags = self.helper.get_setup_ufh1()
        ele = graph.elements

        matches, meta = bim2sim.elements.aggregation.hvac_aggregations.UnderfloorHeating.find_matches(graph)
        self.assertEqual(1, len(matches))
        agg = bim2sim.elements.aggregation.hvac_aggregations.UnderfloorHeating(graph, matches[0], **meta[0])

        exp_length = sum([e.length for e in ele])
        self.assertAlmostEqual(exp_length, agg.length)
        self.assertAlmostEqual(20 * ureg.meter ** 2, agg.heating_area, 0)
        self.assertAlmostEqual(15 * ureg.millimeter, agg.diameter, 0)
        self.assertAlmostEqual(.2 * ureg.meter, agg.y_spacing, 1)
        self.assertAlmostEqual(.24 * ureg.meter, agg.x_spacing, 2)


if __name__ == '__main__':
    unittest.main()
