import unittest
import tempfile
import shutil
import logging
from pathlib import Path
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils.utils_hash_function import (
    generate_hash,
    add_hash_into_idf,
)


logger = logging.getLogger(__name__)
# Set up logger to print to console
if not logger.handlers:
    _handler = logging.StreamHandler()
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


test_rsrc_path = (Path(
    __file__).parent.parent.parent.parent.parent.parent.parent
                  / 'test/resources')


class TestHashFunction(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.test_dir.cleanup()

    def test_generate_hash_and_write_to_idf(self):
        """Unit test: generate IFC hash and prepend to IDF."""

        # Locate IFC test file
        ifc_path = test_rsrc_path / 'arch/ifc/AC20-FZK-Haus.ifc'

        # Use predefined expected correct hash for AC20-FZK-Haus.ifc in the resources folder
        expected_hash = "b0b6cbe8e780f537417a7d67bc98966d2a9cd8644472e77fd3f9f1e5bb1fa97b"

        # Use utils_hash_function to generate hash line and compare with expected hash
        hash_line = generate_hash(str(ifc_path))
        logger.info("Generated hash line: %s", hash_line.strip())
        self.assertTrue(hash_line.startswith('! IFC_GEOMETRY_HASH:'), "Hash line prefix incorrect")
        self.assertIn(expected_hash, hash_line, "Hash content mismatch")
        self.assertIn(ifc_path.name, hash_line, "IFC filename not included")

        # Prepare a temp copy of Minimal.idf
        plugin_data_dir = Path(__file__).parents[3] / 'data'
        minimal_idf = plugin_data_dir / 'Minimal.idf'
        tmp_idf_path = Path(self.test_dir.name) / 'Minimal.idf'
        shutil.copyfile(minimal_idf, tmp_idf_path)

        # Ensure there is no hash in the first line
        with open(tmp_idf_path, 'r', encoding='utf-8') as f:
            original_first_line = f.readline()
        self.assertNotIn("IFC_GEOMETRY_HASH", original_first_line,
                         f"IDF file already contains hash in first line: '{original_first_line.strip()}'")

        # Add hash to IDF
        add_hash_into_idf(hash_line, str(tmp_idf_path))
        with open(tmp_idf_path, 'r', encoding='utf-8') as f:
            new_first_line = f.readline()

        self.assertEqual(new_first_line, hash_line)


if __name__ == '__main__':
    unittest.main()
