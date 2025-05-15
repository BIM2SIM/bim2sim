"""Testing Finders
"""

import os
import tempfile
import unittest
from pathlib import Path

from bim2sim.elements.mapping import ifc2python
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.finder import TemplateFinder

IFC_PATH = (Path(
    __file__).parent.parent.parent.parent /
            'resources/hydraulic/ifc'
            '/KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc')


class TestTemplateFinder(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.TemporaryDirectory(prefix='bim2sim_')
        os.mkdir(os.path.join(cls.root.name, 'templates'))
        cls.ifc = ifc2python.load_ifc(IFC_PATH)
        pipefittings = TestTemplateFinder.ifc.by_type("IfcPipeFitting")
        pipes = TestTemplateFinder.ifc.by_type("IfcPipeSegment")
        cls.pipe1 = hvac.Pipe(ifc=pipes[0], ifc_units={})
        cls.pipe2 = hvac.Pipe(ifc=pipes[1], ifc_units={})
        cls.pipefitting1 = hvac.PipeFitting(ifc=pipefittings[0], ifc_units={})
        cls.pipefitting2 = hvac.PipeFitting(ifc=pipefittings[1], ifc_units={})

    @classmethod
    def tearDownClass(cls):
        # Decision.reset_decisions()
        cls.root.cleanup()

    def setUp(self):
        self.finder = TemplateFinder()
        for decision in self.finder.initialize(self.ifc):
            decision.value = 'Other'

    def tearDown(self):
        del self.finder

    def test_set_find(self):
        tool = self.finder.default_source_tool.templ_name

        self.finder.set(tool, 'Pipe', 'length', 'Abmessungen',
                        'Länge')
        self.finder.set(tool, 'Pipe', 'diameter', 'Abmessungen',
                        'Innendurchmesser')
        self.finder.set(tool, 'PipeFitting', 'diameter', 'Abmessungen',
                        'Nenndurchmesser')

        l1 = self.finder.find(self.pipe1, 'length')
        d1 = self.finder.find(self.pipe1, 'diameter')
        l2 = self.finder.find(self.pipe2, 'length')
        d2 = self.finder.find(self.pipe2, 'diameter')
        l3 = self.finder.find(self.pipefitting1, 'length')
        d3 = self.finder.find(self.pipefitting1, 'diameter')
        self.assertEqual(l1, 118.000000000006)
        self.assertEqual(l2, 157.999999999979)
        self.assertEqual(l3, 12.0)
        self.assertEqual(d1, 10.66)
        self.assertEqual(d2, 10.66)
        self.assertEqual(d3, 15.0)

    def test_save_load(self):
        tool = self.finder.default_source_tool.templ_name
        self.finder.set(tool, 'Pipe', 'length', 'Abmessungen',
                        'Länge')
        self.finder.set(tool, 'Pipe', 'diameter', 'Abmessungen',
                        'Innendurchmesser')
        self.finder.set(tool, 'PipeFitting', 'diameter', 'Abmessungen',
                        'Nenndurchmesser')

        data = self.finder.templates.copy()

        path = os.path.join(self.root.name, 'templates')
        self.finder.save(path)

        self.finder.templates.clear()

        self.finder.load(path)

        self.assertDictEqual(data, self.finder.templates)


if __name__ == '__main__':
    unittest.main()
