import unittest
import os
import shutil
import tempfile

import bim2sim
from bim2sim import manage

TEMP = None
PATH = None
IFC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(bim2sim.__file__), '../..', 
    r'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'))

def setUpModule():
    global TEMP, PATH
    TEMP = tempfile.mkdtemp()
    PATH = os.path.join(TEMP, 'testproject')

def tearDownModule():
    shutil.rmtree(PATH, ignore_errors=True)

class BaseTestManage(unittest.TestCase):

    def __init__(self, methodName = 'runTest'):
        super().__init__(methodName)
        self._allow_delete = False

    def setUp(self):
        self.assertFalse(os.path.exists(PATH), "Path to test folder exists. Can't perform test. (Delete folder manualy)")
        self._allow_delete = True

    def tearDown(self):
        if self._allow_delete:
            try:
                manage.PROJECT.delete(False)
            except AssertionError as ex:
                pass
            self._allow_delete = False

class TestManage(BaseTestManage):

    def test_create_remove(self):

        manage.PROJECT.create(PATH, IFC_PATH)

        self.assertEqual(manage.PROJECT.root, PATH)
        self.assertTrue(os.path.exists(manage.PROJECT.config))
        self.assertTrue(os.path.exists(manage.PROJECT.ifc))

        manage.PROJECT.delete(False)

        self.assertIsNone(manage.PROJECT.root)
        self.assertIsNone(manage.PROJECT.config)
        self.assertIsNone(manage.PROJECT.ifc)

    def test_double_create(self):

        manage.PROJECT.create(PATH, IFC_PATH)

        self.assertTrue(os.path.exists(manage.PROJECT.ifc))

        shutil.rmtree(manage.PROJECT.ifc)

        self.assertFalse(os.path.exists(manage.PROJECT.ifc))

        manage.PROJECT.create(PATH, IFC_PATH)

        self.assertTrue(os.path.exists(manage.PROJECT.ifc))


class Manager(manage.BIM2SIMManager):

    def prepare(self): 
        pass

class Test_Manager(BaseTestManage):

    def test_manager_project_set(self):

        manage.PROJECT.root = None
        with self.assertRaises(AssertionError):
            manager = Manager(None)

        #manage.PROJECT.root = PATH
        manage.PROJECT.create(PATH, IFC_PATH)
        manager = Manager(None)

        manager.run()


if __name__ == '__main__':
    unittest.main()
