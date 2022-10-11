import unittest
from test.unit.kernel.helper import SetupHelperBPS

# todo: create a few zones with tz.usage which are existing in common usages
#  and test if the attributes are all correctly set after enrichment


class TestEnrichUseCond(unittest.TestCase):
    helper: SetupHelperBPS = None

    @classmethod
    def setUpClass(cls):
        cls.helper = SetupHelperBPS()

    def tearDown(self):
        self.helper.reset()

    def test_with_four_different_zones(self):
        test = self.helper.get_setup_simple_house()
        print('test')