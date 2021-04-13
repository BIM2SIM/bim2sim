import sys
import unittest
import tempfile
from shutil import copyfile, copytree, rmtree
from pathlib import Path

import os

from bim2sim import _test_run_bps_ep
from bim2sim.decision import Decision
from bim2sim.utilities.test import IntegrationBase
from bim2sim.project import Project

# raise unittest.SkipTest("Integration tests not reliable for automated use")

EXAMPLE_PATH = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent.parent / 'ExampleFiles'
RESULT_PATH = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent.parent / 'ResultFiles'
DEBUG_ENERGYPLUS = False


class IntegrationBaseEP(IntegrationBase):
    # HACK: We have to remember stderr because eppy resets it currently.
    def setUp(self):
        self.old_stderr = sys.stderr
        self.working_dir = os.getcwd()
        super().setUp()

    def tearDown(self):
        if DEBUG_ENERGYPLUS: # copy EP-results to home directory for further debugging.
            if not os.path.exists(Path.home() / 'idf'):
                os.mkdir(Path.home() / 'idf')
            ifc_name = str(os.listdir(self.project.paths.ifc)[0].split('.ifc')[0])
            temp_dir = Path(self.project.paths.export) / "EP-results/"
            debug_dir = Path.home() / 'idf' / Path(ifc_name + '_EP-results/')
            if os.path.exists(debug_dir):
                rmtree(debug_dir)
            copytree(temp_dir,
                     debug_dir)
            copyfile(str(debug_dir) + "/eplusout.expidf",
                     str(debug_dir) + "/eplusout.idf")
        os.chdir(self.working_dir)
        sys.stderr = self.old_stderr
        super().tearDown()

    def create_project(self, ifc_path: str, plugin: str):
        """create project in temporary directory which is cleaned automatically after test.

        :param plugin: Project plugin e.g. 'hkesim', 'aixlib', ...
        :param ifc: name of ifc file located in dir TestModels"""

        # path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        # ifc_path = os.path.normpath(os.path.join(path_base, rel_ifc_path))
        self.project = Project.create(
            tempfile.TemporaryDirectory(prefix='bim2sim_').name,
            ifc_path=ifc_path,
            default_plugin=plugin)
        return self.project



class TestEPIntegration(IntegrationBaseEP, unittest.TestCase):
    """
    Integration tests for multiple IFC example files.
    Tested are both original IFC files and files from Eric Fichter's Space Boundary Generation tool.
    """

    def test_base_FZK(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc = EXAMPLE_PATH / 'AC20-FZK-Haus.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = (True, True,  'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = project.run()
        self.assertEqual(0, return_code)

    def test_base_FZK_SB(self):
        """Test IFC File from FZK-Haus (KIT) with generated Space Boundaries"""
        # ifc = RESULT_PATH / 'AC20-FZK-Haus_with_SB44.ifc'
        ifc = RESULT_PATH / 'AC20-FZK-Haus_with_SB55.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = (True, True, 'heavy',
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = project.run()
        self.assertEqual(0, return_code)


    def test_base_KIT_Inst(self):
        """Test Original IFC File from Institute (KIT)"""

        ifc = EXAMPLE_PATH / 'AC20-Institute-Var-2.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = (True, True,  'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = project.run()
        self.assertEqual(0, return_code)


    def test_base_KIT_Inst_SB(self):
        """Test IFC File from Institute (KIT) with generated Space Boundaries"""

        # ifc = RESULT_PATH / 'AC20-Institute-Var-2_with_SB11.ifc'
        ifc = RESULT_PATH / 'AC20-Institute-Var-2_with_SB55.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = (True, True,  'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = project.run()
        self.assertEqual(0, return_code)


    def test_base_DH(self):
        """Test DigitalHub IFC"""
        # ifc = EXAMPLE_PATH / 'DigitalHub_Architektur2_2020_Achse_tragend_V2.ifc'
        # ifc = RESULT_PATH / 'FM_ARC_DigitalHub_with_SB11.ifc'
        ifc = RESULT_PATH / 'FM_ARC_DigitalHub_with_SB55.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = (True, True, 'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = project.run()
        self.assertEqual(0, return_code)


    def test_base_KHH(self):
        """Test KIT KHH 3 storey IFC"""
        ifc = EXAMPLE_PATH / 'KIT-EDC.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('ARCHICAD-64', True, True, 'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = project.run()
        self.assertEqual(0, return_code)


    def test_base_EDC_SB(self):
        """Test KIT KHH 3 storey IFC with generated Space Boundaries"""
        ifc = RESULT_PATH / 'KIT-EDC_with_SB.ifc'
        project = self.create_project(ifc, 'energyplus')
        answers = ('ARCHICAD-64', True, True, 'heavy', 2015,
                   'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach', 'ARCHICAD-64')
        with Decision.debug_answer(answers, multi=True):
            return_code = project.run()
        self.assertEqual(0, return_code)



if __name__ == '__main__':
    unittest.main()
