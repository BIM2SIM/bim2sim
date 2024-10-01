import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bim2sim
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.tasks.common import LoadIFC

test_rsrc_path = Path(__file__).parent.parent.parent.parent / 'resources'


class TestLoadIFC(unittest.TestCase):
    load_task = None
    export_path = None
    playground = None

    @classmethod
    def setUpClass(cls) -> None:
        # Set up playground, project and paths via mocks
        cls.playground = mock.Mock()
        project = mock.Mock()
        paths = mock.Mock()
        cls.playground.project = project

        # Instantiate export task and set required values via mocks
        cls.load_ifc_task = LoadIFC(cls.playground)
        cls.load_ifc_task.prj_name = 'TestLoadIFC'
        cls.load_ifc_task.paths = paths
        cls.load_ifc_task.paths.finder = (
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

        self.load_ifc_task.paths.ifc_base = temp_path / 'ifc'
        DebugDecisionHandler(answers=()).handle(self.load_ifc_task.run())

    def test_load_ifczip(self):
        ifc_temp_dir = tempfile.TemporaryDirectory(
            prefix='bim2sim_test_load_ifc')
        temp_path = Path(ifc_temp_dir.name)
        subdir_path = temp_path / 'ifc/arch'
        subdir_path.mkdir(parents=True, exist_ok=True)
        source_file = test_rsrc_path / 'arch/ifc/AC20-FZK-Haus.ifczip'
        destination_file = subdir_path / source_file.name
        shutil.copy2(source_file, destination_file)

        self.load_ifc_task.paths.ifc_base = temp_path / 'ifc'
        DebugDecisionHandler(answers=()).handle(self.load_ifc_task.run())

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

        self.load_ifc_task.paths.ifc_base = temp_path / 'ifc'
        DebugDecisionHandler(answers=()).handle(self.load_ifc_task.run())
