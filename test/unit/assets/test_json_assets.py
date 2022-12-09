"""Testing all json assets for integrity
"""

import os
import tempfile
import unittest
from pathlib import Path

import bim2sim
from bim2sim.utilities.common_functions import validateJSON


class TestJSONAssets(unittest.TestCase):

        @classmethod
        def setUpClass(cls):
            cls.root = tempfile.TemporaryDirectory(prefix='bim2sim_')
            os.mkdir(os.path.join(cls.root.name, 'templates'))

        @classmethod
        def tearDownClass(cls):
            # Decision.reset_decisions()
            cls.root.cleanup()

        def test_json_assets(self):
            assets_path = Path(bim2sim.__file__).parent / 'assets/'
            json_gen = assets_path.rglob('*.json')
            invalids = []
            for json_file_path in json_gen:
                if not validateJSON(json_file_path):
                    invalids.append(json_file_path)
            self.assertEqual(
                len(invalids), 0, 'Invalid JSON files found: {}'.format(
                    invalids))
