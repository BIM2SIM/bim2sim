import collections
import math
import re
import json
import bim2sim

from pathlib import Path


def angle_equivalent(angle):
    while angle >= 360 or angle < 0:
        if angle >= 360:
            angle -= 360
        elif angle < 0:
            angle += 360
    return angle


def vector_angle(vector):
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


assets = Path(bim2sim.__file__).parent/'assets'


def get_usage_dict(prj_name) -> dict:
    custom_usage_path = assets/'enrichment/usage' /\
                        ('UseConditions'+prj_name+'.json')
    if custom_usage_path.is_file():
        usage_path = custom_usage_path
    else:
        usage_path = assets/'enrichment/usage/UseConditions.json'
    with open(usage_path, 'r+') as f:
        usage_dict = json.load(f)
        del usage_dict['version']
    return usage_dict


def get_common_pattern_usage() -> dict:
    custom_pattern_path = assets/'enrichment/usage/commonUsages.json'
    with open(custom_pattern_path, 'r+', encoding='utf-8') as f:
        common_usages = json.load(f)
    return common_usages


def get_custom_pattern_usage(prj_name) -> dict:
    """gets custom usages based on specific project or general defined file."""
    custom_usages = {}
    custom_pattern_path_prj = assets/'enrichment/usage' /\
                        ('customUsages'+prj_name+'.json')
    if custom_pattern_path_prj.is_file():
        custom_pattern_path = custom_pattern_path_prj
    else:
        custom_pattern_path = assets/'enrichment/usage/customUsages.json'
    with open(custom_pattern_path, 'r+', encoding='utf-8') as f:
        custom_usages_json = json.load(f)
    if custom_usages_json["settings"]["use"]:
        custom_usages = custom_usages_json["usage_definitions"]
    return custom_usages


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
        list_engl = re.sub(r'\((.*?)\)', '', i)\
            .replace(' - ', ', ')\
            .replace(' and ', ', ')\
            .replace(' in ', ', ')\
            .replace(' with ', ', ')\
            .replace(' or ', ', ')\
            .replace(' the ', ' ')\
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
        assets/'enrichment/material/TypeBuildingElements.json'
    with open(type_building_elements_path, 'r+') as f:
        type_building_elements = json.load(f)
        del type_building_elements['version']
    template_options = {}
    for i in type_building_elements:
        i_name, i_years, i_template = i.split('_')
        if i_name not in template_options:
            template_options[i_name] = {}
        if i_years not in template_options[i_name]:
            template_options[i_name][i_years] = {}
        template_options[i_name][i_years][i_template] = type_building_elements[i]
    return template_options


def get_material_templates():
    material_templates_path = \
        assets/'enrichment/material/MaterialTemplates.json'
    with open(material_templates_path, 'r+') as f:
        material_templates = json.load(f)
        del material_templates['version']
    return material_templates


def get_type_building_elements_hvac():
    type_building_elements_path = \
        assets/'enrichment/hvac/TypeHVACElements.json'
    with open(type_building_elements_path, 'r+') as f:
        type_building_elements = json.load(f)
        del type_building_elements['version']
    return type_building_elements


def filter_instances(instances, type_name):
    """Filters the inspected instances by type name (e.g. Wall) and
    returns them as list"""
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
        return False
    # proxies_example = {
    #     "https": "34.195.196.27:8080",
    #     "http": "34.195.196.27:8080"
    # }


def all_subclasses(cls):
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in all_subclasses(c)])
