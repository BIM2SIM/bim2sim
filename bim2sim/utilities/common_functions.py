import collections
import json
import math
import re
import zipfile
from urllib.request import urlopen
from pathlib import Path
from typing import Union
from time import sleep

import bim2sim
from bim2sim.utilities.types import IFCDomain

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


def validateJSON(json_data: Union[str, Path,]):
    if not isinstance(json_data, Path):
        json_data = Path(str(json_data))
    try:
        with open(json_data, 'rb') as file:
            json.load(file)
    except ValueError:
        return False
    return True


def get_use_conditions_dict(custom_use_cond_path: Path) -> dict:
    if custom_use_cond_path:
        if custom_use_cond_path.is_file():
            use_cond_path = custom_use_cond_path
    else:
        use_cond_path = assets / 'enrichment/usage/UseConditions.json'
    if validateJSON(use_cond_path):
        with open(use_cond_path, 'r+', encoding='utf-8') as file:
            use_cond_dict = json.load(file)
            del use_cond_dict['version']
            return use_cond_dict
    else:
        raise ValueError(f"Invalid JSON file {use_cond_path}")


def get_common_pattern_usage() -> dict:
    common_pattern_path = assets / 'enrichment/usage/commonUsages.json'
    if validateJSON(common_pattern_path):
        with open(common_pattern_path, 'r+', encoding='utf-8') as file:
            common_usages = json.load(file)
            return common_usages
    else:
        raise ValueError(f"Invalid JSON file  {common_pattern_path}")


def get_custom_pattern_usage(custom_usages_path: Path) -> dict:
    """gets custom usages based on given json file."""
    custom_usages = {}
    if custom_usages_path and custom_usages_path.is_file():
        if validateJSON(custom_usages_path):
            with open(custom_usages_path, 'r+', encoding='utf-8') as file:
                custom_usages_json = json.load(file)
                if custom_usages_json["settings"]["use"]:
                    custom_usages = custom_usages_json["usage_definitions"]
                return custom_usages
        else:
            raise ValueError(f"Invalid JSON file  {custom_usages_path}")


def get_pattern_usage(use_conditions: dict, custom_usages_path: Path):
    """get usage patterns to use it on the thermal zones get_usage"""
    common_usages = get_common_pattern_usage()

    custom_usages = get_custom_pattern_usage(custom_usages_path)
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


def wildcard_match(pattern, text):
    """Check if a text string matches a pattern containing '*' wildcards.

    Args:
        pattern (str): The pattern string that may contain '*' wildcards.
        text (str): The text string to be compared against the pattern.

    Returns:
        bool: True if the text matches the pattern, considering wildcards.
              False otherwise.
    """
    # Split the pattern by '*'
    parts = pattern.split('*')

    # If there is no wildcard in the pattern, perform a simple equality
    # check
    if len(parts) == 1:
        return pattern == text

    # If the pattern starts with '*', check if the text ends with the las
    # t part
    if pattern.startswith('*'):
        return text.endswith(parts[1])

    # If the pattern ends with '*', check if the text starts with the first
    # part
    if pattern.endswith('*'):
        return text.startswith(parts[0])

    # If the pattern has '*' in the middle, check if the parts are present
    # in order in the text
    for i, part in enumerate(parts):
        if part:
            if i == 0:
                if not text.startswith(part):
                    return False
            elif i == len(parts) - 1:
                if not text.endswith(part):
                    return False
            else:
                index = text.find(part)
                if index == -1:
                    return False
                text = text[index + len(part):]

    return True


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


def filter_elements(elements: Union[dict, list], type_name, create_dict=False)\
        -> Union[list, dict]:
    """Filters the inspected elements by type name (e.g. Wall) and
    returns them as list or dict if wanted

    Args:
        elements: dict or list with all bim2sim elements
        type_name: str or element type to filter for
        create_dict (Boolean): True if a dict instead of a list should be
            created
    Returns:
        elements_filtered: list of all bim2sim elements of type type_name
    """
    from bim2sim.elements.base_elements import SerializedElement
    elements_filtered = []
    list_elements = elements.values() if type(elements) is dict \
        else elements
    if isinstance(type_name, str):
        for instance in list_elements:
            if isinstance(instance, SerializedElement):
                if instance.element_type == type_name:
                    elements_filtered.append(instance)
            else:
                if type_name in type(instance).__name__:
                    elements_filtered.append(instance)
    else:
        for instance in list_elements:
            if isinstance(instance, SerializedElement):
                if instance.element_type == type_name.__name__:
                    elements_filtered.append(instance)
            if type_name is type(instance):
                elements_filtered.append(instance)
    if not create_dict:
        return elements_filtered
    else:
        return {inst.guid: inst for inst in elements_filtered}


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


def all_subclasses(cls, as_names: bool = False, include_self: bool=False):
    """Get all subclasses of the given subclass, even subsubclasses and so on

    Args:
        cls: class for which to find subclasses
        as_names: boolean, if True the subclasses are returned as names
        include_self: boolean, if True include evaluated class to subclasses.
        """
    all_cls = set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in all_subclasses(c)])
    if as_names:
        all_cls = [cls.__name__ for cls in all_cls]
    if include_self:
        if as_names:
            all_cls.add(cls.__name__)
        else:
            all_cls.add(cls)
    return all_cls


def get_spaces_with_bounds(elements: dict):
    """Get spaces (ThermalZone) that provide space boundaries.

    This function extracts spaces from an instance dictionary and returns
    those spaces that hold space boundaries.

    Args:
        elements: dict[guid: element]
    """

    spaces = filter_elements(elements, 'ThermalZone')
    spaces_with_bounds = [s for s in spaces if s.space_boundaries]

    return spaces_with_bounds


def download_file(url:str, target: Path):
    """Download the file from url and put into target path.

    Unzips the downloaded content if it is a zip.

    Args:
        url: str that holds url
        target: pathlib path to target
    """
    with urlopen(url) as sciebo_website:
        # Download from URL
        content = sciebo_website.read()
        # Save to file
        with open(target, 'wb') as download:
            download.write(content)
        if str(target).lower().endswith('zip'):
            # unzip files
            with zipfile.ZipFile(target, 'r') as zip_ref:
                zip_ref.extractall(target.parent)
            # wait a second to prevent problems with deleting the file
            sleep(1)
            # remove zip file
            Path.unlink(target)


def download_test_resources(
        domain: Union[str, IFCDomain],
        with_regression: bool = False,
        force_new: bool = False):
    """Download test resources from Sciebo cloud.

    This downloads additional resources in form of IFC files, regression results
    and custom usages for BPS simulations for tests that should not be stored in
    repository for size reasons.

    domain: IFCDomain for that the content is wanted
    with_regression: boolean that determines if regression results should be
    downloaded as well.
    force_new: bool to force update of resources even if folders already exist
    """
    # TODO #539: include hvac regression results here when implemented
    if not isinstance(domain, IFCDomain):
        try:
            domain = IFCDomain[domain]
        except ValueError:
            raise ValueError(f"{domain} is not one of "
                             f"{[domain.name for domain in IFCDomain]}, "
                             f"please specify a valid download domain")
    domain_name = domain.name

    # check if already exists
    test_rsrc_base_path = Path(__file__).parent.parent.parent / 'test/resources'
    if Path.exists(test_rsrc_base_path / domain_name) and not force_new:
        return
    print(f"Downloading test resources for Domain {domain_name}")
    if not Path.exists(test_rsrc_base_path / domain_name):
        Path.mkdir(test_rsrc_base_path / domain_name)

    sciebo_urls = {
        'arch_ifc':
            'https://rwth-aachen.sciebo.de/s/Imfggxwv8AKZ8T7/download',
        'arch_regression_results':
            'https://rwth-aachen.sciebo.de/s/ria5Zi9WdcjFr37/download',
        'arch_custom_usages':
            'https://rwth-aachen.sciebo.de/s/nzrGDLPAmHDQkBo/download',
        'hydraulic_ifc':
            'https://rwth-aachen.sciebo.de/s/fgMCUmFFEZSI9zU/download',
        'hydraulic_regression_results': None,

    }


    download_file(
        url=sciebo_urls[domain_name+'_ifc'],
        target=test_rsrc_base_path / domain_name / 'ifc.zip')
    if domain == IFCDomain.arch:
        download_file(
            url=sciebo_urls[domain_name+'_custom_usages'],
            target=test_rsrc_base_path / domain_name / 'custom_usages.zip')
    if with_regression:
        # TODO #539: remove these lines when implemented hvac regression
        #  tests
        if domain == IFCDomain.hydraulic:
            raise NotImplementedError("Currently there are no regression"
                                      " results for hydraulic simulations")
        else:
            download_file(
                url=sciebo_urls[domain_name + '_regression_results'],
                target=test_rsrc_base_path / domain_name /
                       'regression_results.zip')
    if domain not in [IFCDomain.arch, IFCDomain.hydraulic]:
        raise ValueError(f"For the domain {domain.name} currently no test "
                         f"files exist.")


def rm_tree(pth):
    """Remove an empty or non-empty directory using pathlib"""
    pth = Path(pth)
    for child in pth.glob('*'):
        if child.is_file():
            child.unlink()
        else:
            rm_tree(child)
    pth.rmdir()

def create_plotly_graphs_from_df(self):
    # save plotly graphs to export folder
    # todo 497
    pass


def group_by_levenshtein(entities, similarity_score):
    """
    Groups similar entities based on the similarity of their 'Name' attribute.

    Args:
        entities (list): A list of objects with a 'Name' attribute.
        similarity_score (float): Similarity threshold between 0 and 1.
            0 means all objects will be grouped together, 1 means only identical
             strings are grouped.

    Returns:
        dict: A dictionary where keys are representative entities and values are
         lists of similar entities.
    """

    from collections import defaultdict

    def levenshtein(s1, s2):
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i

        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                dp[i][j] = min(
                    dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)

        return dp[m][n]

    repres = defaultdict(list)

    for entity in entities:
        matched = False
        for rep_entity in repres:
            if levenshtein(entity.Name, rep_entity.Name) <= int((1 - similarity_score) * max(len(entity.Name), len(rep_entity.Name))):
                repres[rep_entity].append(entity)
                matched = True
                break
        if not matched:
            repres[entity].append(entity)

    return repres
