import unittest
import os
import shutil
import tempfile

import bim2sim

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

class TestRunExample(unittest.TestCase):

    def test_hkesim(self):
        
        bim2sim.PROJECT.create(PATH, IFC_PATH, 'hkesim')
        bim2sim.main(PATH)

        results = os.listdir(bim2sim.PROJECT.export)
        self.assertTrue(results)

if __name__ == '__main__':
    unittest.main()
