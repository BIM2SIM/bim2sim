"""Testing Finders
"""

import unittest
import os
import tempfile

import bim2sim
from bim2sim.kernel.elements import hvac
from bim2sim.kernel import ifc2python
from bim2sim.kernel.finder import TemplateFinder


IFC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(bim2sim.__file__), '..',
    r'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'))


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

    def tearDown(self):
        del self.finder

    def test_set_find(self):
        tool = self.pipe1.source_tool
        for decision in self.finder.check_tool_template(tool):
            decision.value = 'Other'

        self.finder.set(tool, 'IfcPipeSegment', 'length', 'Abmessungen', 'Länge')
        self.finder.set(tool, 'IfcPipeSegment', 'diameter', 'Abmessungen', 'Innendurchmesser')
        self.finder.set(tool, 'IfcPipeFitting', 'diameter', 'Abmessungen', 'Nenndurchmesser')

        l1 = self.finder.find(self.pipe1, 'length')
        d1 = self.finder.find(self.pipe1, 'diameter')
        l2 = self.finder.find(self.pipe2, 'length')
        d2 = self.finder.find(self.pipe2, 'diameter')
        l3 = self.finder.find(self.pipefitting1, 'length')
        d3 = self.finder.find(self.pipefitting1, 'diameter')

    def test_save_load(self):
        tool = self.pipe1.source_tool
        self.finder.set(tool, 'IfcPipeSegment', 'length', 'Abmessungen', 'Länge')
        self.finder.set(tool, 'IfcPipeSegment', 'diameter', 'Abmessungen', 'Innendurchmesser')
        self.finder.set(tool, 'IfcPipeFitting', 'diameter', 'Abmessungen', 'Nenndurchmesser')

        data = self.finder.templates.copy()

        path = os.path.join(self.root.name, 'templates')
        self.finder.save(path)

        self.finder.templates.clear()

        self.finder.load(path)

        self.assertDictEqual(data, self.finder.templates)


if __name__ == '__main__':
    unittest.main()
