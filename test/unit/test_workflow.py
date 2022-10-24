import unittest
from test.unit.kernel.helper import SetupHelper

from bim2sim import workflow
# todo #191


class WorkflowHelper(SetupHelper):
    def create_new_wf(self):
        class NewWF(workflow.Workflow):
            def __init__(self):
                super().__init__(
                )
            new_wf_setting = workflow.WorkflowSetting(
                default=workflow.LOD.low,
                choices={
                    workflow.LOD.low: 'not so detailed setting',
                    workflow.LOD.full: 'awesome detailed setting'
                },
                description='A new workflow setting to be created.',
                for_frontend=True
            )

        # instantiate the new wf
        new_wf = NewWF()
        return new_wf


class TestWorkflow(unittest.TestCase):
    helper = WorkflowHelper()

    def tearDown(self):
        self.helper.reset()

    def test_building_simulation_settings(self):
        """Test creation of workflow"""
        # todo
        bs_workflow = workflow.BuildingSimulation()
        self.assertTrue(
            isinstance(bs_workflow.layers_and_materials, workflow.LOD))
        self.assertTrue(
            isinstance(bs_workflow.zoning_setup, workflow.LOD))
        self.assertTrue(
            isinstance(bs_workflow.construction_class_walls, workflow.LOD))
        pass

    def test_additional_settings(self):
        pass

    def test_default_settings(self):
        """Test loading of default settings"""
        pass

    def test_update_from_config(self):
        pass

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
        new_wf_setting = getattr(new_wf, 'new_wf_setting')
        self.assertEqual(new_wf_setting, workflow.LOD.low)

    def test_settings_manager(self):
        pass

    def test_new_workflow_creation(self):
        new_wf = self.helper.create_new_wf()
        # test default
        self.assertEqual(new_wf.new_wf_setting, workflow.LOD.low)
        # test description
        self.assertEqual(
            new_wf.manager['new_wf_setting'].description,
            'A new workflow setting to be created.')
        # test set new value
        new_wf.new_wf_setting = workflow.LOD.full
        self.assertEqual(new_wf.new_wf_setting, workflow.LOD.full)
