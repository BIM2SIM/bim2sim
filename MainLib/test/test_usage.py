import unittest
import subprocess


class TestUsage(unittest.TestCase):
    """Tests for general use of library"""

    def test_import_mainlib(self):
        """Test importing bim2sim in python script"""
        try:
            import bim2sim
        except ImportError as err:
            self.fail("Unable to import bim2sim\nreason: %s"%(err.msg))
        except Exception as err:
            self.skipTest("bim2sim available but errors occured on import\ndetails: %s"%(err.msg))

    def test_import_plugin(self):
        """Test importing bim2sim_energyplus in python script"""
        try:
            import bim2sim_energyplus
        except ImportError as err:
            self.fail("Unable to import plugin\nreason: %s"%(err.msg))
        except Exception as err:
            self.skipTest("Plugin available but errors occured on import\ndetails: %s"%(err.msg))

    def test_call_console(self):
        """Test calling bim2sim -h from console"""
        try:
            import bim2sim
        except:
            self.fail("Unable to localize bim2sim")
        path = '\\'.join(bim2sim.__file__.split('\\')[:-1])
        ret = subprocess.run("python %s -help"%(path))
        self.assertEqual(ret.returncode, 0, "Calling 'bim2sim -help' by console failed")


if __name__ == '__main__':
    unittest.main()
