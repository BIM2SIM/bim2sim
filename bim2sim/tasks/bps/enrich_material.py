import ast
import re

from bim2sim.kernel.decision import ListDecision, DecisionBunch
from bim2sim.elements.base_elements import Material
from bim2sim.elements.bps_elements import Layer, LayerSet, Building
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import get_material_templates, \
    translate_deep, filter_elements, get_type_building_elements
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
   from bim2sim.sim_settings import BaseSimSettings, TEASERSimSettings

class EnrichMaterial(ITask):
    """Enriches material properties that were recognized as invalid
    LOD.layers = Medium & Full"""

    reads = ('elements', 'invalid',)
    touches = ('elements',)

    def __init__(self, playground):
        super().__init__(playground)
        self.enriched_elements = {}
        self.template_layer_set = {}
        self.template_materials = {}

    def run(self, elements: dict, invalid: dict):
        buildings = filter_elements(elements, Building)
        templates = yield from self.get_templates_for_buildings(
            buildings, self.playground.sim_settings)
        if not templates:
            self.logger.warning(
                "Tried to run enrichment for layers structure and materials, "
                "but no fitting templates were found. "
                "Please check your settings.")
            return elements,
        resumed = self.get_resumed_material_templates()
        for invalid_inst in invalid.values():
            yield from self.enrich_invalid_element(invalid_inst, resumed,
                                                   templates)
        self.logger.info("enriched %d invalid materials",
                         len(self.enriched_elements))
        elements = self.update_elements(elements, self.enriched_elements)

        return elements,

    def get_templates_for_buildings(self, buildings: list, sim_settings: TEASERSimSettings):
        """get templates for building"""
        templates = {}
        construction_type = sim_settings.construction_class_walls
        windows_construction_type = sim_settings.construction_class_windows
        if not buildings:
            raise ValueError(
                "No buildings found, without a building no template can be"
                " assigned and enrichment can't proceed.")
        for building in buildings:
            if sim_settings.year_of_construction_overwrite:
                building.year_of_construction = \
                    int(sim_settings.year_of_construction_overwrite)
            if not building.year_of_construction:
                year_decision = building.request('year_of_construction')
                yield DecisionBunch([year_decision])
            year_of_construction = int(building.year_of_construction.m)
            templates[building] = self.get_template_for_year(
                year_of_construction, construction_type,
                windows_construction_type)
        return templates

    def get_template_for_year(self, year_of_construction: int, construction_type: str,
                              windows_construction_type: str):
        element_templates = get_type_building_elements()
        bldg_template = {}
        for element_type, years_dict in element_templates.items():
            if len(years_dict) == 1:
                template_options = years_dict[list(years_dict.keys())[0]]
            else:
                template_options = None
                for i, template in years_dict.items():
                    years = ast.literal_eval(i)
                    if years[0] <= year_of_construction <= years[1]:
                        template_options = element_templates[element_type][i]
                        break
            if len(template_options) == 1:
                bldg_template[element_type] = \
                    template_options[list(template_options.keys())[0]]
            else:
                if element_type == 'Window':
                    try:
                        bldg_template[element_type] = \
                            template_options[windows_construction_type]
                    except KeyError:
                        # select last available window construction type if
                        # the selected/default window type is not available
                        # for the given year. The last construction type is
                        # selected, since the first construction type may be a
                        # single pane wood frame window and should not be
                        # used as new default construction.
                        new_window_construction_type = \
                            list(template_options.keys())[-1]
                        self.logger.warning(
                            "The window_construction_type %s is not available "
                            "for year_of_construction %i. Using the "
                            "window_construction_type %s instead.",
                            windows_construction_type, year_of_construction,
                            new_window_construction_type)
                        bldg_template[element_type] = \
                            template_options[new_window_construction_type]
                else:
                    bldg_template[element_type] = \
                        template_options[construction_type]
        return bldg_template

    def enrich_invalid_element(self, invalid_element: Any, resumed: dict, templates: dict):
        """enrich invalid element"""
        if type(invalid_element) is Layer:
            enriched_element = yield from self.enrich_layer(invalid_element,
                                                             resumed,
                                                             templates)
            self.enriched_elements[invalid_element.guid] = enriched_element

        elif type(invalid_element) is LayerSet:
            enriched_element = self.enrich_layer_set(invalid_element, resumed,
                                                      templates)
            self.enriched_elements[invalid_element.guid] = enriched_element
        else:
            self.enrich_element(invalid_element, resumed, templates)

    def enrich_layer(self, invalid_layer: Any, resumed: dict, templates: dict):
        """enrich layer"""
        invalid_layer_sets = [layer_set for layer_set in
                              invalid_layer.to_layerset]
        type_invalid_elements = self.get_invalid_elements_type(
            invalid_layer_sets)
        if len(type_invalid_elements) == 1:
            specific_element_template = templates[list(
                templates.keys())[0]][type_invalid_elements[0]]
            resumed_names = list(set(
                layer['material']['name'] for layer in
                specific_element_template['layer'].values()))
        else:
            resumed_names = list(resumed.keys())
        layer = Layer()
        layer.thickness = invalid_layer.thickness
        material_name = invalid_layer.material.name
        if material_name in self.template_materials:
            material = self.template_materials[material_name]
        else:
            specific_template = yield from self.get_material_template(
                material_name, resumed_names, resumed)
            material = self.create_material_from_template(specific_template)
            self.template_materials[material_name] = material
        material.parents.append(layer)
        layer.material = material
        for layer_set in invalid_layer_sets:
            layer.to_layerset.append(layer_set)
            layer_set.layers[layer_set.layers.index(invalid_layer)] = layer
        return layer

    @staticmethod
    def get_invalid_elements_type(layer_sets):
        """get invalid elements"""
        invalid_elements = []
        for layer_set in layer_sets:
            for parent in layer_set.parents:
                element_type = type(parent).__name__
                if element_type not in invalid_elements:
                    invalid_elements.append(element_type)
        return invalid_elements

    @classmethod
    def get_material_template(cls, material_name: str, resumed_names: list,
                              resumed: dict) -> [list, str]:
        """get list of matching materials
        if material has no matches, more common name necessary"""
        material = re.sub(r'[^\w]*?[0-9]', '', material_name)
        material_options = cls.get_matches_list(
            material, resumed_names) if material_name else []
        if len(material_options) == 1:
            selected_material = material_options[0]
        else:
            selected_material = yield from cls.material_search(material_options,
                                                               material_name)
        return resumed[selected_material]

    def enrich_layer_set(self, invalid_element: Any, resumed: dict, templates: dict):
        """enrich layer set"""
        type_invalid_elements = self.get_invalid_elements_type(
            [invalid_element])[0]
        layer_set, add_enrichment = self.layer_set_search(
            type_invalid_elements, templates, resumed)
        for parent in invalid_element.parents:
            layer_set.parents.append(parent)
            parent.layerset = layer_set
            self.additional_element_enrichment(parent,
                                                add_enrichment)
        return layer_set

    def enrich_element(self, invalid_element: Any, resumed: dict, templates: dict):
        """enrich element"""
        type_invalid_element = type(invalid_element).__name__
        layer_set, add_enrichment = self.layer_set_search(type_invalid_element,
                                                          templates, resumed)
        layer_set.parents.append(invalid_element)
        invalid_element.layerset = layer_set
        self.additional_element_enrichment(invalid_element, add_enrichment)

    def layer_set_search(self, type_invalid_element: Any, templates: dict, resumed: dict):
        """search for layer set"""

        if type_invalid_element in self.template_layer_set:
            layer_set, add_enrichment = self.template_layer_set[
                type_invalid_element].values()
        else:
            specific_template = templates[
                list(templates.keys())[0]][type_invalid_element]
            add_enrichment = {key: info for key, info in
                              specific_template.items()
                              if type(info) not in [list, dict]}
            layer_set = self.create_layer_set_from_template(resumed,
                                                            specific_template)
            self.template_layer_set[type_invalid_element] = {
                'layer_set': layer_set,
                'add_enrichment': add_enrichment}
        return layer_set, add_enrichment

    @staticmethod
    def additional_element_enrichment(invalid_element: Any, add_enrichment: list):
        for key in add_enrichment:
            if hasattr(invalid_element, key):
                setattr(invalid_element, key, add_enrichment[key])

    def create_layer_set_from_template(self, resumed: dict, template: dict):
        """create layer set from template"""
        layer_set = LayerSet()
        for layer_template in template['layer'].values():
            layer = Layer()
            layer.thickness = layer_template['thickness']
            material_name = layer_template['material']['name']
            if material_name in self.template_materials:
                material = self.template_materials[material_name]
            else:
                material = self.create_material_from_template(
                    resumed[material_name])
                self.template_materials[material_name] = material
            material.parents.append(layer)
            layer.material = material
            layer.to_layerset.append(layer_set)
            layer_set.layers.append(layer)

        return layer_set

    @staticmethod
    def create_material_from_template(material_template: dict):
        material = Material()
        material.name = material_template['material']
        material.density = material_template['density']
        material.spec_heat_capacity = material_template['heat_capac']
        material.thermal_conduc = material_template['thermal_conduc']
        material.solar_absorp = material_template['solar_absorp']
        return material

    def update_elements(self, elements: dict, enriched_elements: dict):
        # add new created materials to elements
        for mat in self.template_materials.values():
            elements[mat.guid] = mat
        for guid, new_element in enriched_elements.items():
            old_element = elements[guid]
            if type(old_element) is Layer:
                old_material = old_element.material
                if old_material.guid in elements:
                    del elements[old_material.guid]
                new_material = new_element.material
                elements[new_material.guid] = new_material
            if type(old_element) is LayerSet:
                for old_layer in old_element.layers:
                    old_material = old_layer.material
                    if old_material.guid in elements:
                        del elements[old_material.guid]
                    if old_layer.guid in elements:
                        del elements[old_layer.guid]
                for new_layer in new_element.layers:
                    new_material = new_layer.material
                    elements[new_material.guid] = new_material
                    elements[new_layer.guid] = new_layer
            if guid in elements:
                del elements[guid]
            elements[new_element.guid] = new_element
        return elements

    @staticmethod
    def get_resumed_material_templates(attrs: dict = None) -> dict:
        """get dict with the material templates and its respective attributes"""
        material_templates = get_material_templates()
        resumed = {}
        for k in material_templates:
            resumed[material_templates[k]['name']] = {}
            if attrs is not None:
                for attr in attrs:
                    if attr == 'thickness':
                        resumed[material_templates[k]['name']][attr] = \
                            material_templates[k]['thickness_default']
                    else:
                        resumed[material_templates[k]['name']][attr] = \
                            material_templates[k][attr]
            else:
                for attr in material_templates[k]:
                    if attr == 'thickness_default':
                        resumed[material_templates[k]['name']]['thickness'] = \
                            material_templates[k][attr]
                    elif attr == 'name':
                        resumed[material_templates[k]['name']]['material'] = \
                            material_templates[k][attr]
                    elif attr == 'thickness_list':
                        continue
                    else:
                        resumed[material_templates[k]['name']][attr] = \
                            material_templates[k][attr]
        return resumed

    @staticmethod
    def get_matches_list(search_words: str, search_list: list) -> list:
        """get patterns for a material name in both english and original language,
        and get afterwards the related elements from list"""

        material_ref = []

        if type(search_words) is str:
            pattern_material = search_words.split()
            translated = translate_deep(search_words)
            if translated:
                pattern_material.extend(translated.split())
            for i in pattern_material:
                material_ref.append(
                    re.compile('(.*?)%s' % i, flags=re.IGNORECASE))

        material_options = []
        for ref in material_ref:
            for mat in search_list:
                if ref.match(mat):
                    if mat not in material_options:
                        material_options.append(mat)
        if len(material_options) == 0:
            return search_list
        return material_options

    @staticmethod
    def material_search(material_options: list, material_input: str):
        material_selection = ListDecision(
            "Multiple possibilities found for material \"%s\"\n"
            "Enter name from given list" % material_input,
            choices=list(material_options),
            global_key='_Material_%s_search' % material_input,
            allow_skip=True,
            live_search=True)
        yield DecisionBunch([material_selection])
        return material_selection.value
