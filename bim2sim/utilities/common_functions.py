import collections
import json
import logging
import math
import re
import shutil
import zipfile
from urllib.request import urlopen
from pathlib import Path
from typing import Union
from time import sleep
import git

import bim2sim
from bim2sim.utilities.types import IFCDomain

assets = Path(bim2sim.__file__).parent / 'assets'
logger = logging.getLogger(__name__)


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

# obsolete
def get_common_pattern_usage() -> dict:
    common_pattern_path = assets / 'enrichment/usage/commonUsages.json'
    if validateJSON(common_pattern_path):
        with open(common_pattern_path, 'r+', encoding='utf-8') as file:
            common_usages = json.load(file)
            return common_usages
    else:
        raise ValueError(f"Invalid JSON file  {common_pattern_path}")

# obsolete
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


def compile_usage_patterns(use_conditions, custom_usages, common_usages):
    import collections
    pattern_usage = collections.defaultdict(lambda: {"common": [], "custom": []})
    combined = combine_usages(common_usages, custom_usages)

    for usage_label in use_conditions:
        list_engl = re.sub(r'\((.*?)\)', '', usage_label) \
            .replace(' - ', ', ') \
            .replace(' and ', ', ') \
            .replace(' in ', ', ') \
            .replace(' with ', ', ') \
            .replace(' or ', ', ') \
            .replace(' the ', ' ') \
            .split(', ')
        for word in list_engl:
            regex = re.compile(f"(.*?){word.strip().replace(' ', '(.*?)')}", re.IGNORECASE)
            pattern_usage[usage_label]["common"].append(regex)

        if usage_label in combined:
            for val in combined[usage_label].get("common", []):
                pattern_usage[usage_label]["common"].append(re.compile(f"(.*?){val}", re.IGNORECASE))
            for val in combined[usage_label].get("custom", []):
                pattern_usage[usage_label]["custom"].append(val)

    return pattern_usage


def get_effective_usage_data(custom_usage_path: Path = None, custom_conditions_path: Path = None):
    """
    Determines which usage and condition data to use:
    - If both custom files are present and valid → use only them.
    - Else → fallback to defaults in `assets/enrichment/usage`.
    
    Returns:
        Tuple of:
        - use_conditions (dict)
        - pattern_usage (dict with compiled regex)
    """
    # Check custom use conditions
    if custom_conditions_path and custom_conditions_path.exists():
        use_conditions_path = custom_conditions_path
    else:
        use_conditions_path = assets / 'enrichment/usage/UseConditions.json'

    if not validateJSON(use_conditions_path):
        raise ValueError(f"Invalid use conditions file: {use_conditions_path}")

    with open(use_conditions_path, 'r', encoding='utf-8') as f:
        use_conditions = json.load(f)
        if "version" in use_conditions:
            del use_conditions["version"]

    # Check custom usage definitions
    custom_usages = {}
    if custom_usage_path and custom_usage_path.exists() and validateJSON(custom_usage_path):
        with open(custom_usage_path, 'r', encoding='utf-8') as f:
            custom_data = json.load(f)
            if custom_data.get("settings", {}).get("use"):
                custom_usages = custom_data["usage_definitions"]

    if custom_usages:
        common_usages = {}  # ⛔️ skip loading common if custom is valid
    else:
        # fallback to defaults
        common_usages_path = assets / 'enrichment/usage/commonUsages.json'
        if not validateJSON(common_usages_path):
            raise ValueError(f"Invalid fallback usage file: {common_usages_path}")
        with open(common_usages_path, 'r', encoding='utf-8') as f:
            common_usages = json.load(f)

    pattern_usage = compile_usage_patterns(use_conditions, custom_usages, common_usages)
    return use_conditions, pattern_usage


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
            else:
                usages[key]["custom"] = value
                usages[key]["common"] = []
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


def get_type_building_elements(data_file):
    type_building_elements_path = \
        assets / 'enrichment/material' / data_file
    if validateJSON(type_building_elements_path):
        with open(type_building_elements_path, 'r+') as file:
            type_building_elements = json.load(file)
            del type_building_elements['version']
    else:
        raise ValueError(f"Invalid JSON file  {type_building_elements_path}")
    template_options = {}
    for i in type_building_elements:
        i_name, i_years = i.split('_')[0:2]
        i_template = i.split(f'{i_years}_')[1]
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


def filter_elements(
        elements: Union[dict, list], type_name, create_dict=False)\
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


def download_library(
        repo_url: str,
        branch_name: str,
        clone_dir: Path,
):
    """Clones a Git repository and checks out a specific branch, or updates
    the repository if it already exists.

    This function clones the specified Git repository into the given directory
    and checks out the specified branch. If the directory already exists and
    is a Git repository, it will perform a 'git pull' to update the repository
    instead of cloning.

    Args:
        repo_url (str): The URL of the Git repository to clone or update.
        branch_name (str): The name of the branch to check out.
        clone_dir (Path): The directory where the repository should be cloned
                          or updated.

    Returns:
        None

    Raises:
        git.GitCommandError: If there is an error during the cloning, checkout,
                             or pull process.
        Exception: If the directory exists but is not a Git repository.
    """
    if clone_dir.exists():
        # If the directory exists, check if it's a Git repository
        try:
            repo = git.Repo(clone_dir)
            if repo.bare:
                raise Exception(
                    f"Directory {clone_dir} is not a valid Git repository.")

            # If it's a valid Git repository, perform a pull to update it
            print(
                f"Directory {clone_dir} already exists. Pulling latest "
                f"changes...")
            repo.git.checkout(
                branch_name)  # Ensure we're on the correct branch
            repo.remotes.origin.pull()
            print(f"Repository in {clone_dir} updated successfully.")

        except git.exc.InvalidGitRepositoryError:
            raise Exception(
                f"Directory {clone_dir} exists but is not a Git repository.")

    else:
        # If the directory doesn't exist, clone the repository
        print(f"Cloning repository {repo_url} into {clone_dir}...")
        repo = git.Repo.clone_from(
            repo_url, clone_dir, branch=branch_name, recursive=True)

        # Checkout the specified branch
        print(f"Checking out branch {branch_name}...")
        repo.git.checkout(branch_name)
        print(f"Checked out branch {branch_name}.")


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
