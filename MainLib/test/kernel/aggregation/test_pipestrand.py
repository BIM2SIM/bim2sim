import unittest
from unittest import mock

from bim2sim.kernel import aggregation
from bim2sim.kernel.element import Port
from bim2sim.kernel.elements import Pipe

from test.kernel.aggregation.base import AggregationHelper


class TestPipeStrand(unittest.TestCase):

    helper = None

    @classmethod
    def setUpClass(cls):

        cls.helper = AggregationHelper()

        # elements = cls.helper.flags.get('strand1')
        # cls.test_aggregation = aggregation.PipeStrand("Test", elements)

        # pipes = []
        # with mock.patch.object(Pipe, '_add_ports', return_value=None):
        #
        #     for i in range(10):
        #         # pip instances
        #         pipe = Pipe(cls.ifc)
        #         pipes.append(pipe)
        #         # attributes
        #         pipe.length = i % 2 * 100 + 100
        #         if i < 5:
        #             pipe.diameter = 20
        #         else:
        #             pipe.diameter = 40
        #
        # # add ports
        # for pipe in pipes:
        #     cls.fake_add_ports(pipe)
        #
        # # setups
        # cls.connect_strait(pipes)
        # cls.setups.append(pipes)
        #
        # # aggregation for default tests
        # cls.test_aggregation = aggregation.PipeStrand("Aggregation Test", cls.setups[0][1:9])
        # cls.edge_ports.extend([cls.setups[0][0].ports[1].connection, cls.setups[0][-1].ports[0].connection])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.helper.reset()

    def test_pipestrand1(self):
        """Test calculation of aggregated length and diameter"""
        graph, flags = self.helper.get_setup()
        elements = flags['strand1']
        agg = aggregation.PipeStrand("Test 1", elements)

        exp_length = sum([e.length for e in elements])
        self.assertAlmostEqual(agg.length, exp_length)

        self.assertAlmostEqual(agg.diameter, 40)

    def test_pipestrand2(self):
        """Test calculation of aggregated length and diameter"""

        graph, flags = self.helper.get_setup()
        elements = flags['strand2']
        agg = aggregation.PipeStrand("Test 2", elements)

        exp_length = sum([e.length for e in elements])
        self.assertAlmostEqual(agg.length, exp_length)

        self.assertAlmostEqual(agg.diameter, 15)

    def test_basics(self):
        graph, flags = self.helper.get_setup()
        elements = flags['strand1']
        agg = aggregation.PipeStrand("Test basics", elements)

        self.assertTrue(self.helper.elements_in_agg(agg))

    def test_detection(self):
        self.skipTest("Detection for PipeStrand not implementes")


if __name__ == '__main__':
    unittest.main()
