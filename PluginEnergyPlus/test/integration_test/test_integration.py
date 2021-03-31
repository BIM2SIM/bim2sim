import sys
import unittest

from bim2sim import _test_run_bps_ep
from bim2sim.decision import Decision


class TestEPIntegration(unittest.TestCase):
    """
    Integration tests for multiple IFC example files.
    Tested are both original IFC files and files from Eric Fichter's Space Boundary Generation tool.
    """

    def test_base_FZK(self):
        """Test Original IFC File from FZK-Haus (KIT)"""

        rel_path = 'ExampleFiles/AC20-FZK-Haus.ifc'
        answers = (True, True,  'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            success = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertTrue(success)

    def test_base_FZK_SB(self):
        """Test IFC File from FZK-Haus (KIT) with generated Space Boundaries"""

        rel_path = 'ResultFiles/AC20-FZK-Haus_with_SB44.ifc'
        answers = (True, True, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            success = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertTrue(success)

    def test_base_KIT_Inst(self):
        """Test Original IFC File from Institute (KIT)"""

        rel_path = 'ExampleFiles/AC20-Institute-Var-2.ifc'
        answers = (True, True,  'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            success = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertTrue(success)

    def test_base_KIT_Inst_SB(self):
        """Test IFC File from Institute (KIT) with generated Space Boundaries"""

        rel_path = 'ResultFiles/AC20-Institute-Var-2_with_SB11.ifc'
        answers = (True, True,  'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            success = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertTrue(success)

    def test_base_DH(self):
        """Test DigitalHub IFC"""
        # rel_path = 'ExampleFiles/DigitalHub_Architektur2_2020_Achse_tragend_V2.ifc'
        rel_path = 'ResultFiles/FM_ARC_DigitalHub_with_SB11.ifc'
        answers = (True, True, 'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            success = _test_run_bps_ep(rel_path=rel_path, temp_project=True)
            self.assertTrue(success)


if __name__ == '__main__':
    unittest.main()
