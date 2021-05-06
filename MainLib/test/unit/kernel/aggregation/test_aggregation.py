import unittest
from typing import List, Tuple

import networkx as nx

from bim2sim.kernel.elements import hvac
from bim2sim.kernel.attribute import Attribute, multi_calc
from bim2sim.kernel import aggregation
from bim2sim.kernel import elements
from bim2sim.kernel.element import ProductBased
from bim2sim.kernel.element import HVACPort
from bim2sim.kernel.hvac.hvac_graph import HvacGraph

from bim2sim.kernel.units import ureg

from test.unit.kernel.helper import SetupHelper


class SampleElement(ProductBased):
    attr1 = Attribute()
    attr2 = Attribute()
    attr3 = Attribute()


class SampleElementAggregation(aggregation.AggregationMixin, SampleElement):

    def _calc_attr1(self, name):
        total = 0
        for e in self.elements:
            total += e.attr1
        return total / len(self.elements)
    attr1 = SampleElement.attr1.to_aggregation(_calc_attr1)

    @multi_calc
    def _calc_multi(self):
        return {
            'attr2': 2,
            'attr3': 3
        }
    attr2 = SampleElement.attr2.to_aggregation(_calc_multi)
    attr3 = SampleElement.attr3.to_aggregation(_calc_multi)


class TestAggregation(unittest.TestCase):
    """Test abstract Aggregation"""

    def test_instantiation(self):
        sample1 = SampleElement(attr1=5)
        sample2 = SampleElement(attr1=15)

        agg = SampleElementAggregation([sample1, sample2])

        self.assertIsInstance(agg, SampleElement)
        self.assertEqual(10, agg.attr1)
        self.assertEqual(2, agg.attr2)
        self.assertEqual(3, agg.attr3)


# --- domain Aggregations ---

class SampleHVACElement(hvac.HVACProduct):
    attr1 = Attribute()
    attr2 = Attribute()
    attr3 = Attribute()


class SampleHVACElementAggregation(
    aggregation.HVACAggregationMixin, SampleHVACElement):

    @classmethod
    def find_matches(cls, graph: HvacGraph) -> Tuple[List[nx.Graph], List[dict]]:
        return [graph.element_graph], [{}]

    @classmethod
    def get_edge_ports(cls, graph) -> List[HVACPort]:
        return []

    def _calc_attr1(self, name):
        total = 0
        for e in self.elements:
            total += e.attr1
        return total / len(self.elements)
    attr1 = SampleHVACElement.attr1.to_aggregation(_calc_attr1)

    @multi_calc
    def _calc_multi(self):
        return {
            'attr2': 2,
            'attr3': 3
        }
    attr2 = SampleHVACElement.attr2.to_aggregation(_calc_multi)
    attr3 = SampleHVACElement.attr3.to_aggregation(_calc_multi)


class AggregationHelper(SetupHelper):

    def get_setup_sample1(self):
        """get consumer circuit made of 2 parallel pumps (equal size),
         space heater and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            eles = [self.element_generator(
                SampleHVACElement, attr1=10 * (i+1)) for i in range(3)]

        # connect
        self.connect_strait(eles)

        flags['connect'] = [eles[0], eles[-1]]
        graph = HvacGraph(eles)
        return graph, flags


class TestHVACAggregation(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = AggregationHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_instantiation(self):
        setup, flags = self.helper.get_setup_sample1()
        matches, metas = SampleHVACElementAggregation.find_matches(setup)
        agg = SampleHVACElementAggregation(matches[0], **metas[0])

        self.assertIsInstance(agg, SampleHVACElement)
        self.assertEqual(20, agg.attr1)
        self.assertEqual(2, agg.attr2)
        self.assertEqual(3, agg.attr3)


if __name__ == '__main__':
    unittest.main()
