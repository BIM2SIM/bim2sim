import sys
import unittest

import os

from bim2sim import _test_run_bps_ep
from bim2sim.decision import Decision
from bim2sim.utilities.test import IntegrationBase

# raise unittest.SkipTest("Integration tests not reliable for automated use")


class IntegrationBaseEP(IntegrationBase):
    # HACK: We have to remember stderr because eppy resets it currently.
    def setUp(self):
        self.old_stderr = sys.stderr
        self.working_dir = os.getcwd()
        super().setUp()

    def tearDown(self):
        os.chdir(self.working_dir)
        sys.stderr = self.old_stderr
        super().tearDown()


class TestEPIntegration(IntegrationBaseEP, unittest.TestCase):
    """
    Integration tests for multiple IFC example files.
    Tested are both original IFC files and files from Eric Fichter's Space Boundary Generation tool.
    """

    def test_base_FZK(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = 'AC20-FZK-Haus.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = (True, True,  'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = project.run()
        self.assertEqual(0, return_code)

    def test_base_FZK_SB(self):
        """Test IFC File from FZK-Haus (KIT) with generated Space Boundaries"""

        # rel_path = 'ResultFiles/AC20-FZK-Haus_with_SB44.ifc'
        rel_path = 'ResultFiles/AC20-FZK-Haus_with_SB55.ifc'
        answers = (True, True, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertEqual(0, return_code)


    def test_base_KIT_Inst(self):
        """Test Original IFC File from Institute (KIT)"""

        rel_path = 'ExampleFiles/AC20-Institute-Var-2.ifc'
        answers = (True, True,  'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertEqual(0, return_code)


    def test_base_KIT_Inst_SB(self):
        """Test IFC File from Institute (KIT) with generated Space Boundaries"""

        # rel_path = 'ResultFiles/AC20-Institute-Var-2_with_SB11.ifc'
        rel_path = 'ResultFiles/AC20-Institute-Var-2_with_SB55.ifc'
        answers = (True, True,  'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertEqual(0, return_code)


    def test_base_DH(self):
        """Test DigitalHub IFC"""
        # rel_path = 'ExampleFiles/DigitalHub_Architektur2_2020_Achse_tragend_V2.ifc'
        # rel_path = 'ResultFiles/FM_ARC_DigitalHub_with_SB11.ifc'
        rel_path = 'ResultFiles/FM_ARC_DigitalHub_with_SB55.ifc'
        answers = (True, True, 'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertEqual(0, return_code)


    def test_base_KHH(self):
        """Test KIT KHH 3 storey IFC"""
        rel_path = 'ExampleFiles/KIT-EDC.ifc'
        answers = ('ARCHICAD-64', True, True, 'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertEqual(0, return_code)


    def test_base_EDC_SB(self):
        """Test KIT KHH 3 storey IFC with generated Space Boundaries"""
        rel_path = 'ResultFiles/KIT-EDC_with_SB.ifc'
        answers = ('ARCHICAD-64', True, True, 'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertEqual(0, return_code)



if __name__ == '__main__':
    unittest.main()
