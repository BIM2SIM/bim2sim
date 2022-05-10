import unittest
import os
import shutil
import tempfile

import bim2sim
from bim2sim.project import Project



IFC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(bim2sim.__file__), '..',
    r'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'))


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

        project = Project.create(self.path, IFC_PATH, 'dummy')

        self.assertTrue(os.path.samefile(self.path, project.paths.root))
        self.assertTrue(os.path.exists(project.paths.config))
        self.assertTrue(os.path.exists(project.paths.ifc))

        project.delete()

        self.assertFalse(os.path.exists(project.paths.root),
                         f"Project folder {project.paths} not deleted!")

    def test_double_create(self):
        """Test creating two projects in same dir"""
        project = Project.create(self.path, IFC_PATH, 'dummy')
        self.assertTrue(os.path.exists(project.paths.ifc))
        project.finalize(True)
        shutil.rmtree(project.paths.ifc)
        self.assertFalse(os.path.exists(project.paths.ifc))

        project2 = Project.create(self.path, IFC_PATH, 'dummy')
        self.assertTrue(os.path.exists(project2.paths.ifc))
        project2.finalize(True)
