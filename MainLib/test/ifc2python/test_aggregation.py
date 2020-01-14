import unittest

from bim2sim.kernel import aggregation
from bim2sim.kernel.elements import Pipe

# TODO: expand test for ports when implemented
class DummyIFC():

    class Port:
        RelatingPort = None

    def __init__(self, guid, name):
        self.GlobalId = guid
        self.Name = name
        self.HasPorts = [DummyIFC.Port(), DummyIFC.Port()]

class DummyPipe(Pipe):

    def __init__(self, n, length, diameter):
        ifc = DummyIFC("id%d"%n, "Pipe%d"%n)
        super().__init__(ifc)
        self._diameter = diameter
        self._length = length

    @property
    def length(self):
        return self._length

    @property
    def diameter(self):
        return self._diameter

@unittest.skip("Testcase needs update")
class TestAggregation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pipe1 = DummyPipe(1, 300, 32)
        cls.pipe2 = DummyPipe(2, 800, 32)
        cls.pipe3 = DummyPipe(3, 300, 25)
        cls.pipe4 = DummyPipe(4, 500, 25)

    def test_pipestrand(self):

        models = [
            TestAggregation.pipe1, 
            TestAggregation.pipe2,
            TestAggregation.pipe3,
            TestAggregation.pipe4,
        ]
        agg = aggregation.PipeStrand("Test", models)

        exp_length = sum([m.length for m in models])
        self.assertAlmostEqual(agg.length, exp_length)

        self.assertLessEqual(agg.diameter, 32)
        self.assertGreaterEqual(agg.diameter, 25)

if __name__ == '__main__':
    unittest.main()
