import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bim2sim.plugins import Plugin
from bim2sim.project import Project
from bim2sim.simulation_settings import PlantSimSettings

sample_root = Path(__file__).parent.parent.parent / 'test/TestModels/HVAC'


class PluginDummy(Plugin):
    name = "Dummy"
    default_settings = PlantSimSettings
    tasks = []


class BaseTestProject(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='bim2sim_')
        self.path = os.path.join(self.directory.name, 'proj')

    def tearDown(self):
        try:
            self.directory.cleanup()
        except PermissionError:
            pass


class TestProject(BaseTestProject):

    def test_create_remove(self):
        """Test creation and deletion of Project"""

        project = Project.create(
            self.path,
            sample_root /
            'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc',
            PluginDummy
        )

        self.assertTrue(os.path.samefile(self.path, project.paths.root))
        self.assertTrue(os.path.exists(project.paths.config))
        self.assertTrue(os.path.exists(project.paths.ifc))

        project.delete()

        self.assertFalse(os.path.exists(project.paths.root),
                         f"Project folder {project.paths} not deleted!")

    def test_double_create(self):
        """Test creating two projects in same dir"""
        project = Project.create(
            self.path,
            sample_root /
            'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc',
            PluginDummy
        )
        self.assertTrue(os.path.exists(project.paths.ifc))
        project.finalize(True)
        shutil.rmtree(project.paths.ifc)
        self.assertFalse(os.path.exists(project.paths.ifc))

        project2 = Project.create(
            self.path,
            sample_root /
            'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc',
            PluginDummy
        )
        self.assertTrue(os.path.exists(project2.paths.ifc))
        project2.finalize(True)
