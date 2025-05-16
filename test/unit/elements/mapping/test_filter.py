"""Testing StoreyFilter functionality on IFC elements"""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bim2sim.elements.mapping import ifc2python
from bim2sim.elements.mapping.filter import StoreyFilter, TypeFilter
from bim2sim.elements.base_elements import Material
from bim2sim.elements import bps_elements as bps_elements
from bim2sim.elements.mapping.ifc2python import (getSpatialChildren,
                                                 getHierarchicalChildren)
from bim2sim.tasks.common import CreateElementsOnIfcTypes

# Path to test file
IFC_PATH = (Path(__file__).parent.parent.parent.parent /
            'resources/arch/ifc/AC20-FZK-Haus.ifc')


class TestStoreyFilter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Loads the IFC file for all test cases"""
        cls.ifc = ifc2python.load_ifc(IFC_PATH)

    def setUp(self):
        """Called before each test case"""
        # Create mock objects for entity_type_dict and unknown
        self.entity_type_dict = {}
        self.unknown = []
        default_ifc_types = {'IfcBuildingElementProxy', 'IfcUnitaryEquipment'}
        relevant_elements = {*bps_elements.items, Material}
        relevant_ifc_types = CreateElementsOnIfcTypes.get_ifc_types(
            relevant_elements)
        relevant_ifc_types.update(default_ifc_types)

        # Get real storeys from the IFC file
        self.all_storeys = self.ifc.by_type('IfcBuildingStorey')

        # Create a new StoreyFilter object for each test
        # We assume that the first storey should be kept
        self.keep_guid = self.all_storeys[0].GlobalId
        self.filter = StoreyFilter([self.keep_guid])

        # Fill dictionaries with all storeys
        type_filter = TypeFilter(relevant_ifc_types)
        self.entity_type_dict, self.unknown = type_filter.run(
            self.ifc)

    def test_filter_initialization(self):
        """Test if the filter is initialized correctly"""
        self.assertEqual(self.filter.storey_guids, [self.keep_guid])

    def test_run_basic_functionality(self):
        """Test the basic filter functionality"""
        # Create a copy of the original dictionary keys and unknown list
        original_keys = set(self.entity_type_dict.keys())
        original_unknown = set(self.unknown)

        # Count original storeys in both dictionaries
        original_storeys_in_dict = sum(
            1 for k in original_keys if k in self.all_storeys)
        original_storeys_in_unknown = sum(
            1 for k in original_unknown if k in self.all_storeys)

        # Execute the filter with a fresh copy of the dictionaries
        working_dict = self.entity_type_dict.copy()
        working_unknown = self.unknown.copy()

        result_dict, result_unknown = self.filter.run(
            self.ifc, working_dict, working_unknown)

        # Check if only the storey to be kept remains in the result
        storey_keys = [k for k in result_dict.keys() if k in self.all_storeys]
        self.assertEqual(len(storey_keys), 1)
        self.assertEqual(storey_keys[0].GlobalId, self.keep_guid)

        # Check if the storey to be kept also remains in unknown (if it was
        # there)
        unknown_storeys = [s for s in result_unknown if s in self.all_storeys]
        if any(s.GlobalId == self.keep_guid for s in self.unknown):
            self.assertEqual(len(unknown_storeys), 1)
            self.assertEqual(unknown_storeys[0].GlobalId, self.keep_guid)
        else:
            self.assertEqual(len(unknown_storeys), 0)

        # Verify that some filtering actually occurred
        self.assertLess(len(result_dict), len(original_keys))

    def test_empty_guid_list(self):
        """Test with empty GUID list - no storeys should be removed"""
        empty_filter = StoreyFilter([])

        # Create a copy of the original dictionary keys and unknown list
        original_keys = set(self.entity_type_dict.keys())
        original_unknown = set(self.unknown)

        # Execute the filter with a fresh copy of the dictionaries
        working_dict = self.entity_type_dict.copy()
        working_unknown = self.unknown.copy()

        result_dict, result_unknown = empty_filter.run(
            self.ifc, working_dict, working_unknown)

        # Check if the counts match the original
        self.assertEqual(len(result_dict), len(original_keys))
        self.assertEqual(len(result_unknown), len(original_unknown))

        # Verify that all keys from the original dictionaries are present in
        # the results
        for key in original_keys:
            self.assertIn(key, result_dict)

        for item in original_unknown:
            self.assertIn(item, result_unknown)

    def test_keep_all_storeys(self):
        """Test where all storeys should be kept"""
        all_guids = [storey.GlobalId for storey in self.all_storeys]
        keep_all_filter = StoreyFilter(all_guids)

        # Create a copy of the original dictionary keys and unknown list
        original_keys = set(self.entity_type_dict.keys())
        original_unknown = set(self.unknown)

        # Execute the filter with a fresh copy of the dictionaries
        working_dict = self.entity_type_dict.copy()
        working_unknown = self.unknown.copy()

        result_dict, result_unknown = keep_all_filter.run(
            self.ifc, working_dict, working_unknown)

        # Check if the counts match the original
        self.assertEqual(len(result_dict), len(original_keys))
        self.assertEqual(len(result_unknown), len(original_unknown))

        # Verify that all keys from the original dictionaries are present in
        # the results
        for key in original_keys:
            self.assertIn(key, result_dict)

        for item in original_unknown:
            self.assertIn(item, result_unknown)

    def test_nonexistent_guid(self):
        """Test with a GUID that doesn't exist - no storeys should be
        removed"""
        non_existent_filter = StoreyFilter(["non_existent_guid"])

        # Create a copy of the original dictionary keys and unknown list
        original_keys = set(self.entity_type_dict.keys())
        original_unknown = set(self.unknown)

        # Execute the filter with a fresh copy of the dictionaries
        working_dict = self.entity_type_dict.copy()
        working_unknown = self.unknown.copy()

        result_dict, result_unknown = non_existent_filter.run(
            self.ifc, working_dict, working_unknown)

        # Check if the counts match the original
        self.assertEqual(len(result_dict), len(original_keys))
        self.assertEqual(len(result_unknown), len(original_unknown))

        # Verify that all keys from the original dictionaries are present in
        # the results
        for key in original_keys:
            self.assertIn(key, result_dict)

        for item in original_unknown:
            self.assertIn(item, result_unknown)

    def test_error_handling(self):
        """Test error handling"""
        # Create a copy of the original dictionary keys and unknown list
        original_keys = set(self.entity_type_dict.keys())
        original_unknown = set(self.unknown)

        # Count storeys to be kept
        kept_storey = next(
            s for s in self.all_storeys if s.GlobalId == self.keep_guid)
        has_kept_storey_in_dict = kept_storey in original_keys
        has_kept_storey_in_unknown = kept_storey in original_unknown

        # Execute the filter with a fresh copy of the dictionaries
        working_dict = self.entity_type_dict.copy()
        working_unknown = self.unknown.copy()

        # Create a mock for getSpatialChildren that throws an exception
        with (patch(
                'bim2sim.elements.mapping.ifc2python.getSpatialChildren') as
        mock_get_spatial):
            mock_get_spatial.side_effect = Exception("Test error")

            # The filter should catch the error and still function
            result_dict, result_unknown = self.filter.run(
                self.ifc, working_dict, working_unknown)

            # The storey to be kept should still be present
            if has_kept_storey_in_dict:
                self.assertIn(kept_storey, result_dict)
            if has_kept_storey_in_unknown:
                self.assertIn(kept_storey, result_unknown)


if __name__ == '__main__':
    unittest.main()
