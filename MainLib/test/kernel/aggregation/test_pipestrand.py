import unittest
from unittest import mock

from bim2sim.kernel import aggregation
from bim2sim.kernel.element import Port
from bim2sim.kernel.elements import Pipe

from .base import TestAggregation

class TestPipeStrand(TestAggregation):

    pipes = []

    @classmethod
    def setUpClass(cls):

        with mock.patch.object(Pipe, '_add_ports', return_value=None):

            for i in range(10):
                # pip instances
                pipe = Pipe(cls.ifc)
                cls.pipes.append(pipe)
                # attributes
                pipe.length = i % 2 * 100 + 100
                if i < 5:
                    pipe.diameter = 20
                else:
                    pipe.diameter = 40

        # add ports
        for pipe in cls.pipes:
            cls.fake_add_ports(pipe)

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()

        for item in cls.pipes.copy():
            item.discard()

    def test_pipestrand(self):

        self.connect_strait(self.pipes)
        models = self.pipes[1:9]

        agg = aggregation.PipeStrand("Test", models)

        exp_length = sum([m.length for m in models])
        self.assertAlmostEqual(agg.length, exp_length)

        self.assertAlmostEqual(agg.diameter, 30)

        mapping = agg.get_replacement_mapping()

        self.assertIs(agg.ports[0], mapping[models[0].ports[0]])
        self.assertIs(agg.ports[1], mapping[models[-1].ports[1]])


if __name__ == '__main__':
    unittest.main()
