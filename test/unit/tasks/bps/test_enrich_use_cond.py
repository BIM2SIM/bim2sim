import tempfile
import unittest
from unittest import mock

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.sim_settings import BuildingSimSettings
from bim2sim.tasks.bps import EnrichUseConditions, enrich_use_cond
from bim2sim.utilities.common_functions import get_use_conditions_dict, \
    get_pattern_usage
from test.unit.elements.helper import SetupHelperBPS
from bim2sim.elements.mapping.units import ureg


class TestEnrichMaterial(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        # Set up playground, project and paths via mocks
        cls.playground = mock.Mock()
        project = mock.Mock()
        paths = mock.Mock()
        cls.playground.project = project
        cls.playground.sim_settings = BuildingSimSettings()

        # Instantiate export task and set required values via mocks
        cls.enrich_task = EnrichUseConditions(cls.playground)
        cls.enrich_task.prj_name = 'TestEnrichUseConditions'
        cls.enrich_task.paths = paths

        cls.helper = SetupHelperBPS()

    def setUp(self) -> None:
        # Set export path to temporary path
        self.export_path = tempfile.TemporaryDirectory(prefix='bim2sim')
        self.enrich_task.paths.export = self.export_path.name

    def tearDown(self) -> None:
        self.helper.reset()

    def test_enrichment_maintained_illuminance_false(self):
        """Test if sim_setting to false leads to fixed lighting power"""
        self.playground.sim_settings.use_maintained_illuminance = False
        tz = self.helper.get_thermalzone(
            guid='ThermalZone001',
            usage='Office',
            gross_area=10)
        elements = {tz.guid: tz}
        test_res = DebugDecisionHandler(()).handle(
            self.enrich_task.run(elements, ))
        self.assertEqual(tz.lighting_power, tz.fixed_lighting_power)
        self.assertEqual(tz.lighting_power, 15.9 * ureg.watt / ureg.m ** 2)

    def test_enrichment_single_office_common_conditions(self):
        """Tests enrichment of single office with common use conditions."""
        self.playground.sim_settings.use_maintained_illuminance = True
        tz = self.helper.get_thermalzone(
            guid='ThermalZone001',
            usage='Office',
            gross_area=10)
        elements = {tz.guid: tz}
        test_res = DebugDecisionHandler(()).handle(
            self.enrich_task.run(elements, ))
        self.assertEqual(tz.usage, 'Single office')
        self.assertEqual(tz.machines, 7.0 * ureg.watt / ureg.m ** 2)
        self.assertEqual(tz.use_maintained_illuminance, True)
        self.assertEqual(tz.lighting_power, 10 / 3 * ureg.watt / ureg.m ** 2)

    def test_with_five_different_zones(self):
        """Tests if usages get set correctly for five ThermalZone elements.

        The first ThermalZone has a usage that can be identified by regular
        expressions ('Wohnen').
        The second ThermalZone is a direct fit to the existing usage
        conditions.
        The third and fourth ThermalZone can't be identified due to random
        names
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
        gross_areas = [
            100,
            100,
            100,
            100,
            100
            ]
        tz_elements = self.helper.get_thermalzones_diff_usage(
            usages, gross_areas)
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
