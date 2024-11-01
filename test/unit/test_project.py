import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bim2sim.plugins import Plugin
from bim2sim.project import Project
from bim2sim.sim_settings import PlantSimSettings
from bim2sim.utilities.types import IFCDomain

sample_root = Path(__file__).parent.parent.parent / \
              'test/resources/hydraulic/ifc'
ifc_paths = {
    IFCDomain.hydraulic:
        sample_root /
        'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'}


class PluginDummy(Plugin):
    name = "Dummy"
    sim_settings = PlantSimSettings
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
            ifc_paths,
            PluginDummy
        )

        self.assertTrue(os.path.samefile(self.path, project.paths.root))
        self.assertTrue(os.path.exists(project.paths.config))
        self.assertTrue(os.path.exists(project.paths.ifc_base))

        project.delete()

        self.assertFalse(os.path.exists(project.paths.root),
                         f"Project folder {project.paths} not deleted!")

    def test_double_create(self):
        """Test creating two projects in same dir"""
        project = Project.create(
            self.path,
            ifc_paths,
            PluginDummy
        )
        self.assertTrue(os.path.exists(project.paths.ifc_base))
        project.finalize(True)

        domain = list(ifc_paths.keys())[0].name
        shutil.rmtree(project.paths.ifc_base / domain)
        self.assertFalse(os.path.exists(project.paths.ifc_base / domain))

        project2 = Project.create(
            self.path,
            ifc_paths,
            PluginDummy
        )
        self.assertTrue(os.path.exists(project2.paths.ifc_base / domain))
        project2.finalize(True)
