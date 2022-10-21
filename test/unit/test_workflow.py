import unittest

from bim2sim import workflow
# todo #191

class TestWorkflow(unittest.TestCase):

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