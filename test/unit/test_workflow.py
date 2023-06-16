import configparser
import unittest

import bim2sim.utilities.types
from bim2sim import simulation_settings
from test.unit.kernel.helper import SetupHelper


class simulation_typeHelper(SetupHelper):
    def create_new_wf(self):
        class NewWF(simulation_type.SimSettings):
            def __init__(self):
                super().__init__(
                )
            new_wf_setting_lod = simulation_type.Setting(
                default=bim2sim.utilities.types.LOD.low,
                choices={
                    bim2sim.utilities.types.LOD.low: 'not so detailed setting',
                    bim2sim.utilities.types.LOD.full: 'awesome detailed setting'
                },
                description='A new simulation_type lod setting to be created.',
                for_frontend=True
            )
            new_wf_setting_bool = simulation_type.Setting(
                default=False,
                choices={
                    False: 'Nope',
                    True: 'Yes'
                },
                description='A new simulation_type bool setting to be created.',
                for_frontend=True
            )
            new_wf_setting_str = simulation_type.Setting(
                default='Perfect',
                choices={
                    'Perfect': 'A perfect setting',
                    'Awesome': 'An awesome setting'
                },
                description='A new simulation_type str setting to be created.',
                for_frontend=True
            )
            new_wf_setting_list = simulation_type.Setting(
                default=[
                    'a', 'b', 'c'],
                choices={
                    'a': 'option a',
                    'b': 'option b',
                    'c': 'option c'
                },
                description='A new simulation_type list setting to be created.',
                multiple_choice=True,
                for_frontend=True
            )

        # instantiate the new wf
        new_wf = NewWF()
        return new_wf


class Testsimulation_type(unittest.TestCase):
    helper = simulation_typeHelper()

    def tearDown(self):
        self.helper.reset()

    def test_default_settings(self):
        """Test loading of default settings"""
        standard_wf = simulation_type.SimSettings()
        self.assertFalse(standard_wf.dymola_simulation)
        self.assertFalse(standard_wf.create_external_elements)

    def test_update_from_config(self):
        """Test loading simulation_type settings from config"""
        new_wf = self.helper.create_new_wf()
        self.assertEqual(new_wf.new_wf_setting_lod, bim2sim.utilities.types.LOD.low)
        self.assertFalse(new_wf.new_wf_setting_bool)
        self.assertEqual(new_wf.new_wf_setting_str, 'Perfect')
        config = configparser.ConfigParser(allow_no_value=True)
        config.add_section('NewWF')
        # set full LOD (3) for new setting in config
        config['NewWF']['new_wf_setting_lod'] = '3'
        config['NewWF']['new_wf_setting_bool'] = 'True'
        config['NewWF']['new_wf_setting_str'] = 'Awesome'
        config['NewWF']['new_wf_setting_list'] = '["a","b","c"]'
        new_wf.update_from_config(config)
        self.assertEqual(new_wf.new_wf_setting_lod, bim2sim.utilities.types.LOD.full)
        self.assertTrue(new_wf.new_wf_setting_bool)
        self.assertEqual(new_wf.new_wf_setting_str, 'Awesome')
        self.assertEqual(new_wf.new_wf_setting_list, ['a', 'b', 'c'])

    def test_LOD(self):
        """Test setting and getting the different LODs"""
        set_detail = bim2sim.utilities.types.LOD.low
        self.assertEqual(set_detail, bim2sim.utilities.types.LOD.low)
        set_detail = bim2sim.utilities.types.LOD(1)
        self.assertEqual(set_detail, bim2sim.utilities.types.LOD.low)
        set_detail = bim2sim.utilities.types.LOD.medium
        self.assertEqual(set_detail, bim2sim.utilities.types.LOD.medium)
        set_detail = bim2sim.utilities.types.LOD(2)
        self.assertEqual(set_detail, bim2sim.utilities.types.LOD.medium)
        set_detail = bim2sim.utilities.types.LOD.full
        self.assertEqual(set_detail, bim2sim.utilities.types.LOD.full)
        set_detail = bim2sim.utilities.types.LOD(3)
        self.assertEqual(set_detail, bim2sim.utilities.types.LOD.full)

    def test_auto_name_setting(self):
        """Test if name is correctly set by meta class AutoSettingNameMeta"""
        new_wf = self.helper.create_new_wf()
        # get attribute by name
        new_wf_setting = getattr(new_wf, 'new_wf_setting_lod')
        self.assertEqual(new_wf_setting, bim2sim.utilities.types.LOD.low)

    def test_new_simulation_type_creation(self):
        """Test if the creation of new simulation_type and settings work"""
        new_wf = self.helper.create_new_wf()
        # test default
        self.assertEqual(new_wf.new_wf_setting_lod, bim2sim.utilities.types.LOD.low)
        # test description
        self.assertEqual(
            new_wf.manager['new_wf_setting_lod'].description,
            'A new simulation_type lod setting to be created.')
        # test set new value
        new_wf.new_wf_setting_lod = bim2sim.utilities.types.LOD.full
        self.assertEqual(new_wf.new_wf_setting_lod, bim2sim.utilities.types.LOD.full)
