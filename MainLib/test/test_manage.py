import unittest
import os
import shutil
import tempfile

import bim2sim
from bim2sim import manage


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
        self.directory.cleanup()


class TestManage(BaseTestManage):

    def test_create_remove(self):

        manage.PROJECT.create(self.path, IFC_PATH)

        self.assertEqual(manage.PROJECT.root, self.path)
        self.assertTrue(os.path.exists(manage.PROJECT.config))
        self.assertTrue(os.path.exists(manage.PROJECT.ifc))

        manage.PROJECT.delete(False)

        self.assertIsNone(manage.PROJECT.root)
        self.assertIsNone(manage.PROJECT.config)
        self.assertIsNone(manage.PROJECT.ifc)

    def test_double_create(self):

        manage.PROJECT.create(self.path, IFC_PATH)

        self.assertTrue(os.path.exists(manage.PROJECT.ifc))

        shutil.rmtree(manage.PROJECT.ifc)

        self.assertFalse(os.path.exists(manage.PROJECT.ifc))

        manage.PROJECT.create(self.path, IFC_PATH)

        self.assertTrue(os.path.exists(manage.PROJECT.ifc))


class Manager(manage.BIM2SIMManager):

    def prepare(self): 
        pass

class Test_Manager(BaseTestManage):

    def test_manager_project_set(self):

        manage.PROJECT.root = None
        with self.assertRaises(AssertionError):
            manager = Manager(None)

        #manage.PROJECT.root = self.path
        manage.PROJECT.create(self.path, IFC_PATH)
        manager = Manager(None)

        #manager.run()


if __name__ == '__main__':
    unittest.main()
