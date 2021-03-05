"""Finders are used to get properties from ifc which do not use the default PropertySets"""

import os
import json
import hashlib
import contextlib
from pathlib import Path

import bim2sim
from bim2sim.kernel import ifc2python
from bim2sim.decision import ListDecision, Decision


DEFAULT_PATH = Path(bim2sim.__file__).parent / 'assets/finder'


class Finder:

    def find(self, element, property_name):
        raise NotImplementedError()

    def reset(self):
        """Reset finder instance"""
        raise NotImplementedError()


class TemplateFinder(Finder):
    """TemplateFinder works like a multi key diktonary.

    Use it for tool dependent property usage. 
    E.g. Revit stores length of IfcPipeSegment in PropertySet 'Abmessungen' with name 'Länge'
    """
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
        """loads templates from given path. Each *.json file is interpretet as tool with name *
        also searches default templates"""
        self.path = path

        # search in path
        for filename in os.listdir(path):
            if filename.lower().startswith(TemplateFinder.prefix) and filename.lower().endswith(".json"):
                tool = filename[len(TemplateFinder.prefix):-5]
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
        if not self.enabled:
            raise AttributeError("Finder is disabled")

        self.check_template(element)

        key1 = element.source_tool
        key2 = type(element).__name__
        key3 = 'default_ps'
        key4 = property_name
        try:
            res = self.templates[key1][key2][key3][key4]
            if type(element).__name__ == 'ThermalZone':
                print('Test')
        except KeyError:
            raise AttributeError("%s does not know where to look for %s"%(
                self.__class__.__name__, (key1, key2, key3, key4)))

        try:
            pset = ifc2python.get_Property_Set(res[0], element.ifc)
            if type(element).__name__ == 'ThermalZone':
                print('Test')
        except AttributeError:
            raise AttributeError("Can't find property as defined by template.")
        return pset.get(res[1])

    def check_template(self, element):
        """Check the given IFC Creation tool and chose the template."""
        if element.source_tool in self.blacklist:
            raise AttributeError('No finder template found for {}.'.format(element.source_tool))

        elif element.source_tool not in self.templates:
            # no matching template
            element.logger.warning('No finder template found for {}.'.format(element.source_tool))

            choices = list(self.templates.keys()) + ['Other']
            decision_source_tool = ListDecision(
                "Please select best matching source tool %s" % element.source_tool,
                choices=choices,
                default='Other',
                global_key='tool_' + hashlib.md5(''.join(choices).encode('utf-8')).hexdigest(),
                allow_skip=True, allow_load=True, allow_save=True,
                collect=False, quick_decide=False)
            tool_name = decision_source_tool.decide()

            if not tool_name or tool_name == 'Other':
                self.blacklist.append(element.source_tool)
                raise AttributeError('No finder template found for {}.'.format(element.source_tool))

            self.templates[element.source_tool] = self.templates[tool_name]
            element.logger.info("Set {} as finder template for {}.".format(tool_name, element.source_tool))

    def reset(self):
        self.blacklist.clear()
        self.templates.clear()
        self.load(self.path)

    @contextlib.contextmanager
    def disable(self):
        temp = self.enabled
        self.enabled = False
        yield
        self.enabled = temp
