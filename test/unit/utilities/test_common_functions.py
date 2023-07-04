"""Test for common_functions.py"""
import re
import unittest
from pathlib import Path

import bim2sim.utilities.common_functions as cf
from bim2sim.elements.bps_elements import BPSProduct, Wall, Window, Door


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
        """test get_usage_dict function (perform test for 4 samples)"""
        prj_name = 'FM_ARC_DigitalHub_fixed002'
        usage_dict = cf.get_usage_dict(prj_name)
        self.assertIsInstance(usage_dict, dict)
        expected_heating_profile = [
            291.15, 291.15, 291.15, 291.15, 291.15, 294.15, 294.15, 294.15,
            294.15, 294.15, 294.15, 294.15, 294.15, 294.15, 294.15, 294.15,
            294.15, 294.15, 294.15, 294.15, 294.15, 291.15, 291.15, 291.15]
        expected_cooling_profile = [
            309.15, 309.15, 309.15, 309.15, 309.15, 299.15, 299.15, 299.15,
            299.15, 299.15, 299.15, 299.15, 299.15, 299.15, 299.15, 299.15,
            299.15, 299.15, 299.15, 299.15, 299.15, 309.15, 309.15, 309.15]
        self.assertEqual(
            usage_dict[
                'Group Office (between 2 and 6 employees)']['heating_profile'],
            expected_heating_profile)
        self.assertEqual(
            usage_dict[
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
        prj_name = 'FM_ARC_DigitalHub_fixed002'
        usage_dict = cf.get_custom_pattern_usage(prj_name)

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
        prj_name = 'FM_ARC_DigitalHub_fixed002'
        pattern_usage = cf.get_pattern_usage(prj_name)
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
        type_building_elements = cf.get_type_building_elements()
        self.assertIsInstance(type_building_elements, dict)
        self.assertEqual(
            type_building_elements['OuterWall']['[0, 1918]']['heavy']['layer']['0']['thickness'], 0.015)

    def test_get_material_templates(self):
        """test get_material_templates function (perform test for 1
        sample)"""
        material_templates = cf.get_material_templates()
        self.assertIsInstance(material_templates, dict)
        self.assertEqual(
            material_templates[
                '245ce424-3a43-11e7-8714-2cd444b2e704']['heat_capac'], 0.84)

    def test_filter_instances(self):
        """test filter_instances function"""
        wall_1 = Wall()
        wall_2 = Wall()
        window_1 = Window()
        window_2 = Window()
        door_1 = Door()
        door_2 = Door()
        instances = [wall_1, wall_2, window_1, window_2, door_1, door_2]
        filtered_instances = cf.filter_instances(instances, 'Wall')
        expected_instances = [wall_1, wall_2]
        self.assertIsInstance(instances, list)
        self.assertEqual(filtered_instances, expected_instances)

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
        self.assertEqual(len(all_subclasses), 24)

    def test_download_test_files_arch(self):
        testmodels_path = Path(__file__).parent.parent.parent / 'TestModels' / \
                          'BPS'
        # delete if already exists
        if testmodels_path.exists():
            cf.rm_tree(testmodels_path)
        cf.download_test_models('arch')
        if not testmodels_path.exists():
            raise AssertionError(
                f"Path does not exist: {testmodels_path}, download of "
                f"architecture IFC files didn't work.")

    def test_download_test_files_hydraulic(self):
        testmodels_path = Path(__file__).parent.parent.parent / 'TestModels' / \
                          'HVAC'
        if testmodels_path.exists():
            cf.rm_tree(testmodels_path)
        cf.download_test_models('hydraulic')
        if not testmodels_path.exists():
            raise AssertionError(
                f"Path does not exist: {testmodels_path}, download of "
                f"architecture IFC files didn't work.")
