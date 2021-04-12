import math
import re
import json
import translators as ts

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
            return 90
        elif x < 0:
            return 270
        else:
            return 0
    if x >= 0:
        # quadrant 1
        if y > 0:
            return tang
        # quadrant 2
        else:
            return tang + 180
    else:
        # quadrant 3
        if y < 0:
            return tang + 180
        # quadrant 4
        else:
            return tang + 360


assets = Path(bim2sim.__file__).parent/'assets'


def get_usage_dict() -> dict:
    usage_path = assets/'MaterialTemplates'/'UseConditions.json'
    with open(usage_path, 'r+') as f:
        usage_dict = json.load(f)
        del usage_dict['version']
    return usage_dict


def get_pattern_usage(translate=False):
    """get usage patterns to use it on the thermal zones get_usage"""
    use_conditions_path = assets/'MaterialTemplates/UseConditions.json'
    with open(use_conditions_path, 'r+') as f:
        use_conditions = list(json.load(f).keys())
        use_conditions.remove('version')

    common_translations = {
        "Bed room": ['Schlafzimmer'],
        "Living": ["Galerie", "Wohnen"],
        "Laboratory": ["Labor"],
        'office_function': ['Office', 'Buero'],
        "Meeting, Conference, seminar": ['Besprechungsraum', 'Seminarraum'],
        'Kitchen in non-residential buildings': ['Kitchen', 'Küche'],
        'Kitchen - preparations, storage': ['Kitchen', 'Küche'],
        'Traffic area': ['Hall', 'Flur', 'Dachboden'],
        'WC and sanitary rooms in non-residential buildings': ['bath', 'bathroom', 'WC', 'Toilet', 'Bad'],
        'Stock, technical equipment, archives': ['Technical room', 'Technikraum']
    }
    pattern_usage_teaser = {}
    for i in use_conditions:
        pattern_usage_teaser[i] = []
        list_engl = re.sub(r'\((.*?)\)', '', i).replace(' - ', ', ').replace(' and ', ', ').replace(' in ', ', ') \
            .replace(' with ', ', ').replace(' or ', ', ').replace(' the ', ' ').split(', ')
        for i_eng in list_engl:
            new_i_eng = i_eng.replace(' ', '(.*?)')
            pattern_usage_teaser[i].append(re.compile('(.*?)%s' % new_i_eng, flags=re.IGNORECASE))
            if i in common_translations:
                for c_trans in common_translations[i]:
                    pattern_usage_teaser[i].append(re.compile('(.*?)%s' % c_trans, flags=re.IGNORECASE))
        if translate:
            trans = ts.bing(i, from_language='en', to_language='de')

            list_de = re.sub(r'\((.*?)\)', '', trans).replace(' - ', ', ').replace(' and ', ', ').replace(' in ', ', ') \
                .replace(' with ', ', ').replace(' or ', ', ').replace(' the ', ' ').split(', ')
            for i_de in list_de:
                new_i_de = i_de.replace(' ', '(.*?)')
                pattern_usage_teaser[i].append(re.compile('(.*?)%s' % new_i_de, flags=re.IGNORECASE))

    pattern_usage_teaser['office_function'] = [re.compile('(.*?)Office', re.IGNORECASE),
                                               re.compile('(.*?)Buero', re.IGNORECASE)]

    return pattern_usage_teaser


def get_type_building_elements():
    type_building_elements_path = \
        assets/'MaterialTemplates/TypeBuildingElements.json'
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
    material_templates_path = assets/'MaterialTemplates/MaterialTemplates.json'
    with open(material_templates_path, 'r+') as f:
        material_templates = json.load(f)
        del material_templates['version']
    return material_templates


def get_type_building_elements_hvac():
    type_building_elements_path = assets/'enrichment/TypeBuildingElements.json'
    with open(type_building_elements_path, 'r+') as f:
        type_building_elements = json.load(f)
        del type_building_elements['version']
    return type_building_elements


def filter_instances(instances, type_name):
    """Filters the inspected instances by type name (e.g. Wall) and
    returns them as list"""
    instances_filtered = []
    if type(instances) is dict:
        list_instances = instances.values()
    else:
        list_instances = instances
    for instance in list_instances:
        if type_name in type(instance).__name__:
            instances_filtered.append(instance)
    return instances_filtered
