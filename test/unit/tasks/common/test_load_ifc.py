import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bim2sim
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.tasks.common import LoadIFC

from test.unit.tasks import TestTask
from test.unit.elements.helper import SetupHelper
from bim2sim.sim_settings import BaseSimSettings

test_rsrc_path = Path(__file__).parent.parent.parent.parent / 'resources'

class TestLoadIFC(TestTask):
    @classmethod
    def simSettingsClass(cls):
        return BaseSimSettings()

    @classmethod
    def testTask(cls):
        return LoadIFC(cls.playground)

    @classmethod
    def helper(cls):
        return SetupHelper()

    # define setUpClass
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.test_task.paths.finder = (
                Path(bim2sim.__file__).parent /
                'assets/finder/template_ArchiCAD.json')

    def test_load_ifc(self):
        ifc_temp_dir = tempfile.TemporaryDirectory(
            prefix='bim2sim_test_load_ifc')
        temp_path = Path(ifc_temp_dir.name)
        subdir_path = temp_path / 'ifc/arch'
        subdir_path.mkdir(parents=True, exist_ok=True)
        source_file = test_rsrc_path / 'arch/ifc/AC20-FZK-Haus.ifc'
        destination_file = subdir_path / source_file.name
        shutil.copy2(source_file, destination_file)

        self.test_task.paths.ifc_base = temp_path / 'ifc'
        touches = DebugDecisionHandler(answers=()).handle(self.test_task.run())

        ifc_file_name = touches[0][0].ifc_file_name
        ifc_schema = touches[0][0].schema
        n_windows = len(touches[0][0].file.by_type('IfcWindow'))
        self.assertEqual(ifc_file_name, "AC20-FZK-Haus.ifc")
        self.assertEqual(ifc_schema, "IFC4")
        self.assertEqual(n_windows, 11)

    def test_load_ifczip(self):
        ifc_temp_dir = tempfile.TemporaryDirectory(
            prefix='bim2sim_test_load_ifc')
        temp_path = Path(ifc_temp_dir.name)
        subdir_path = temp_path / 'ifc/arch'
        subdir_path.mkdir(parents=True, exist_ok=True)
        source_file = test_rsrc_path / 'arch/ifc/AC20-FZK-Haus.ifczip'
        destination_file = subdir_path / source_file.name
        shutil.copy2(source_file, destination_file)

        self.test_task.paths.ifc_base = temp_path / 'ifc'
        touches = DebugDecisionHandler(
            answers=()).handle(self.test_task.run())

        ifc_file_name = touches[0][0].ifc_file_name
        ifc_schema = touches[0][0].schema
        n_windows = len(touches[0][0].file.by_type('IfcWindow'))
        self.assertEqual(ifc_file_name, "AC20-FZK-Haus.ifczip")
        self.assertEqual(ifc_schema, "IFC4")
        self.assertEqual(n_windows, 11)

    @unittest.skip("IFCXML created with IfcOpenShell seems faulty, this might "
                   "not be due to bim2sim but IfcOpenShell itself")
    def test_load_ifcxml(self):
        ifc_temp_dir = tempfile.TemporaryDirectory(
            prefix='bim2sim_test_load_ifc')
        temp_path = Path(ifc_temp_dir.name)
        subdir_path = temp_path / 'ifc/arch'
        subdir_path.mkdir(parents=True, exist_ok=True)
        source_file = test_rsrc_path / 'arch/ifc/AC20-FZK-Haus.ifcxml'
        destination_file = subdir_path / source_file.name
        shutil.copy2(source_file, destination_file)

        self.test_task.paths.ifc_base = temp_path / 'ifc'
        touches = DebugDecisionHandler(
            answers=()).handle(self.test_task.run())

        ifc_file_name = touches[0][0].ifc_file_name
        ifc_schema = touches[0][0].schema
        n_windows = len(touches[0][0].file.by_type('IfcWindow'))
        self.assertEqual(ifc_file_name, "AC20-FZK-Haus.ifcxml")
        self.assertEqual(ifc_schema, "IFC4")
        self.assertEqual(n_windows, 11)
