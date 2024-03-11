import unittest

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler

from bim2sim.tasks.bps import enrich_use_cond
from bim2sim.utilities.common_functions import get_pattern_usage, \
    get_use_conditions_dict
from test.unit.elements.helper import SetupHelperBPS


class TestEnrichUseCond(unittest.TestCase):
    helper: SetupHelperBPS = None

    @classmethod
    def setUpClass(cls):
        cls.helper = SetupHelperBPS()

    def tearDown(self):
        self.helper.reset()

    def test_with_five_different_zones(self):
        """Tests if usages get set correctly for five ThermalZone elements.

        The first ThermalZone has a usage that can be identified by regular
        expressions ('Wohnen').
        The second ThermalZone is a direct fit to the existing usage conditions.
        The third and fourth ThermalZone can't be identified due to random names
        , but the third one is similar to the first).
        The fifth ThermalZone can again be identified using the office_usage
        function.

        """
        prj_name = 'test'
        usages = [
            'Wohnen',
            'Living',
            'NotToIdentify',  # should be found as 'Bed room'
            'NotToIdentifyAsWell',  # should be found as 'Kitchen'
            'Office'
        ]
        tz_elements = self.helper.get_thermalzones_diff_usage(usages)
        expected_usages_list = [
            'Living',
            'Living',
            'Bed room',
            'Kitchen - preparations, storage',
            'Open-plan Office (7 or more employees)'
        ]
        expected_usages = {
            tz_elements[i]: expected_usages_list[i] for i in range(
                len(tz_elements))}
        tz_elements_dict = {tz.guid: tz for tz in tz_elements}
        handler = DebugDecisionHandler(
            answers=['Bed room', 'Kitchen - preparations, storage'])
        # No custom usages and use conditions required for this test
        custom_usage_path = None
        custom_use_conditions_path = None
        self.use_conditions = get_use_conditions_dict(custom_usage_path)
        pattern_usage = get_pattern_usage(self.use_conditions,
                                          custom_use_conditions_path)
        found_usages = handler.handle(
            enrich_use_cond.EnrichUseConditions.enrich_usages(
                pattern_usage, tz_elements_dict))
        self.assertDictEqual(
            expected_usages,
            found_usages)
