import configparser
import unittest

from test.unit.kernel.helper import SetupHelper
from bim2sim import workflow


class WorkflowHelper(SetupHelper):
    def create_new_wf(self):
        class NewWF(workflow.Workflow):
            def __init__(self):
                super().__init__(
                )
            new_wf_setting_lod = workflow.WorkflowSetting(
                default=workflow.LOD.low,
                choices={
                    workflow.LOD.low: 'not so detailed setting',
                    workflow.LOD.full: 'awesome detailed setting'
                },
                description='A new workflow lod setting to be created.',
                for_frontend=True
            )
            new_wf_setting_bool = workflow.WorkflowSetting(
                default=False,
                choices={
                    False: 'Nope',
                    True: 'Yes'
                },
                description='A new workflow bool setting to be created.',
                for_frontend=True
            )
            new_wf_setting_str = workflow.WorkflowSetting(
                default='Perfect',
                choices={
                    'Perfect': 'A perfect setting',
                    'Awesome': 'An awesome setting'
                },
                description='A new workflow str setting to be created.',
                for_frontend=True
            )
            new_wf_setting_list = workflow.WorkflowSetting(
                default=[
                    'a', 'b', 'c'],
                choices={
                    'a': 'option a',
                    'b': 'option b',
                    'c': 'option c'
                },
                description='A new workflow list setting to be created.',
                multiple_choice=True,
                for_frontend=True
            )

        # instantiate the new wf
        new_wf = NewWF()
        return new_wf


class TestWorkflow(unittest.TestCase):
    helper = WorkflowHelper()

    def tearDown(self):
        self.helper.reset()

    def test_default_settings(self):
        """Test loading of default settings"""
        standard_wf = workflow.Workflow()
        self.assertFalse(standard_wf.dymola_simulation)
        self.assertFalse(standard_wf.create_external_elements)

    def test_update_from_config(self):
        """Test loading workflow settings from config"""
        new_wf = self.helper.create_new_wf()
        self.assertEqual(new_wf.new_wf_setting_lod, workflow.LOD.low)
        self.assertFalse(new_wf.new_wf_setting_bool)
        self.assertEqual(new_wf.new_wf_setting_str, 'Perfect')
        config = configparser.ConfigParser(allow_no_value=True)
        config.add_section('NewWF')
        # set full LOD (3) for new setting in config
        config['NewWF']['new_wf_setting_lod'] = '3'
        config['NewWF']['new_wf_setting_bool'] = 'True'
        config['NewWF']['new_wf_setting_str'] = 'Awesome'
        config['NewWF']['new_wf_setting_list'] = '["a","b","c"]'
        new_wf.update_from_conf(config)
        self.assertEqual(new_wf.new_wf_setting_lod, workflow.LOD.full)
        self.assertTrue(new_wf.new_wf_setting_bool)
        self.assertEqual(new_wf.new_wf_setting_str, 'Awesome')
        self.assertEqual(new_wf.new_wf_setting_list, ['a', 'b', 'c'])

    def test_LOD(self):
        """Test setting and getting the different LODs"""
        set_detail = workflow.LOD.low
        self.assertEqual(set_detail, workflow.LOD.low)
        set_detail = workflow.LOD(1)
        self.assertEqual(set_detail, workflow.LOD.low)
        set_detail = workflow.LOD.medium
        self.assertEqual(set_detail, workflow.LOD.medium)
        set_detail = workflow.LOD(2)
        self.assertEqual(set_detail, workflow.LOD.medium)
        set_detail = workflow.LOD.full
        self.assertEqual(set_detail, workflow.LOD.full)
        set_detail = workflow.LOD(3)
        self.assertEqual(set_detail, workflow.LOD.full)

    def test_auto_name_setting(self):
        """Test if name is correctly set by meta class AutoSettingNameMeta"""
        new_wf = self.helper.create_new_wf()
        # get attribute by name
        new_wf_setting = getattr(new_wf, 'new_wf_setting_lod')
        self.assertEqual(new_wf_setting, workflow.LOD.low)

    def test_new_workflow_creation(self):
        """Test if the creation of new workflow and settings work"""
        new_wf = self.helper.create_new_wf()
        # test default
        self.assertEqual(new_wf.new_wf_setting_lod, workflow.LOD.low)
        # test description
        self.assertEqual(
            new_wf.manager['new_wf_setting_lod'].description,
            'A new workflow lod setting to be created.')
        # test set new value
        new_wf.new_wf_setting_lod = workflow.LOD.full
        self.assertEqual(new_wf.new_wf_setting_lod, workflow.LOD.full)
