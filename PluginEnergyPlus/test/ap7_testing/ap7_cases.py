import unittest
from pathlib import Path


import os

from bim2sim import workflow
from bim2sim.decision.decisionhandler import DebugDecisionHandler
from test.integration_test.test_integration import IntegrationBaseEP

EXAMPLE_PATH = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent.parent / 'ExampleFiles'
RESULT_PATH = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent.parent / 'ResultFiles'
DEBUG_ENERGYPLUS = True


class AP7EPCases(IntegrationBaseEP, unittest.TestCase):
    """
    AP7 tests for multiple IFC example files.
    Tested are IFC files from Eric Fichter's Space Boundary Generation tool.
    """

    def test_ap7_DH88_heavy(self):
        """Test DigitalHub IFC"""
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_fixed002.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('Autodesk Revit 2020 (DEU)', *(None,)*150, True, True, 2015, 'heavy',
                   'Waermeschutzverglasung, dreifach', True, False, False,
                   True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    def test_ap7_DH88_light(self):
        """Test DigitalHub IFC"""
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_fixed002.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('Autodesk Revit 2020 (DEU)', *(None,)*150, True, True, 2015, 'light',
                   'Waermeschutzverglasung, dreifach', True, False, False, True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)

    def test_ap7_FZK_CFD_heavy(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = EXAMPLE_PATH / 'AC20-FZK-Haus.ifc'
        project = self.create_project(ifc, 'energyplus',
                                      workflow.BPSMultiZoneSeparatedEPforCFD())
        answers = (True, True, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, '
                   'zweifach', True, True, True, False)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(
                project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value)

    def test_ap7_DH_CFD_heavy(self):
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_fixed002.ifc'
        project = self.create_project(ifc, 'energyplus',
                                      workflow.BPSMultiZoneSeparatedEPforCFD())
        answers = ('Autodesk Revit 2020 (DEU)', *(None,)*150, True, True,
                   2015, 'heavy', 'Waermeschutzverglasung, dreifach', True,
                   False, False, True)
        handler = DebugDecisionHandler(answers)
        return_code = handler.handle(project.run())
        self.assertEqual(0, return_code)


if __name__ == '__main__':
    unittest.main()
