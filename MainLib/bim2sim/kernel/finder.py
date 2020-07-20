"""Finders are used to get properties from ifc which do not use the default PropertySets"""

import os
import json
from pathlib import Path

import bim2sim
from bim2sim.kernel import ifc2python


DEFAULT_PATH = Path(bim2sim.__file__).parent / 'assets/finder'


class Finder:

    def find(self, element, property_name):
        raise NotImplementedError()


class TemplateFinder(Finder):
    """TemplateFinder works like a multi key diktonary.

    Use it for tool dependent property usage. 
    E.g. Revit stores length of IfcPipeSegment in PropertySet 'Abmessungen' with name 'Länge'
    """
    prefix = "template_"

    def __init__(self):
        super().__init__()
        #{tool: {Element class name: {parameter: (Pset name, property name)}}}
        self.templates = {}
        self.blacklist = []

    def load(self, path):
        """loads templates from given path. Each *.json file is interpretet as tool with name *
        also searches default templates"""

        # search in project folder
        for filename in os.listdir(path):
            if filename.lower().startswith(TemplateFinder.prefix) and filename.lower().endswith(".json"):
                tool = filename[len(TemplateFinder.prefix):-5]
                try:
                    with open(os.path.join(path, filename)) as file:
                        self.templates[tool] = json.load(file)
                except (IOError, json.JSONDecodeError) as ex:
                    continue

        # search for default finder templates
        for filename in os.listdir(DEFAULT_PATH):
            if filename.lower().startswith(TemplateFinder.prefix) and filename.lower().endswith(".json"):
                tool = filename[len(TemplateFinder.prefix):-5]
                if tool in self.templates:
                    # not overwrite project templates
                    continue
                try:
                    with open(os.path.join(path, filename)) as file:
                        self.templates[tool] = json.load(file)
                except (IOError, json.JSONDecodeError) as ex:
                    continue

    def save(self, path):
        """Save templates to path. One file for each tool in templates"""

        for tool, element_dict in self.templates.items():
            full_path = os.path.join(path, TemplateFinder.prefix + tool + '.json')
            with open(full_path, 'w') as file:
                json.dump(element_dict, file, indent=2)

    def set(self, tool, element, parameter, property_set_name, property_name):
        """Internally saves property_set_name ans property_name as lookup source 
        for tool, element and parameter"""

        if isinstance(element, str):
            element_name = element  # string
        elif isinstance(element.__class__, type):
            element_name = element.ifc_type  # class
        else:
            element_name = element.__class__.ifc_type  # instance

        value = [property_set_name, property_name]
        self.templates.setdefault(tool, {}).setdefault(element_name, {}).setdefault('default_ps', {})[parameter] = value

    def find(self, element, property_name):
        """Tries to find the required property
        
        :return: value of property or None if propertyset or property is not available
        :raises: AttributeError if TemplateFinder does not know about given input"""

        self.check_template(element)

        key1 = element.source_tool
        key2 = element.ifc_type
        key3 = 'default_ps'
        key4 = property_name
        try:
            res = self.templates[key1][key2][key3][key4]
        except KeyError:
            raise AttributeError("%s does not know where to look for %s"%(
                self.__class__.__name__, (key1, key2, key3, key4)))

        try:
            pset = ifc2python.get_Property_Set(res[0], element.ifc)
        except AttributeError:
            raise AttributeError("Can't find property as defined by template.")
        return pset.get(res[1])

    def check_template(self, element):
        """Check the given IFC Creation tool and choos the template."""
        if element.source_tool in self.blacklist:
            raise AttributeError('No finder template found for {}.'.format(element.source_tool))
        elif element.source_tool not in self.templates:
            # try to set similar template
            if element.source_tool.lower().startswith('Autodesk'.lower()):
                tool_name = 'Autodesk Revit 2019 (DEU)'
            elif element.source_tool.lower().startswith('ARCHICAD'.lower()):
                tool_name = 'ARCHICAD-64'
            else:
                # no matching template
                element.logger.warning('No finder template found for {}.'.format(element.source_tool))
                self.blacklist.append(element.source_tool)
                raise AttributeError('No finder template found for {}.'.format(element.source_tool))

            self.templates[element.source_tool] = self.templates[tool_name]
            element.logger.info("Set {} as finder template for {}.".format(tool_name, element.source_tool))

