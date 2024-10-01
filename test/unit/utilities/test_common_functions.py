"""Test for common_functions.py"""
import re
import unittest
from pathlib import Path

import bim2sim.utilities.common_functions as cf
from bim2sim.elements.bps_elements import BPSProduct, Wall, Window, Door
import bim2sim.elements.aggregation.bps_aggregations


class TestCommonFunctions(unittest.TestCase):
    """General common functions reltead tests"""

    def test_angle_equivalent(self):
        """test angle_equivalent function"""
        input_angles = [0, 180, 360, -180, -360]
        expected_angles = [0, 180, 0, 180, 0]
        output_angles = []
        for input_angle in input_angles:
            output_angles.append(cf.angle_equivalent(input_angle))
        self.assertEqual(expected_angles, output_angles,)

    def test_vector_angle(self):
        """test vector_angle function"""
        input_vectors = [[1, 0], [0, 1], [1, 1], [-1, 1], [1, -1], [-1, -1]]
        expected_angles = [90, 0.0, 45.0, 315.0, 135.0, 225.0]
        output_angles = []
        for input_vector in input_vectors:
            output_angles.append(cf.vector_angle(input_vector))
        self.assertEqual(expected_angles, output_angles,)

    def test_get_usage_dict(self):
        """test get_use_conditions_dict function (perform test for 4 samples)"""
        use_conditions_dh_path = Path(bim2sim.__file__).parent.parent / \
                             'test/resources/arch/custom_usages/' \
                             'UseConditionsFM_ARC_DigitalHub_fixed002.json'
        use_conditions_dict = cf.get_use_conditions_dict(use_conditions_dh_path)
        self.assertIsInstance(use_conditions_dict, dict)
        expected_heating_profile = [
            291.15, 291.15, 291.15, 291.15, 291.15, 294.15, 294.15, 294.15,
            294.15, 294.15, 294.15, 294.15, 294.15, 294.15, 294.15, 294.15,
            294.15, 294.15, 294.15, 294.15, 294.15, 291.15, 291.15, 291.15]
        expected_cooling_profile = [
            309.15, 309.15, 309.15, 309.15, 309.15, 299.15, 299.15, 299.15,
            299.15, 299.15, 299.15, 299.15, 299.15, 299.15, 299.15, 299.15,
            299.15, 299.15, 299.15, 299.15, 299.15, 309.15, 309.15, 309.15]
        self.assertEqual(
            use_conditions_dict[
                'Group Office (between 2 and 6 employees)']['heating_profile'],
            expected_heating_profile)
        self.assertEqual(
            use_conditions_dict[
                'Group Office (between 2 and 6 employees)']['cooling_profile'],
            expected_cooling_profile)

    def test_get_common_pattern_usage(self):
        """test get_common_pattern_usage function (perform test for three
        samples)"""
        usage_dict = cf.get_common_pattern_usage()
        self.assertIsInstance(usage_dict, dict)
        self.assertEqual(
            usage_dict['Auxiliary areas (without common rooms)'], ['Nebenrau'])
        self.assertEqual(
            usage_dict['Canteen'], ["Kantine", "Cafeteria"])
        self.assertEqual(
            usage_dict['Classroom'], ["Klassenzimmer"])

    def test_get_custom_pattern_usage(self):
        """test get_custom_pattern_usage function (perform test for two
        samples)"""
        usage_dict_dh_path = Path(bim2sim.__file__).parent.parent / \
                             'test/resources/arch/custom_usages/' \
                             'customUsagesFM_ARC_DigitalHub_fixed002.json'
        usage_dict = cf.get_custom_pattern_usage(usage_dict_dh_path)

        self.assertIsInstance(usage_dict, dict)
        self.assertEqual(
            usage_dict['Group Office (between 2 and 6 employees)'][0],
            'Space_13')
        self.assertEqual(
            usage_dict[
                'Stock, technical equipment, archives'][0], 'Aufzug West 300')

    def test_get_custom_pattern_usage_2(self):
        """test get_custom_pattern_usage function (perform test for two
         samples)"""
        use_conditions_dh_path = Path(bim2sim.__file__).parent.parent / \
                             'test/resources/arch/custom_usages/' \
                             'UseConditionsFM_ARC_DigitalHub_fixed002.json'
        use_conditions_dict = cf.get_use_conditions_dict(use_conditions_dh_path)
        usage_dict_dh_path = Path(bim2sim.__file__).parent.parent / \
                             'test/resources/arch/custom_usages/' \
                             'customUsagesFM_ARC_DigitalHub_fixed002.json'

        pattern_usage = cf.get_pattern_usage(
            use_conditions_dict, usage_dict_dh_path)
        self.assertEqual(
            pattern_usage['Group Office (between 2 and 6 employees)']['common'],
            [re.compile('(.*?)Group(.*?)Office(.*?)', re.IGNORECASE),
             re.compile('(.*?)Gruppen Buero', re.IGNORECASE)]
        )
        self.assertEqual(
            pattern_usage[
                'Group Office (between 2 and 6 employees)']['custom'][0],
            'Space_13')

    def test_get_type_building_elements(self):
        """test get_type_building_elements function (perform test for 1
        sample)"""
        type_building_elements = cf.get_type_building_elements(data_file="TypeElements_IWU.json")
        self.assertIsInstance(type_building_elements, dict)
        self.assertEqual(
            type_building_elements['OuterWall']['[0, 1918]']['iwu_heavy']['layer']['0']['thickness'], 0.015)

    def test_get_material_templates(self):
        """test get_material_templates function (perform test for 1
        sample)"""
        material_templates = cf.get_material_templates()
        self.assertIsInstance(material_templates, dict)
        self.assertEqual(
            material_templates[
                '245ce424-3a43-11e7-8714-2cd444b2e704']['heat_capac'], 0.84)

    def test_filter_elements(self):
        """test filter_elements function"""
        wall_1 = Wall()
        wall_2 = Wall()
        window_1 = Window()
        window_2 = Window()
        door_1 = Door()
        door_2 = Door()
        elements = [wall_1, wall_2, window_1, window_2, door_1, door_2]
        filtered_elements = cf.filter_elements(elements, 'Wall')
        expected_elements = [wall_1, wall_2]
        self.assertIsInstance(elements, list)
        self.assertEqual(filtered_elements, expected_elements)

    def test_remove_umlaut(self):
        """test remove_umlaut function"""
        input_string = 'äöü'
        expected_string = 'aeoeue'
        output_string = cf.remove_umlaut(input_string)
        self.assertEqual(output_string, expected_string)

    def test_translate_deep(self):
        """test translate_deep function"""
        input_texts = ['cheese', 'tomatoes', 'potatoes']
        translated = []
        expected_translations = ['käse', 'tomaten', 'kartoffeln']
        for input_text in input_texts:
            translated.append(
                cf.translate_deep(input_text, target='de').lower())
        self.assertEqual(translated, expected_translations)

    def test_all_subclasses(self):
        """test all_subclasses function"""
        all_subclasses = cf.all_subclasses(BPSProduct)
        self.assertIsInstance(all_subclasses, set)
        self.assertEqual(len(all_subclasses), 29)

    def test_download_test_files_arch(self):
        testmodels_path = Path(__file__).parent.parent.parent / \
                          'resources/arch'
        # delete if already exists
        if testmodels_path.exists():
            cf.rm_tree(testmodels_path)
        cf.download_test_resources('arch', with_regression=True)
        ifc_path = testmodels_path / 'ifc'
        usages_path = testmodels_path / 'custom_usages'
        regression_path = testmodels_path / 'regression_results'
        for path in [ifc_path, usages_path, regression_path]:
            if not path.exists():
                raise AssertionError(
                    f"Path does not exist: {path}, download of "
                    f"architecture IFC files didn't work.")

    def test_download_test_files_hydraulic(self):
        testmodels_path = Path(__file__).parent.parent.parent / \
                          'resources/hydraulic'
        # delete if already exists
        if testmodels_path.exists():
            cf.rm_tree(testmodels_path)
        cf.download_test_resources('hydraulic', with_regression=True)
        ifc_path = testmodels_path / 'ifc'
        regression_path = testmodels_path / 'regression_results'
        for path in [ifc_path, regression_path]:
            if not path.exists():
                raise AssertionError(
                    f"Path does not exist: {path}, download of "
                    f"hydraulic IFC files didn't work.")

    def test_download_test_files_mixed(self):
        testmodels_path = Path(__file__).parent.parent.parent / \
                          'resources/mixed'
        # delete if already exists
        if testmodels_path.exists():
            cf.rm_tree(testmodels_path)
        cf.download_test_resources('mixed', with_regression=False)
        ifc_path = testmodels_path / 'ifc'
        # TODO #1 include regression results for mixed  when they exist
        regression_path = testmodels_path / 'regression_results'
        for path in [ifc_path]:
            if not path.exists():
                raise AssertionError(
                    f"Path does not exist: {path}, download of "
                    f"mixed IFC files didn't work.")
