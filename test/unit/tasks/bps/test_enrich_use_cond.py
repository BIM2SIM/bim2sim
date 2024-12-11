import tempfile
import unittest
from unittest import mock

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.sim_settings import BuildingSimSettings
from bim2sim.tasks.bps import EnrichUseConditions
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
            usage='Office',
            gross_area=10)
        elements = {tz.guid: tz}
        test_res = DebugDecisionHandler(()).handle(
            self.enrich_task.run(elements, ))
        self.assertEqual(tz.lighting_power, tz.fixed_lighting_power)
        self.assertEqual(tz.lighting_power, 15.9 * ureg.watt/ureg.m**2)

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
        self.assertEqual(tz.machines, 7.0 * ureg.watt/ureg.m**2)
        self.assertEqual(tz.use_maintained_illuminance, True)
        self.assertEqual(tz.lighting_power, 10 / 3 * ureg.watt/ureg.m**2)
