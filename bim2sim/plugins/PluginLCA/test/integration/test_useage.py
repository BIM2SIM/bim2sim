import unittest


class TestUsage(unittest.TestCase):
    """Tests for general use of library"""

    def test_import_plugin(self):
        """Test importing LCA plugin in python script"""
        try:
            from bim2sim.plugins import load_plugin, Plugin
            plugin = load_plugin('bim2sim_lca')
            assert issubclass(plugin, Plugin)
        except ImportError as err:
            self.fail("Unable to import plugin\nreason: %s"%(err))


if __name__ == '__main__':
    unittest.main()
