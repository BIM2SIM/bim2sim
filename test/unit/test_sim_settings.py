import configparser
import unittest

from pathlib import Path

from bim2sim.utilities.types import LOD
from bim2sim import sim_settings
from test.unit.elements.helper import SetupHelper


class SimSettingsHelper(SetupHelper):
    def create_new_sim_setting(self):
        class NewSettings(sim_settings.BaseSimSettings):
            def __init__(self):
                super().__init__(
                )
            new_setting_lod = sim_settings.ChoiceSetting(
                default=LOD.low,
                choices={
                    LOD.low: 'not so detailed setting',
                    LOD.full: 'awesome detailed setting'
                },
                description='A new sim_settings lod setting to be created.',
                for_frontend=True
            )
            new_setting_bool = sim_settings.BooleanSetting(
                default=False,
                description='A new sim_settings bool setting to be created.',
                for_frontend=True
            )
            new_setting_str = sim_settings.ChoiceSetting(
                default='Perfect',
                choices={
                    'Perfect': 'A perfect setting',
                    'Awesome': 'An awesome setting'
                },
                description='A new sim_settings str setting to be created.',
                for_frontend=True
            )
            new_setting_list = sim_settings.ChoiceSetting(
                default=[
                    'a', 'b', 'c'],
                choices={
                    'a': 'option a',
                    'b': 'option b',
                    'c': 'option c'
                },
                description='A new sim_settings list setting to be created.',
                multiple_choice=True,
                for_frontend=True
            )
            new_setting_path = sim_settings.PathSetting(
                default=Path(__file__),
                description='Setting to get a path.'
            )

        # instantiate the new wf
        new_wf = NewSettings()
        return new_wf


class TestSimSettings(unittest.TestCase):
    helper = SimSettingsHelper()

    def tearDown(self):
        self.helper.reset()

    def test_default_settings(self):
        """Test loading of default settings"""
        standard_wf = sim_settings.BaseSimSettings()
        self.assertFalse(standard_wf.dymola_simulation)
        self.assertFalse(standard_wf.create_external_elements)

    def test_update_from_config(self):
        """Test loading sim_settings settings from config"""
        new_wf = self.helper.create_new_sim_setting()
        self.assertEqual(
            new_wf.new_setting_lod, LOD.low)
        self.assertFalse(new_wf.new_setting_bool)
        self.assertEqual(new_wf.new_setting_str, 'Perfect')
        config = configparser.ConfigParser(allow_no_value=True)
        config.add_section('NewSettings')
        # set full LOD (3) for new setting in config
        config['NewSettings']['new_setting_lod'] = 'LOD.full'
        config['NewSettings']['new_setting_bool'] = 'True'
        config['NewSettings']['new_setting_str'] = 'Awesome'
        config['NewSettings']['new_setting_list'] = '["a","b","c"]'
        config['NewSettings']['new_setting_path'] = str(Path(__file__).parent)
        new_wf.update_from_config(config)
        self.assertEqual(
            new_wf.new_setting_lod, LOD.full)
        self.assertTrue(new_wf.new_setting_bool)
        self.assertEqual(new_wf.new_setting_str, 'Awesome')
        self.assertEqual(new_wf.new_setting_list, ['a', 'b', 'c'])
        self.assertEqual(new_wf.new_setting_path, Path(__file__).parent)

    def test_LOD(self):
        """Test setting and getting the different LODs"""
        set_detail = LOD.low
        self.assertEqual(set_detail, LOD.low)
        set_detail = LOD(1)
        self.assertEqual(set_detail, LOD.low)
        set_detail = LOD.medium
        self.assertEqual(set_detail, LOD.medium)
        set_detail = LOD(2)
        self.assertEqual(set_detail, LOD.medium)
        set_detail = LOD.full
        self.assertEqual(set_detail, LOD.full)
        set_detail = LOD(3)
        self.assertEqual(set_detail, LOD.full)

    def test_auto_name_setting(self):
        """Test if name is correctly set by meta class AutoSettingNameMeta"""
        new_wf = self.helper.create_new_sim_setting()
        # get attribute by name
        new_setting = getattr(new_wf, 'new_setting_lod')
        self.assertEqual(new_setting, LOD.low)

    def test_new_sim_settings_creation(self):
        """Test if the creation of new sim settings work"""
        new_sim_setting = self.helper.create_new_sim_setting()
        # test default
        self.assertEqual(
            new_sim_setting.new_setting_lod, LOD.low)
        # test description
        self.assertEqual(
            new_sim_setting.manager['new_setting_lod'].description,
            'A new sim_settings lod setting to be created.')
        # test set new value
        new_sim_setting.new_setting_lod = LOD.full
        self.assertEqual(
            new_sim_setting.new_setting_lod, LOD.full)
