"""Finders are used to get properties from ifc which do not meet IFC standards.

Currently, we implemented only one Finder, the TemplateFinder.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
from pathlib import Path
from typing import Generator, TYPE_CHECKING, Union

from ifcopenshell import file, entity_instance

import bim2sim
from bim2sim.kernel.decision import ListDecision, Decision, DecisionBunch
from bim2sim.elements.mapping import ifc2python
from bim2sim.utilities.common_functions import validateJSON

if TYPE_CHECKING:
    from bim2sim.elements.base_elements import IFCBased

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

    The TemplateFinder allows to find information (properties) which are stored
    in the IFC file but not on the position the IFC schema specifies. To find
    these information we implemented templates in form of .json files for the
    most relevant IFC exporter tools. These templates hold the information where
    to look in the IFC. E.g. Revit stores length of IfcPipeSegment in
    PropertySet 'Abmessungen' with name 'Länge'.
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
        self.source_tools = []
        self.default_source_tool = None

    def load(self, path: Union[str, Path]):
        """Loads jsontemplates from given path.

         Each *.json file is loaded into the templates dictionary with tool
         name as key and converted json dictionary as value.

         Args:
             path: str or Path where the templates are stored.
         Raises:
             ValueError: if an invalid json is loaded.
         """
        if not isinstance(path, Path):
            path = Path(path)
        self.path = path

        # search in path
        json_gen = self.path.rglob('*.json')
        for json_file_path in json_gen:
            if json_file_path.name.lower().startswith(TemplateFinder.prefix):
                tool_name = json_file_path.stem[len(TemplateFinder.prefix):]
                if validateJSON(json_file_path):
                    with open(json_file_path, 'rb') as json_file:
                        self.templates[tool_name] = json.load(json_file)
                else:
                    raise ValueError(f"Invalid JSON in {json_file_path}")

    def save(self, path):
        """Save templates to path, one file for each tool in templates.

        Allows to save the created templates to path.

        Args:
            path: str or Path where the templates are stored.
        """

        for tool, element_dict in self.templates.items():
            full_path = os.path.join(
                path, TemplateFinder.prefix + tool + '.json')
            with open(full_path, 'w') as file:
                json.dump(element_dict, file, indent=2)

    def set(
            self, tool, ifc_type: str, parameter, property_set_name,
            property_name):
        """Internally saves property_set_name as property_name.

        This deals as a lookup source  for tool, element and parameter"""
        value = [property_set_name, property_name]
        self.templates.setdefault(tool, {}).setdefault(ifc_type, {}).setdefault(
            'default_ps', {})[parameter] = value

    def find(self, element: IFCBased, property_name: str):
        """Tries to find the required property.

        Args:
            element: IFCBased bim2sim element
            property_name: str with name of the property
        Returns:
            value of property or None if propertyset or property is not
            available.
        Raises:
            AttributeError if TemplateFinder does not know about given input
        """
        if not self.enabled:
            raise AttributeError("Finder is disabled")

        self._get_elements_source_tool(element)
        if not element.source_tool:
            return None
        key1 = element.source_tool.templ_name
        key2 = type(element).__name__
        key3 = 'default_ps'
        key4 = property_name
        try:
            res = self.templates[key1][key2][key3][key4]
        except KeyError:
            raise AttributeError("%s does not know where to look for %s" % (
                self.__class__.__name__, (key1, key2, key3, key4)))

        try:
            # get value from templates
            for res_ele in (
                    res if all(isinstance(r, list) for r in res[:2]) else [
                        res]):
                pset = ifc2python.get_property_set_by_name(res_ele[0],
                                                           element.ifc,
                                                           element.ifc_units)
                val = pset.get(res_ele[1])
                if val is not None:
                    return val
            return None
        except AttributeError:
            raise AttributeError("Can't find property as defined by template.")

    def _set_templates_by_tools(self, source_tool: SourceTool) \
            -> Generator[Decision, None, None]:
        """Check the given IFC Creation tool and choose the template.

        If no template exists for the given source_tool a decision is triggered
        if their another of the existing should be chosen. If yes the selected
        template is used for the given source_tool as well.

        Args:
             source_tool: str of ApplicationFullName of the IfcApplication
         Yields:
             decision_source_tool: ListDecision which existing tool template
             might fit
        """
        if source_tool.full_name in self.blacklist:
            logger.warning(f'No finder template found for '
                           f'{source_tool.full_name}')
            return

        for templ in self.templates.items():
            templ_name = templ[0]
            temp_tool_names = [templ_name]
            try:
                temp_tool_names += templ[-1]["Identification"]["tool_names"]
            except KeyError:
                logger.warning(
                    f'No Identification defined in template for {templ_name}')
            # generate all potential fitting names based on content of template
            tool_names = []
            for tool_name in temp_tool_names:
                # Revit stores version and language, so generate possible names
                if any(x in tool_name for x in ["%lang", "%v"]):
                    if "%v" in tool_name:
                        tool_name = tool_name.replace(
                            "%v", source_tool.version)
                    if "%lang" in tool_name:
                        langs = templ[-1]["Identification"]["languages"]
                        for lang in langs:
                            tool_names.append(tool_name.replace("%lang", lang))
                else:
                    tool_names.append(tool_name)

            pot_names = list(map(lambda tool: tool.lower(), tool_names))

            if any(name in pot_names for name in
                   [source_tool.full_name.lower(), source_tool.ident.lower()]):
                source_tool.templ_name = templ_name
                break

        if not source_tool.templ_name:
            # no matching template
            logger.warning('No finder template found for {}.'
                           .format(source_tool.full_name))

            choices = list(self.templates.keys()) + ['Other']
            choice_checksum = ListDecision.build_checksum(choices)
            decision_source_tool = ListDecision(
                f"Please select best matching source tool for "
                f"{source_tool.full_name} with version: {source_tool.version} ",
                choices=choices,
                default='Other',
                global_key=f'tool_{source_tool.full_name}_{source_tool.ifc}_'
                           f'{choice_checksum}',
                allow_skip=True)
            yield decision_source_tool
            tool_name = decision_source_tool.value

            if not tool_name or tool_name == 'Other':
                self.blacklist.append(source_tool.full_name)
                logger.warning('No finder template found for %s.', source_tool)
                return
            else:
                source_tool.templ_name = tool_name

        logger.info(f'Found matching template for IfcApplication with'
                    f'full name {source_tool.full_name} in template '
                    f'{source_tool.templ_name}')

    def initialize(self, ifc: file):
        """Find fitting templates for given IFC and set default source tool.

         Checks the IfcApplications in the IFC File against the existing
         templates of the finder. If multiple IfcApplications with existing
         templates are found a decision is triggered which template should be
         used by default for template lookup to reduce number of decisions
         during process.
         This must be called from inside a tasks because it holds decisions.

         Args:
             ifc: ifcopenshell instance of ifc file
         """
        # use finder to get correct export tool
        source_tools = []
        for app in ifc.by_type('IfcApplication'):
            source_tool = SourceTool(app)
            source_tools.append(source_tool)
        # Filter source tools as there might be duplications in IFC
        unique_source_tools = self.remove_duplicate_source_tools(source_tools)
        for unique_source_tool in unique_source_tools:
            self.source_tools.append(unique_source_tool)
            for decision in self._set_templates_by_tools(unique_source_tool):
                yield DecisionBunch([decision])
        # Only take source tools with existing template into account
        tools = [tool.templ_name for tool in self.source_tools if
                 tool.templ_name]
        if len(tools) == 1:
            self.default_source_tool = self.source_tools[0]
        elif len(tools) > 1:
            choice_checksum = ListDecision.build_checksum(tools)
            decision_source_tool = ListDecision(
                "Multiple source tools found, please decide which one to "
                "use as fallback for template based searches if no"
                " IfcOwnerHistory exists.",
                choices=tools,
                global_key=f'tool_{choice_checksum}',
                allow_skip=True)
            yield DecisionBunch([decision_source_tool])
            if decision_source_tool.value:
                self.default_source_tool = \
                    decision_source_tool.value
            else:
                logger.info(f"No decision for default source tool, taking "
                            f"last source tool found: "
                            f"{self.source_tools[-1]}")
                self.default_source_tool = self.source_tools[-1]
        else:
            logger.info(f"No template could be found for one of the following "
                        f"tools: "
                        f"{[tool.full_name for tool in self.source_tools]}")
            self.default_source_tool = None

    def _get_elements_source_tool(self, element: IFCBased):
        """Get source_tool for specific element

        As IfcOwnerHistory is only an optional attribute we can't rely on that
        ,and it's formation about the used application exists. As fallback,
        we use the default source tool which is selected in
        set_source_tool_templates.

        Args:
            element: IFCBased bim2sim element
        """
        if element.ifc.OwnerHistory:
            full_name = element.ifc.OwnerHistory.OwningApplication. \
                ApplicationFullName
            for source_tool in self.source_tools:
                if source_tool.full_name == full_name:
                    element.source_tool = source_tool
                    return
        else:
            element.source_tool = self.default_source_tool

    @staticmethod
    def remove_duplicate_source_tools(source_tools: list) -> list:
        """Removes duplicates from source_tools list.

        Filters a list of SourceTool objects to retain only those with unique
        combinations of 'version', 'full_name', and 'ident' attributes.

        Args:
            source_tools (list): A list of SourceTool objects to be filtered.

        Returns:
            list: A new list containing SourceTool objects with unique
            combinations of 'version', 'full_name', and 'ident'.

        Example:
            Assuming source_tools is a list of SourceTool objects,
            filtered_tools = filter_source_tools(source_tools)
        """
        unique_tools = []
        seen_combinations = set()

        for tool in source_tools:
            tool_info = (tool.version, tool.full_name, tool.ident)

            # Check if the combination of version, full_name,
            # and ident is unique
            if tool_info not in seen_combinations:
                seen_combinations.add(tool_info)
                unique_tools.append(tool)

        return unique_tools

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


class SourceTool:
    def __init__(self, app_ifc: entity_instance):
        """Represents the author software that created the IFC file.

        Gets the basic information about the tool needed to identify which
        template should be searched. One IFC might have multiple SourceTools.

        Args:
            app_ifc: entity_instance of IfcApplication
        """
        self.ifc = app_ifc
        self.version = self.ifc.Version
        self.full_name = self.ifc.ApplicationFullName
        self.ident = self.ifc.ApplicationIdentifier
        self.developer = self.ifc.ApplicationDeveloper
        self.templ_name = None

    def __repr__(self):
        return "<%s (Name: %s)>" % (self.__class__.__name__, self.full_name)
