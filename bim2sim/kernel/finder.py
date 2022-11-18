"""Finders are used to get properties from ifc which do not use the default
 PropertySets
 """

import os
import json
import contextlib
from pathlib import Path
import logging
from typing import Generator

import bim2sim
from bim2sim.kernel import ifc2python
from bim2sim.decision import ListDecision, Decision
from bim2sim.utilities.common_functions import validateJSON

logger = logging.getLogger(__name__)
DEFAULT_PATH = Path(bim2sim.__file__).parent / 'assets/finder'


class Finder:

    def find(self, element, property_name):
        raise NotImplementedError()

    def reset(self):
        """Reset finder instance"""
        raise NotImplementedError()


class TemplateFinder(Finder):
    """TemplateFinder works like a multi key dictionary.

    Use it for tool dependent property usage. 
    E.g. Revit stores length of IfcPipeSegment in PropertySet 'Abmessungen'
    with name 'Länge'."""
    prefix = "template_"

    def __init__(self):
        super().__init__()
        # {tool: {Element class name: {parameter: (Pset name, property name)}}}
        self.templates = {}
        self.blacklist = []
        self.path = None
        self.load(DEFAULT_PATH)  # load default path
        self.enabled = True

    def load(self, path):
        """loads templates from given path. Each *.json file is interpreted as
         tool with name *, also searches default templates"""
        if not isinstance(path, Path):
            path = Path(path)
        self.path = path

        # search in path
        json_gen = self.path.rglob('*.json')
        for json_file_path in json_gen:
            if json_file_path.name.lower().startswith(TemplateFinder.prefix):
                tool_name = json_file_path.name[len(TemplateFinder.prefix):-5]
                if validateJSON(json_file_path):
                    with open(json_file_path, 'rb') as file:
                        self.templates[tool_name] = json.load(file)
                else:
                    raise ValueError(f"Invalid JSON in {json_file_path}")

    def save(self, path):
        """Save templates to path. One file for each tool in templates"""

        for tool, element_dict in self.templates.items():
            full_path = os.path.join(
                path, TemplateFinder.prefix + tool + '.json')
            with open(full_path, 'w') as file:
                json.dump(element_dict, file, indent=2)

    def set(self, tool, ifc_type: str, parameter, property_set_name, property_name):
        """Internally saves property_set_name ans property_name as lookup source 
        for tool, element and parameter"""

        value = [property_set_name, property_name]
        self.templates.setdefault(tool, {}).setdefault(ifc_type, {}).setdefault('default_ps', {})[parameter] = value

    def find(self, element, property_name):
        """Tries to find the required property
        
        :return: value of property or None if propertyset or property is not available
        :raises: AttributeError if TemplateFinder does not know about given input"""
        if not self.enabled:
            raise AttributeError("Finder is disabled")

        key1 = element.source_tool
        key2 = type(element).__name__
        key3 = 'default_ps'
        key4 = property_name
        try:
            res = self.templates[key1][key2][key3][key4]
        except KeyError:
            raise AttributeError("%s does not know where to look for %s"%(
                self.__class__.__name__, (key1, key2, key3, key4)))

        try:
            pset = ifc2python.get_property_set_by_name(
                res[0], element.ifc, element.ifc_units)
        except AttributeError:
            raise AttributeError("Can't find property as defined by template.")
        return pset.get(res[1])

    def check_tool_template(self, source_tool) \
            -> Generator[Decision, None, None]:
        """Check the given IFC Creation tool and chose the template."""
        if source_tool in self.blacklist:
            logger.warning('No finder template found for %s.', source_tool)
            return

        elif source_tool not in self.templates:
            # no matching template
            logger.warning('No finder template found for {}.'
                           .format(source_tool))

            choices = list(self.templates.keys()) + ['Other']
            choice_checksum = ListDecision.build_checksum(choices)
            decision_source_tool = ListDecision(
                "Please select best matching source tool %s" % source_tool,
                choices=choices,
                default='Other',
                global_key=f'tool_{source_tool}_{choice_checksum}',
                allow_skip=True)
            yield decision_source_tool
            tool_name = decision_source_tool.value

            if not tool_name or tool_name == 'Other':
                self.blacklist.append(source_tool)
                logger.warning('No finder template found for %s.', source_tool)
                return

            self.templates[source_tool] = self.templates[tool_name]
            logger.info("Set {} as finder template for {}."
                        .format(tool_name, source_tool))

    def reset(self):
        self.blacklist.clear()
        self.templates.clear()
        self.load(DEFAULT_PATH)

    @contextlib.contextmanager
    def disable(self):
        temp = self.enabled
        self.enabled = False
        yield
        self.enabled = temp
