import unittest

from decision.decisionhandler import DebugDecisionHandler
from test.unit.kernel.helper import SetupHelperBPS
from bim2sim.task.bps import enrich_use_cond


class TestEnrichUseCond(unittest.TestCase):
    helper: SetupHelperBPS = None

    @classmethod
    def setUpClass(cls):
        cls.helper = SetupHelperBPS()

    def tearDown(self):
        self.helper.reset()

    def test_with_five_different_zones(self):
        """Tests if usages get set correctly for five ThermalZone instances.

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
        tz_instances = self.helper.get_thermalzones_diff_usage(usages)
        expected_usages_list = [
            'Living',
            'Living',
            'Bed room',
            'Kitchen - preparations, storage',
            'Open-plan Office (7 or more employees)'
        ]
        expected_usages = {
            tz_instances[i]: expected_usages_list[i] for i in range(
                len(tz_instances))}
        tz_instances_dict = {tz.guid: tz for tz in tz_instances}
        handler = DebugDecisionHandler(
            answers=['Bed room', 'Kitchen - preparations, storage'])
        found_usages = handler.handle(
            enrich_use_cond.EnrichUseConditions.enrich_usages(
                prj_name, tz_instances_dict))
        self.assertDictEqual(
            expected_usages,
            found_usages)
