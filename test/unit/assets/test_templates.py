"""Testing all json assets for integrity
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import bim2sim
from bim2sim.utilities.common_functions import validateJSON


class TestTemplates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.TemporaryDirectory(prefix='bim2sim_')
        os.mkdir(os.path.join(cls.root.name, 'templates'))

    @classmethod
    def tearDownClass(cls):
        # Decision.reset_decisions()
        cls.root.cleanup()

    def test_material_templates_keys(self):
        material_path = (Path(bim2sim.__file__).parent /
                       'assets/enrichment/material/MaterialTemplates.json')
        with open(material_path, 'rb') as file:
            material_template = json.load(file)

        required_keys = {
            "name",
            "density",
            "thermal_conduc",
            "heat_capac",
            "thickness_default",
            "thickness_list",
            "solar_absorp"
        }

        failures = []

        for key, value in material_template.items():
            if key == "version":
                continue

            if not isinstance(value, dict):
                failures.append(
                    f"Value for key '{key}' is not a dictionary")
                continue

            value_keys = value.keys()
            missing_keys = required_keys - value_keys
            extra_keys = value_keys - required_keys

            if missing_keys:
                failures.append(
                    f"Missing keys in entry '{key}': {missing_keys}")
            if extra_keys:
                failures.append(
                    f"Extra keys in entry '{key}': {extra_keys}")

        self.assertEqual(len(failures), 0,
                         f"Failures found:\n" + "\n".join(failures))

    def test_material_templates_values(self):
        material_path = (Path(bim2sim.__file__).parent /
                         'assets/enrichment/material/MaterialTemplates.json')
        with open(material_path, 'rb') as file:
            material_template = json.load(file)

        required_keys = {
            "name": {"type": str},
            "density": {"type": (int, float), "min": 1e-6,
                        "max": 25000},
            "thermal_conduc": {"type": (int, float), "min": 1e-6},
            "heat_capac": {"type": (int, float)},
            "thickness_default": {"type": (int, float),
                                  "min": 1e-6},
            "thickness_list": {"type": list,
                               "element_type": (int, float),
                               "min_element": 1e-6},
            "solar_absorp": {"type": (int, float), "min": 0,
                             "max": 1}
        }

        failures = []

        for key, value in material_template.items():
            if key == "version":
                continue

            for subkey, constraints in required_keys.items():
                if subkey not in value:
                    continue
                subvalue = value[subkey]
                if not isinstance(subvalue, constraints["type"]):
                    failures.append(
                        f"'{subkey}' in entry '{key}' is not of type "
                        f"{constraints['type']}")
                if "min" in constraints and subvalue < constraints["min"]:
                    failures.append(
                        f"'{subkey}' in entry '{key}' is less than "
                        f"{constraints['min']}, which is {subvalue}")
                if "max" in constraints and subvalue > constraints["max"]:
                    failures.append(
                        f"'{subkey}' in entry '{key}' is greater than "
                        f"{constraints['max']}, which is {subvalue}")

                if subkey == "thickness_list":
                    if not isinstance(subvalue, list):
                        failures.append(
                            f"'{subkey}' in entry '{key}' is not a list")
                    else:
                        for element in subvalue:
                            if not isinstance(element,
                                              constraints["element_type"]):
                                failures.append(
                                    f"An element in 'thickness_list' in entry "
                                    f"'{key}' is not of type "
                                    f"{constraints['element_type']}")
                            if element < constraints["min_element"]:
                                failures.append(
                                    f"An element in 'thickness_list' in "
                                    f"entry '{key}' is less than "
                                    f"{constraints['min_element']}, which is "
                                    f"{element}")

        self.assertEqual(len(failures), 0,
                         f"Failures found:\n" + "\n".join(failures))
