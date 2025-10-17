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
                value=LOD.low,
                choices={
                    LOD.low: 'not so detailed setting',
                    LOD.full: 'awesome detailed setting'
                },
                description='A new sim_settings lod setting to be created.',
                for_frontend=True
            )
            new_setting_bool = sim_settings.BooleanSetting(
                value=False,
                description='A new sim_settings bool setting to be created.',
                for_frontend=True
            )
            new_setting_str = sim_settings.ChoiceSetting(
                value='Perfect',
                choices={
                    'Perfect': 'A perfect setting',
                    'Awesome': 'An awesome setting'
                },
                description='A new sim_settings str setting to be created.',
                for_frontend=True
            )
            new_setting_list = sim_settings.ChoiceSetting(
                value=[
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
                value=Path(__file__),
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

    def test_guid_list_setting(self):
        """Test the GuidListSetting class for handling IFC GUIDs"""

        # Create a test settings class with GuidListSetting
        class TestGuidSettings(sim_settings.BaseSimSettings):
            def __init__(self):
                super().__init__()

            guid_list = sim_settings.GuidListSetting(
                value=['0rB_VAJfDAowPYhJGd9wjZ', '3V8lRtj8n5AxfePCnKtF31'],
                description='Test GUID list setting',
                for_frontend=True
            )

            empty_guid_list = sim_settings.GuidListSetting(
                description='Test empty GUID list setting',
                for_frontend=True
            )

            mandatory_guid_list = sim_settings.GuidListSetting(
                description='Test mandatory GUID list setting',
                mandatory=True
            )

        # Create settings instance
        test_settings = TestGuidSettings()

        # Test default values are correctly set
        self.assertEqual(
            test_settings.guid_list,
            ['0rB_VAJfDAowPYhJGd9wjZ', '3V8lRtj8n5AxfePCnKtF31']
        )
        dings = test_settings.empty_guid_list

        self.assertEqual(test_settings.empty_guid_list, None)

        # Test valid GUID updates
        valid_guids = ['1HBLcH3L5AgRg8QXUjHQ2T', '2MBmFkSRv59wfBR9XN_dIe']
        test_settings.guid_list = valid_guids
        self.assertEqual(test_settings.guid_list, valid_guids)

        # Test empty list
        test_settings.guid_list = []
        self.assertEqual(test_settings.guid_list, [])

        # Test None value
        test_settings.guid_list = None
        self.assertIsNone(test_settings.guid_list)

        # Test invalid inputs - should raise ValueError
        with self.assertRaises(ValueError):
            test_settings.guid_list = "not_a_list"

        with self.assertRaises(ValueError):
            test_settings.guid_list = [123, 456]  # Not strings

        with self.assertRaises(ValueError):
            test_settings.guid_list = [
                "invalid_guid_format"]  # Invalid GUID format

        with self.assertRaises(ValueError):
            test_settings.guid_list = ["0rB_VAJfDAowPYhJGd9wjZ", "invalid_guid"]

        # Test config update
        config = configparser.ConfigParser(allow_no_value=True)
        config.add_section('TestGuidSettings')
        config['TestGuidSettings'][
            'guid_list'] = '["3V8lRtj8n5AxfePCnKtF31", "0rB_VAJfDAowPYhJGd9wjZ"]'
        test_settings.update_from_config(config)
        self.assertEqual(
            test_settings.guid_list,
            ['3V8lRtj8n5AxfePCnKtF31', '0rB_VAJfDAowPYhJGd9wjZ']
        )

        # Test mandatory setting check
        with self.assertRaises(ValueError):
            test_settings.check_mandatory()

    def test_stories_to_load_guids(self):
        """Test the stories_to_load_guids setting in BaseSimSettings"""
        settings = sim_settings.BaseSimSettings()

        # Test default value
        self.assertEqual(settings.stories_to_load_guids, [])

        # Test valid update
        valid_guids = ['0rB_VAJfDAowPYhJGd9wjZ', '3V8lRtj8n5AxfePCnKtF31']
        settings.stories_to_load_guids = valid_guids
        self.assertEqual(settings.stories_to_load_guids, valid_guids)

        # Create a config that matches the exact format used in Project.config
        config = configparser.ConfigParser(allow_no_value=True)
        config.add_section(
            'BaseSimSettings')  # Use the actual class name, not "Generic Simulation Settings"
        config['BaseSimSettings'][
            'stories_to_load_guids'] = '["1HBLcH3L5AgRg8QXUjHQ2T"]'

        # Update settings from config
        settings.update_from_config(config)

        # Test the value was updated
        self.assertEqual(settings.stories_to_load_guids,
                         ['1HBLcH3L5AgRg8QXUjHQ2T'])
