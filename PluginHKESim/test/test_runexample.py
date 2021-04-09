import unittest
import os
import shutil
import tempfile

import bim2sim


IFC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(bim2sim.__file__), '../..', 
    r'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'))

class TestRunExample(unittest.TestCase):

    def test_hkesim(self):
        
        with tempfile.TemporaryDirectory(prefix='bim2sim_') as path:
            bim2sim.PROJECT.create(path, IFC_PATH, 'hkesim')
            bim2sim.setup_default(path)

            results = os.listdir(bim2sim.PROJECT.export)

        self.assertTrue(results)

if __name__ == '__main__':
    unittest.main()
