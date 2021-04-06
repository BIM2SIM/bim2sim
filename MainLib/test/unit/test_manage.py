import unittest
import os
import shutil
import tempfile

import bim2sim
from bim2sim import plugin


IFC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(bim2sim.__file__), '../..', 
    r'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'))


class BaseTestManage(unittest.TestCase):

    #def __init__(self, methodName = 'runTest'):
    #    super().__init__(methodName)
    #    self._allow_delete = False

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='bim2sim_')
        self.path = os.path.join(self.directory.name, 'proj')

    def tearDown(self):
        try:
            self.directory.cleanup()
        except PermissionError:
            pass


class TestManage(BaseTestManage):

    def test_create_remove(self):

        plugin.PROJECT.create(self.path, IFC_PATH)

        self.assertTrue(os.path.samefile(self.path, plugin.PROJECT.root))
        self.assertTrue(os.path.exists(plugin.PROJECT.config))
        self.assertTrue(os.path.exists(plugin.PROJECT.ifc))

        plugin.PROJECT.delete(False)

        self.assertIsNone(plugin.PROJECT.root)
        self.assertIsNone(plugin.PROJECT.config)
        self.assertIsNone(plugin.PROJECT.ifc)

    def test_double_create(self):

        plugin.PROJECT.create(self.path, IFC_PATH)

        self.assertTrue(os.path.exists(plugin.PROJECT.ifc))

        shutil.rmtree(plugin.PROJECT.ifc)

        self.assertFalse(os.path.exists(plugin.PROJECT.ifc))

        plugin.PROJECT.create(self.path, IFC_PATH)

        self.assertTrue(os.path.exists(plugin.PROJECT.ifc))


class Manager(plugin.Plugin):

    def prepare(self): 
        pass


class Test_Manager(BaseTestManage):

    def test_manager_project_set(self):

        plugin.PROJECT.root = None
        with self.assertRaises(AssertionError):
            manager = Manager(None)

        #manage.PROJECT.root = self.path
        plugin.PROJECT.create(self.path, IFC_PATH)
        manager = Manager(None)

        #manager.run()


if __name__ == '__main__':
    unittest.main()
