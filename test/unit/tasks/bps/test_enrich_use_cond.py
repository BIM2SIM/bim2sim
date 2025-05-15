from bim2sim.elements.mapping.units import ureg
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.sim_settings import BuildingSimSettings
from bim2sim.tasks.bps import EnrichUseConditions, enrich_use_cond
from bim2sim.utilities.common_functions import get_use_conditions_dict, \
    get_pattern_usage
from test.unit.elements.helper import SetupHelperBPS
from test.unit.tasks import TestTask


class TestEnrichUseConditions(TestTask):
    @classmethod
    def simSettingsClass(cls):
        return BuildingSimSettings()

    @classmethod
    def testTask(cls):
        return EnrichUseConditions(cls.playground)

    @classmethod
    def helper(cls):
        return SetupHelperBPS()

    def test_enrichment_maintained_illuminance_false(self):
        """Test if sim_setting to false leads to fixed lighting power"""
        self.playground.sim_settings.use_maintained_illuminance = False
        tz = self.helper.get_thermalzone(
            guid='ThermalZone001',
            usage='Office',
            gross_area=10)
        elements = {tz.guid: tz}
        answers = ()
        reads = (elements,)
        test_res = self.run_task(answers, reads)
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
        answers = ()
        reads = (elements,)
        test_res = self.run_task(answers, reads)
        self.assertEqual(tz.usage, 'Single office')
        self.assertEqual(tz.machines, 7.0 * ureg.watt / ureg.m ** 2)
        self.assertEqual(tz.use_maintained_illuminance, True)
        self.assertEqual(tz.lighting_power, 10 / 3 * ureg.watt / ureg.m ** 2)

    def test_enrichment_sim_setting_without_overwrite(self):
        """Tests enrichment of single office without overwrite via settings."""
        print(self.playground.sim_settings.heating_tz_overwrite)
        print(self.playground.sim_settings.cooling_tz_overwrite)
        print(self.playground.sim_settings.ahu_tz_overwrite)
        tz = self.helper.get_thermalzone(
            guid='ThermalZone001',
            usage='Office',
            gross_area=10)
        elements = {tz.guid: tz}
        answers = ()
        reads = (elements,)
        test_res = self.run_task(answers, reads)
        self.assertTrue(tz.with_heating)
        self.assertFalse(tz.with_cooling)
        self.assertFalse(tz.with_ahu)

    def test_enrichment_sim_setting_overwrite(self):
        """Tests enrichment of single office with overwrite via settings."""
        self.playground.sim_settings.heating_tz_overwrite = True
        self.playground.sim_settings.cooling_tz_overwrite = True
        self.playground.sim_settings.ahu_tz_overwrite = True

        tz = self.helper.get_thermalzone(
            guid='ThermalZone001',
            usage='Office',
            gross_area=10)
        elements = {tz.guid: tz}
        answers = ()
        reads = (elements,)
        test_res = self.run_task(answers, reads)
        self.assertTrue(tz.with_heating)
        self.assertTrue(tz.with_cooling)
        self.assertTrue(tz.with_ahu)

    def test_enrichment_sim_setting_overwrite_false(self):
        """Tests enrichment of single office with overwrite via settings."""
        self.playground.sim_settings.heating_tz_overwrite = False
        self.playground.sim_settings.cooling_tz_overwrite = False
        self.playground.sim_settings.ahu_tz_overwrite = False

        tz = self.helper.get_thermalzone(
            guid='ThermalZone001',
            usage='Office',
            gross_area=10)
        elements = {tz.guid: tz}
        answers = ()
        reads = (elements,)
        test_res = self.run_task(answers, reads)
        self.assertFalse(tz.with_heating)
        self.assertFalse(tz.with_cooling)
        self.assertFalse(tz.with_ahu)

    def test_bldg_ahu_enrichment(self):
        """Test if enrichment of AHU on tz level sets AHU on bldg level"""
        self.playground.sim_settings.ahu_tz_overwrite = True

        elements = self.helper.get_setup_simple_house()

        answers = ()
        reads = (elements,)
        test_res = self.run_task(answers, reads)
        bldg = elements['bldg001']
        tz = elements['tz001']
        self.assertTrue(tz.with_ahu)
        self.assertTrue(bldg.with_ahu)

    def test_bldg_ahu_enrichment_false(self):
        """Test if enrichment of AHU on tz level sets AHU on bldg level"""
        self.playground.sim_settings.ahu_tz_overwrite = False

        elements = self.helper.get_setup_simple_house()

        answers = ()
        reads = (elements,)
        test_res = self.run_task(answers, reads)
        bldg = elements['bldg001']
        tz = elements['tz001']
        self.assertFalse(tz.with_ahu)
        self.assertFalse(bldg.with_ahu)

    def test_bldg_ahu_enrichment_complete(self):
        """Test if enrichment of AHU on tz level sets AHU on bldg level"""
        self.playground.sim_settings.ahu_tz_overwrite = True
        self.playground.sim_settings.ahu_heating_overwrite = True
        self.playground.sim_settings.ahu_cooling_overwrite = True
        self.playground.sim_settings.ahu_dehumidification_overwrite = True
        self.playground.sim_settings.ahu_humidification_overwrite = True
        self.playground.sim_settings.ahu_heat_recovery_overwrite = True
        self.playground.sim_settings.ahu_heat_recovery_efficiency_overwrite = \
            0.8

        elements = self.helper.get_setup_simple_house()

        answers = ()
        reads = (elements,)
        test_res = self.run_task(answers, reads)
        bldg = elements['bldg001']
        tz = elements['tz001']
        self.assertTrue(tz.with_ahu)
        self.assertTrue(bldg.with_ahu)
        self.assertTrue(bldg.ahu_heating)
        self.assertTrue(bldg.ahu_cooling)
        self.assertTrue(bldg.ahu_dehumidification)
        self.assertTrue(bldg.ahu_humidification)
        self.assertTrue(bldg.ahu_heat_recovery)
        self.assertEqual(bldg.ahu_heat_recovery_efficiency, 0.8)

    def test_infiltration_sim_setting_overwrite(self):
        """Test if enrichment of infiltration on tz level works."""
        self.playground.sim_settings.use_constant_infiltration_overwrite = True
        self.playground.sim_settings.base_infiltration_rate_overwrite = 0.5

        elements = self.helper.get_setup_simple_house()

        answers = ()
        reads = (elements,)
        test_res = self.run_task(answers, reads)
        bldg = elements['bldg001']
        tz = elements['tz001']
        self.assertTrue(tz.use_constant_infiltration)
        self.assertEqual(tz.base_infiltration, 0.5)

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
        pattern_usage = get_pattern_usage(
            self.use_conditions, custom_use_conditions_path)
        found_usages = handler.handle(
            enrich_use_cond.EnrichUseConditions.enrich_usages(
                pattern_usage, tz_elements_dict))
        self.assertDictEqual(
            expected_usages,
            found_usages)
