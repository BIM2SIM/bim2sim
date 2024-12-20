import json
import logging
import re
import unittest
from pathlib import Path

import bim2sim
from bim2sim.kernel.decision.console import ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import LOD, IFCDomain, ZoningCriteria

logger = logging.getLogger(__name__)


class IntegrationBaseTEASER(IntegrationBase):
    def model_domain_path(self) -> str:
        return 'arch'

    def compare_serialized_teaser_models(self):
        """Compares two serialized TEASER model JSON files & logs their diffs.

        This function compares a reference TEASER model JSON file with a newly
         generated one. It creates a detailed log file of any differences
         found while ignoring variations in DisAgg_ naming conventions.

        Returns:
            bool or None: Returns True if files are equivalent
             (ignoring DisAgg_ names),
                False if differences are found, None if reference file 
                doesn't exist.

        The log file is created at self.project.paths.log /
        'serialized_teaser_compare.log'
        """
        ref_serialized_teaser_json = (
                Path(bim2sim.__file__).parent.parent /
                "test/resources/arch/model_compare" /
                f"{self._testMethodName}.json")
        if not ref_serialized_teaser_json.exists():
            logger.error(
                f"No Serialized .json fiels to compare TEASER models found in"
                f" {ref_serialized_teaser_json}.")
            test_result = None
        else:
            new_serialized_teaser_json = (
                    self.project.paths.export / "TEASER/serialized_teaser" /
                    f"{self.project.name}.json")
            test_result, diff_log = self.compare_json_files(
                ref_serialized_teaser_json,
                new_serialized_teaser_json)

            # Write differences to log file
            log_path = self.project.paths.log / 'serialized_teaser_compare.log'
            with open(log_path, 'w') as f:
                f.write(f"Comparison between:\n")
                f.write(f"Reference file: {ref_serialized_teaser_json}\n")
                f.write(f"New file: {new_serialized_teaser_json}\n\n")
                if diff_log:
                    f.write("Differences found:\n")
                    f.write(diff_log)
                    msg = (
                        f"Exported TEASER model has deviations with validated"
                        f" existing exports. Please check the error log under "
                        f"{self.project.paths.log / 'serialized_teaser_compare.log'}"
                        f" for further information.")
                else:
                    f.write("No differences found (ignoring DisAgg_ naming "
                            "variations)")
                    msg = ''

        return test_result, msg

    def compare_json_files(self, file_path1, file_path2):
        """Compares two JSON files while ignoring DisAgg_ naming differences.

        Args:
            file_path1 (Path or str): Path to the reference JSON file.
            file_path2 (Path or str): Path to the comparison JSON file.

        Returns:
            tuple: A tuple containing:
                - bool: True if files are equivalent (ignoring DisAgg_ names),
                False otherwise
                - str: A detailed log of all differences found,
                empty if files are equivalent
        """
        # Read JSON files
        with open(file_path1, 'r') as f1, open(file_path2, 'r') as f2:
            data1 = json.load(f1)
            data2 = json.load(f2)

        diff_log = []
        is_equal = self.compare_structures(data1, data2, diff_log, path="root")
        return is_equal, "\n".join(diff_log)

    def compare_structures(self, obj1, obj2, diff_log, path=""):
        """Recursively compares two Python objects and logs their differences.

        This function handles nested dictionaries and lists, comparing their
         structures and values while normalizing DisAgg_ keys.

        Args:
            obj1: First object to compare (from reference file)
            obj2: Second object to compare (from new file)
            diff_log (list): List to store difference messages
            path (str): Current path in the object structure for logging

        Returns:
            bool: True if objects are equivalent (ignoring DisAgg_ names),
             False otherwise
        """
        # If objects are of different types, they're not equal
        if type(obj1) != type(obj2):
            diff_log.append(f"Type mismatch at {path}:")
            diff_log.append(f"  Type in ref file: {type(obj1)}")
            diff_log.append(f"  Type in new file: {type(obj2)}")
            return False

        # Handle dictionaries
        if isinstance(obj1, dict):
            if len(obj1) != len(obj2):
                diff_log.append(f"Different number of keys at {path}:")
                diff_log.append(f"  Keys in ref file: {sorted(obj1.keys())}")
                diff_log.append(f"  Keys in new file: {sorted(obj2.keys())}")
                return False

            # Create maps of normalized keys to values
            map1 = self.normalize_keys(obj1)
            map2 = self.normalize_keys(obj2)

            # Compare normalized keys
            if set(map1.keys()) != set(map2.keys()):
                diff_log.append(f"Different keys at {path}:")
                diff_log.append(
                    f"  Only in ref file: "
                    f"{sorted(set(map1.keys()) - set(map2.keys()))}")
                diff_log.append(
                    f"  Only in new file: "
                    f"{sorted(set(map2.keys()) - set(map1.keys()))}")
                return False

            # Recursively compare values
            is_equal = True
            for key in map1:
                new_path = f"{path}.{key}" if path else key
                if not self.compare_structures(map1[key], map2[key], diff_log,
                                               new_path):
                    is_equal = False
            return is_equal

        # Handle lists
        elif isinstance(obj1, list):
            if len(obj1) != len(obj2):
                diff_log.append(f"Different list lengths at {path}:")
                diff_log.append(f"  Length in ref file: {len(obj1)}")
                diff_log.append(f"  Length in new file: {len(obj2)}")
                return False

            # Compare each element
            is_equal = True
            for idx, (item1, item2) in enumerate(zip(obj1, obj2)):
                if not self.compare_structures(item1, item2, diff_log,
                                               f"{path}[{idx}]"):
                    is_equal = False
            return is_equal

        # Handle primitive types
        else:
            if obj1 != obj2:
                diff_log.append(f"Value mismatch at {path}:")
                diff_log.append(f"  Value in ref file: {obj1}")
                diff_log.append(f"  Value in new file: {obj2}")
                return False
            return True

    @staticmethod
    def normalize_keys(dictionary):
        normalized = {}
        for key, value in dictionary.items():
            # Replace DisAgg_<random> with DisAgg_normalized
            if re.match(r'^DisAgg_', key):
                normalized_key = 'DisAgg_normalized'
            else:
                normalized_key = key
            normalized[normalized_key] = value
        return normalized


class TestIntegrationTEASER(IntegrationBaseTEASER, unittest.TestCase):
    def test_teaser_fzkhaus_individual_zones(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.ahu_tz_overwrite = False
        project.sim_settings.zoning_criteria = (
            ZoningCriteria.combined_single_zone)
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project export did not finish successfully.")
        test_result, msg = self.compare_serialized_teaser_models()
        self.assertTrue(test_result, msg)

    def test_teaser_ac20_institute_var_2_all_criteria_zoned(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.ahu_tz_overwrite = False
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = (2015,)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
        test_result, msg = self.compare_serialized_teaser_models()
        self.assertTrue(test_result, msg)

    def test_teaser_ac20_institute_var_2_individual_zones(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.ahu_tz_overwrite = False
        answers = (2015,)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
        test_result, msg = self.compare_serialized_teaser_models()
        self.assertTrue(test_result, msg)

    def test_teaser_digital_hub_all_criteria_zoned(self):
        """Test DigitalHub IFC"""
        ifc_names = {IFCDomain.arch: 'FM_ARC_DigitalHub_with_SB_neu.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.ahu_tz_overwrite = False
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        project.sim_settings.prj_use_conditions = (Path(
            bim2sim.__file__).parent.parent
            / "test/resources/arch/custom_usages/"
            "UseConditionsFM_ARC_DigitalHub.json")
        project.sim_settings.prj_custom_usages = (Path(
            bim2sim.__file__).parent.parent
             / "test/resources/arch/custom_usages/"
             "customUsagesFM_ARC_DigitalHub_with_SB_neu.json")
        answers = ('Other', *(None,) * 12, 2015)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
        test_result, msg = self.compare_serialized_teaser_models()
        self.assertTrue(test_result, msg)

    def test_teaser_ebc_mainbuilding_individual_zones(self):
        """Test ERC Main Building"""
        ifc_names = {IFCDomain.arch: 'ERC_Mainbuilding_Arch.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.ahu_tz_overwrite = False
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
        test_result, msg = self.compare_serialized_teaser_models()
        self.assertTrue(test_result, msg)

    @unittest.skip('Skip because is covered in Regression tests')
    def test_run_kitfzkhaus_spaces_medium_layers_low(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitfzkhaus_spaces_medium_layers_full(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.layers_and_materials = LOD.full
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = ('vertical_core_brick_700',
                   'solid_brick_h',)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitoffice_spaces_medium_layers_full(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.layers_and_materials = LOD.full
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = (2015, 'concrete_CEM_II_BS325R_wz05', 'clay_brick',
                   'Concrete_DK',)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitfzkhaus_spaces_full_layers_full(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.layers_and_materials = LOD.full
        project.sim_settings.zoningCriteria = ZoningCriteria.individual_spaces
        answers = (True, 'solid_brick_h', True, 'hardwood', True,
                   'Concrete_DK', True, 'Light_Concrete_DK',
                   'heavy', 1, 'Door', 1, 'Brick', 'solid_brick_h', 'EnEv',
                   *(1,) * 8)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    @unittest.skip('skip layers_full test until new answers are created')
    def test_run_kitoffice_spaces_full_layers_full(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.individual_spaces
        project.sim_settings.layers_and_materials = LOD.full
        answers = ('Glas', True, 'glas_generic', 500, 1.5, 0.2,
                   True, 'air_layer', 'sandstone', True, 'lime_sandstone_1',
                   True, 'aluminium', 0.1, True, 'Concrete_DK', 2015,
                   "heavy", 1, 'Beton', 'Light_Concrete_DK', 1, 'Door', 1,
                   'Beton', 1, 'Beton', 1, 'fenster', 'Glas1995_2015Aluoder'
                                                      'StahlfensterWaermeschutzverglasungzweifach',
                   1, 'Door',
                   1, 'Beton', 1, 'Beton', *(1,) * 8)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
        test_result, msg = self.compare_serialized_teaser_models()
        self.assertTrue(test_result, msg)

    @unittest.skip('just available to console test')
    def test_live_decisions(self):
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        # ifc_names = {IFCDomain.arch:  'AC20-Institute-Var-2.ifc'
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.individual_spaces
        # answers = ('Glas', True, 'generic', 500, 1.5, 0.2,
        #            True, 'air_layer_DK', 'sandstone', True, 'lime',
        #            'lime_sandstone_1', True, 'aluminium', 0.1, True,
        #            'Concrete_DK', 2015, "heavy",
        #            1, 'Beton', 'Light_Concrete_DK', 1, 'Door', 1, 'Beton', 1,
        #            'Beton', 1, 'fenster', 
        #            'Glas1995_2015AluoderStahlfensterWaer'
        #                                   'meschutzverglasungzweifach', 1,
        #            'Door', 1, 'Beton', 1,
        #            'Beton', *(1,) * 8)
        answers_haus = ('Kitchen - preparations, storage', True,
                        'solid_brick_h', True, 'hard', 'hardwood', True,
                        'DKConcrete_DK', 'light', 'DK', 'heavy', 1, 'Door', 1,
                        'Brick', 'brick_H', 'EnEv', *(1,) * 8)

        ConsoleDecisionHandler().handle(project.run(),
                                        project.loaded_decisions)

    @unittest.skip("just with no internet test")
    def test_run_kitfzkhaus_spaces_medium_layers_full_no_translator(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.layers_and_materials = LOD.full
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = ('Kitchen - preparations, storage', True,
                   'solid_brick_h', True, None, 'wood', 'hardwood', 'concrete',
                   True, 'Concrete_DK', 'concrete', True, 'Light_Concrete_DK',
                   "heavy", 1, ' Door', 1, 'Brick', 'brick_H', "EnEv",
                   *(1,) * 8,)
        ConsoleDecisionHandler().handle(project.run(),
                                        project.loaded_decisions)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
        test_result, msg = self.compare_serialized_teaser_models()
        self.assertTrue(test_result, msg)

    @unittest.skip('skip layers_full test until new answers are created')
    def test_ERC_Full(self):
        """Test ERC Main Building"""
        ifc_names = {IFCDomain.arch: 'ERC_Mainbuilding_Arch.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.ahu_tz_overwrite = False
        project.sim_settings.zoning_criteria = ZoningCriteria.individual_spaces
        project.sim_settings.layers_and_materials = LOD.full
        answers = ("Kitchen in non-residential buildings",
                   "Library - reading room",
                   "MultiUseComputerRoom",
                   "Laboratory",
                   "Parking garages (office and private usage)",
                   "Stock, technical equipment, archives", True,
                   "Air_layer_DK", "perlite", True, "heavy", 1,
                   "beton", "Concrete_DK", "EnEv", 1, 0.3,
                   "beton", 1, "beton", 1, "beton", *(1,) * 8)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
        test_result, msg = self.compare_serialized_teaser_models()
        self.assertTrue(test_result, msg)

    @unittest.skip('Skip because takes to long in CI')
    def test_ERC_Medium(self):
        """Test ERC Main Building"""
        ifc_names = {IFCDomain.arch: 'ERC_Mainbuilding_Arch.ifc'}
        project = self.create_project(ifc_names, 'TEASER')
        project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
        test_result, msg = self.compare_serialized_teaser_models()
        self.assertTrue(test_result, msg)
