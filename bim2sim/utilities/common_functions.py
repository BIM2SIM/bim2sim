import collections
import json
import math
import re
from pathlib import Path
from typing import Union

import bim2sim

assets = Path(bim2sim.__file__).parent / 'assets'


def angle_equivalent(angle):
    while angle >= 360 or angle < 0:
        if angle >= 360:
            angle -= 360
        elif angle < 0:
            angle += 360
    return angle


def vector_angle(vector):
    """returns the angle between y-axis and vector"""
    x = vector[0]
    y = vector[1]
    try:
        tang = math.degrees(math.atan(x / y))
    except ZeroDivisionError:
        if x > 0:
            angle = 90
        elif x < 0:
            angle = 270
        else:
            angle = 0
    else:
        if x >= 0:
            # quadrant 1
            if y > 0:
                angle = tang
            # quadrant 2
            else:
                angle = tang + 180
        else:
            # quadrant 3
            if y < 0:
                angle = tang + 180
            # quadrant 4
            else:
                angle = tang + 360
    return angle




def validateJSON(json_data: Union[str, Path, ]):
    if not isinstance(json_data, Path):
        json_data = Path(str(json_data))
    try:
        with open(json_data, 'rb') as file:
            json.load(file)
    except ValueError:
        return False
    return True


def get_usage_dict(prj_name) -> dict:
    custom_usage_path = assets / 'enrichment/usage' / \
                        ('UseConditions' + prj_name + '.json')
    if custom_usage_path.is_file():
        usage_path = custom_usage_path
    else:
        usage_path = assets / 'enrichment/usage/UseConditions.json'
    if validateJSON(usage_path):
        with open(usage_path, 'r+', encoding='utf-8') as file:
            usage_dict = json.load(file)
            del usage_dict['version']
            return usage_dict
    else:
        raise ValueError(f"Invalid JSON file  {usage_path}")


def get_common_pattern_usage() -> dict:
    common_pattern_path = assets / 'enrichment/usage/commonUsages.json'
    if validateJSON(common_pattern_path):
        with open(common_pattern_path, 'r+', encoding='utf-8') as file:
            common_usages = json.load(file)
            return common_usages
    else:
        raise ValueError(f"Invalid JSON file  {common_pattern_path}")


def get_custom_pattern_usage(prj_name) -> dict:
    """gets custom usages based on specific project or general defined file."""
    custom_usages = {}
    custom_pattern_path_prj = assets / 'enrichment/usage' \
        / ('customUsages' + prj_name + '.json')
    if custom_pattern_path_prj.is_file():
        custom_pattern_path = custom_pattern_path_prj
    else:
        custom_pattern_path = assets / 'enrichment/usage/customUsages.json'
    if validateJSON(custom_pattern_path):
        with open(custom_pattern_path, 'r+', encoding='utf-8') as file:
            custom_usages_json = json.load(file)
            if custom_usages_json["settings"]["use"]:
                custom_usages = custom_usages_json["usage_definitions"]
            return custom_usages
    else:
        raise ValueError(f"Invalid JSON file  {custom_pattern_path}")


def get_pattern_usage(prj_name):
    """get usage patterns to use it on the thermal zones get_usage"""
    use_conditions = get_usage_dict(prj_name)
    common_usages = get_common_pattern_usage()

    custom_usages = get_custom_pattern_usage(prj_name)
    usages = combine_usages(common_usages, custom_usages)

    pattern_usage_teaser = collections.defaultdict(dict)

    for i in use_conditions:
        pattern_usage_teaser[i]["common"] = []
        pattern_usage_teaser[i]["custom"] = []
        list_engl = re.sub(r'\((.*?)\)', '', i) \
            .replace(' - ', ', ') \
            .replace(' and ', ', ') \
            .replace(' in ', ', ') \
            .replace(' with ', ', ') \
            .replace(' or ', ', ') \
            .replace(' the ', ' ') \
            .split(', ')
        for i_eng in list_engl:
            new_i_eng = i_eng.replace(' ', '(.*?)')
            pattern_usage_teaser[i]["common"].append(re.compile(
                '(.*?)%s' % new_i_eng, flags=re.IGNORECASE))
            if i in usages:
                for c_trans in usages[i]["common"]:
                    pattern_usage_teaser[i]["common"].append(re.compile(
                        '(.*?)%s' % c_trans, flags=re.IGNORECASE))
                if "custom" in usages[i]:
                    for clear_usage in usages[i]["custom"]:
                        pattern_usage_teaser[i]["custom"].append(clear_usage)

    pattern_usage_teaser['office_function']["common"] = [re.compile(
        '(.*?)%s' % c_trans, re.IGNORECASE)
        for c_trans in usages['office_function']["common"]]

    return pattern_usage_teaser


def combine_usages(common_usages, custom_usages) -> dict:
    """combines the custom and common usages to one dictionary"""
    usages = collections.defaultdict(dict)
    # combine common and custom usages
    for key, value in common_usages.items():
        usages[key]["common"] = value
    if custom_usages:
        for key, value in custom_usages.items():
            if not isinstance(value, list):
                try:
                    value = list(value)
                except TypeError:
                    raise TypeError("custom usages must be a list")
            if key in usages.keys():
                usages[key]["custom"] = value
    return usages


def get_type_building_elements():
    type_building_elements_path = \
        assets / 'enrichment/material/TypeBuildingElements.json'
    if validateJSON(type_building_elements_path):
        with open(type_building_elements_path, 'r+') as file:
            type_building_elements = json.load(file)
            del type_building_elements['version']
    else:
        raise ValueError(f"Invalid JSON file  {type_building_elements_path}")
    template_options = {}
    for i in type_building_elements:
        i_name, i_years, i_template = i.split('_')
        if i_name not in template_options:
            template_options[i_name] = {}
        if i_years not in template_options[i_name]:
            template_options[i_name][i_years] = {}
        template_options[i_name][i_years][i_template] = type_building_elements[
            i]
    return template_options


def get_material_templates():
    material_templates_path = \
        assets / 'enrichment/material/MaterialTemplates.json'
    if validateJSON(material_templates_path):
        with open(material_templates_path, 'r+') as f:
            material_templates = json.load(f)
            del material_templates['version']
    else:
        raise ValueError(f"Invalid JSON file  {material_templates_path}")
    return material_templates


def get_type_building_elements_hvac():
    # todo: still needed?
    type_building_elements_path = \
        assets / 'enrichment/hvac/TypeHVACElements.json'
    if validateJSON(type_building_elements_path):
        with open(type_building_elements_path, 'r+') as file:
            type_building_elements = json.load(file)
            del type_building_elements['version']
    else:
        raise ValueError(f"Invalid JSON file  {type_building_elements_path}")
    return type_building_elements


def filter_instances(instances: Union[dict, list], type_name) -> list:
    """Filters the inspected instances by type name (e.g. Wall) and
    returns them as list

    Args:
        instances: dict or list with all bim2sim instances
        type_name: str or element type to filter for
    Returns:
        instances_filtered: list of all bim2sim instances of type type_name
    """
    instances_filtered = []
    list_instances = instances.values() if type(instances) is dict \
        else instances
    if isinstance(type_name, str):
        for instance in list_instances:
            if type_name in type(instance).__name__:
                instances_filtered.append(instance)
    else:
        for instance in list_instances:
            if type_name is type(instance):
                instances_filtered.append(instance)
    return instances_filtered


def remove_umlaut(string):
    """
    Removes umlauts from strings and replaces them with the letter+e convention
    :param string: string to remove umlauts from
    :return: unumlauted string
    """
    u = 'ü'.encode()
    U = 'Ü'.encode()
    a = 'ä'.encode()
    A = 'Ä'.encode()
    o = 'ö'.encode()
    O = 'Ö'.encode()
    ss = 'ß'.encode()

    string = string.encode()
    string = string.replace(u, b'ue')
    string = string.replace(U, b'Ue')
    string = string.replace(a, b'ae')
    string = string.replace(A, b'Ae')
    string = string.replace(o, b'oe')
    string = string.replace(O, b'Oe')
    string = string.replace(ss, b'ss')

    string = string.decode('utf-8')
    return string


def translate_deep(text, source='auto', target='en'):
    """ translate function that uses deep_translator package with
    Google Translator"""
    # return False  # test no internet
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(
            source=source, target=target).translate(text=text)
        return translated
    except:
        #return False
        return ''
    # proxies_example = {
    #     "https": "34.195.196.27:8080",
    #     "http": "34.195.196.27:8080"
    # }


def all_subclasses(cls, as_names: bool = False):
    """Get all subclasses of the given subclass, even subsubclasses and so on

    Args:
        as_names: boolean, if True the subclasses are returned as names
        """
    all_cls = set(cls.__subclasses__()).union(
            [s for c in cls.__subclasses__() for s in all_subclasses(c)])
    if as_names:
        all_cls = [cls.__name__ for cls in all_cls]
    return all_cls


def get_spaces_with_bounds(instances: dict):
    """Get spaces (ThermalZone) that provide space boundaries.
    This function extracts spaces from an instance dictionary and returns
    those spaces that hold space boundaries.
    Args:
        instances: dict[guid: element]
    """

    spaces = filter_instances(instances, 'ThermalZone')
    spaces_with_bounds = [s for s in spaces if s.space_boundaries]

    return spaces_with_bounds
