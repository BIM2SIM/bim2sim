import ast

from bim2sim.elements.base_elements import Material, ProductBased
from bim2sim.elements.mapping.attribute import Attribute
from bim2sim.kernel.decision import DecisionBunch, ListDecision
from bim2sim.sim_settings import BuildingSimSettings
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements, \
    get_type_building_elements, get_material_templates
from bim2sim.elements.bps_elements import (Layer, LayerSet, Building,
                                           BPSProductWithLayers)
from bim2sim.utilities.types import AttributeDataSource


class EnrichMaterial(ITask):
    """Enriches material properties that were recognized as invalid
    LOD.layers = Medium & Full"""

    reads = ('elements',)

    mapping_templates_bim2sim = {
        "OuterWall": ["OuterWall", "OuterWallDisaggregated"],
        "InnerWall": ["InnerWall", "InnerWallDisaggregated"],
        "Window": ["Window"],
        "Roof": ["Roof"],
        "Floor": ["InnerFloor", "InnerFloorDisaggregated"],
        "GroundFloor": ["GroundFloor", "GroundFloorDisaggregated"],
        "OuterDoor": ["OuterDoor", "OuterDoorDisaggregated"],
        "InnerDoor": ["InnerDoor", "InnerDoorDisaggregated"],
    }

    def __init__(self, playground):
        super().__init__(playground)
        self.layer_sets_added = []
        self.template_materials = {}

    def run(self, elements: dict):
        # TODO change data_source when existing for all overwritten information
        [element_templates, material_template] = \
            yield from self.get_templates(elements)

        if not self.playground.sim_settings.use_construction_templates:
            # TODO #676
            yield from self.validate_ifc_materials_and_layers(elements)
        # check again for layers_and materials, the LOD of
        # layers_and_materials may have changed in previous if-clause
        if self.playground.sim_settings.use_construction_templates:
            self.create_new_layer_sets_and_materials(
                elements, element_templates, material_template)
            for layer_set in self.layer_sets_added:
                elements[layer_set.guid] = layer_set
                for layer in layer_set.layers:
                    elements[layer.guid] = layer
            for material in self.template_materials.values():
                elements[material.guid] = material

    def validate_ifc_materials_and_layers(self, elements: dict):
        """Validate IFC-based layers and materials.

        This function validates IFC-based layers and materials. If invalid
        elements are found, a decision is triggered, if all materials should
        be enriched template-based, or if manual enrichment should be applied
        to the invalid materials. If manual enrichment is selected, all invalid
        attributes are reset to None and NOT_AVAILABLE, so they can be
        enriched by triggered decisions later.

        Args:
            elements: dict with IFC-based elements, layers and materials

        """
        el_layers = filter_elements(elements, 'Layer')
        el_layersets = filter_elements(elements, 'LayerSet')
        el_materials = filter_elements(elements, 'Material')
        el_windows = filter_elements(elements, 'Window')
        elements_with_layersets = []
        elements_layerset_none = []
        element_material_set = {}
        invalid_layersets = []
        invalid_g_values_dict = {}
        invalid_material_dict = {}
        invalid_layer_dict = {}
        # validate elements and their layersets

        # Get all elements with layer sets
        elements_with_layersets = [ele for ele in elements.values() if
                                   isinstance(ele, BPSProductWithLayers)]
        for ele_with_layerset in elements_with_layersets:
            if ele_with_layerset.layerset is None:
                elements_layerset_none.append(ele_with_layerset)
                # todo: implement handling of material_sets
                #  if element.material_set:
                #       element_material_set.update(
                #       {element: element.material_set})
        # for element in elements.values():
        #     if hasattr(element, 'layerset'):
        #         elements_with_layersets.append(element)
        #         if not element.layerset:
        #             elements_layerset_none.append(element)
        #             if hasattr(element, 'material_set'):
        #                 # todo: implement handling of material_sets
        #                 if element.material_set:
        #                     element_material_set.update(
        #                         {element: element.material_set})

        # validate material attributes
        for mat in el_materials:
            mat_inv_atts = {}
            for att in ['density', 'thermal_conduc', 'spec_heat_capacity',
                        'solar_absorp']:
                if getattr(mat, att) is None or getattr(mat, att).m < 1e-4:
                    mat_inv_atts.update({att: getattr(mat, att)})
            if mat_inv_atts:
                invalid_material_dict.update({mat: mat_inv_atts})
        # validate layer thickness, should be larger than 0.1mm
        for ell in el_layers:
            for att in ['thickness']:
                if getattr(ell, att).m < 1e-4:
                    invalid_layer_dict.update(
                        {ell: {att: getattr(ell, att).m}})

        # Since layersets mainly consist out of materials and layers,
        # the layersets are only labeled as invalid if empty layers are
        # found. Other Checks only add warnings, e.g., for incomplete
        # materials or U-values out of range.
        for ls in el_layersets:
            r = []
            if not ls.layers:
                invalid_layersets.append(ls)
                self.logger.warning(f'Failed to process {ls} due to invalid '
                                    'materials layers.')
                continue
            for layer in ls.layers:
                if (layer.thickness
                        and layer.material and layer.material.thermal_conduc):
                    r.append(layer.thickness / layer.material.thermal_conduc)
                else:
                    self.logger.warning(f'Incomplete materials in layerset, '
                                        f'please correct these materials!:'
                                        f'Layerset: {ls}'
                                        f' Thickness: {layer.thickness},'
                                        f' Material: '
                                        f'{layer.material.ifc}')
            if r:
                u = 1 / sum(r)
                if u.m > 30 or u.m < 1e-4:
                    self.logger.warning(f'U-value {u} is out of range for '
                                        f'layerset! [1e-4, 30 W/m²]')
        # check if all windows have a g_value that is not none
        for w in el_windows:
            if w.g_value is None:
                invalid_g_values_dict.update({w: {'g_value': w.g_value}})
            elif w.g_value < 0 or w.g_value > 1:
                invalid_g_values_dict.update({w: {'g_value': w.g_value}})
        if invalid_layersets or elements_layerset_none:
            # todo: these issues cannot be fixed yet so only template based
            #  enrichment is applicable
            material_warning = ListDecision(
                f"\nDetected "
                f"{len(invalid_layersets)} incomplete layersets out of "
                f"{len(el_layersets)} layersets.\n Detected "
                f"{len(elements_layerset_none)} elements without layersets "
                f"out of {len(elements_with_layersets)} elements that should "
                f"have layersets.\nHowever, {len(element_material_set)} have "
                f"material_sets instead.\n\n Unfortunately, this cannot be "
                f"fixed. Please add layers to all layersets and layersets to "
                f"all IfcProducts if you want to continue using IFC "
                f"materials. How should we proceed?",
                choices=['Abort', 'Full template-based enrichment',
                         'Continue anyways, program may crash'],
                default='Full template-based enrichment',
                global_key=f'material_warning_abort',
                allow_skip=True)
            yield DecisionBunch([material_warning])
            if material_warning.value == 'Abort':
                raise ValueError
            elif material_warning.value == 'Full template-based enrichment':
                self.playground.sim_settings.use_construction_templates = True
                return
            else:
                pass

            # todo: reset only the invalid layerset to be enriched with
            #  template-based values
            # todo: add implementation for material_sets (not supported by
            #  PluginEnergyPlus).
            # todo: Convert material_sets to layersets?
        enrichment_choice = ListDecision(
            f"Detected {len(invalid_material_dict)} out of "
            f"{len(el_materials)} material attributes as invalid."
            f"\nDetected {len(invalid_layer_dict)} out of "
            f"{len(el_layers)} layer thicknesses as invalid.\nDetected "
            f"{len(invalid_g_values_dict)} out of {len(el_windows)} g_values "
            f"as "
            f"invalid.\n"
            f"Do you want to enrich these attributes manually or do you want "
            f"to run a full template-based enrichment ignoring the available "
            f"IFC material data?",
            choices=['Manual Enrichment', 'Template-based Enrichment'],
            default='Manual Enrichment',
            global_key=f'enrichment_for_ifc_materials',
            allow_skip=True)
        yield DecisionBunch([enrichment_choice])
        if enrichment_choice.value == 'Manual Enrichment':
            # ensure that all invalid attributes are set to None such that
            # they can be manually set once requested.
            for window, attr in invalid_g_values_dict.items():
                for att in attr.keys():
                    window.reset(att)
            for mat, attr in invalid_material_dict.items():
                for att in attr.keys():
                    mat.reset(att)
            for layer, attr in invalid_layer_dict.items():
                for att in attr.keys():
                    layer.reset(att)
            # for ls, attr in invalid_layersets_dict.items():
            #     for att in attr.keys():
            #         ls.reset(att)
        else:
            # template based enrichment
            # set LOD for layers and materials to low.
            self.playground.sim_settings.use_construction_templates = True

    def create_new_layer_sets_and_materials(
            self, elements: dict,
            element_templates: dict,
            material_template: dict):
        """Create a new layer set including layers and materials.

        This creates a completely new layer set, including the relevant layers
        and materials. Materials are only created once, even if they occur in
        multiple layer sets/layers.
        Additionally, some information on element level are overwritten with
        data from the templates, like inner_convection etc.
        """
        # TODO multi building support would require to have relations
        #  between each bim2sim element and its bim2sim Building
        #  instance. For now we always take the first building.
        element_template = element_templates[
            list(element_templates.keys())[0]]
        for template_name, ele_types in (
                self.mapping_templates_bim2sim.items()):
            layer_set = self.create_layer_set_from_template(
                element_template[template_name], material_template)
            ele_enrichment_data = self.enrich_element_data_from_template(
                element_template[template_name])
            elements_to_enrich = []
            for ele_type in ele_types:
                elements_to_enrich.extend(filter_elements(elements, ele_type))
            for element in elements_to_enrich:
                # set layer_set
                element.layerset = layer_set
                # TODO set layer_set also to not disaggregated parent, t.b.d.
                # if hasattr(element, "disagg_parent"):
                #     element.disagg_parent.layerset = layer_set
                # overwrite element level attributes like inner_convection
                for att, value in ele_enrichment_data.items():
                    if hasattr(element, att):
                        setattr(element, att, value)
                # overwrite thickness/width of element with enriched layer_set
                # thickness
                if hasattr(element, "width"):
                    element.width = (
                        layer_set.thickness, AttributeDataSource.enrichment)

    @staticmethod
    def enrich_element_data_from_template(element_template: dict) -> dict:
        """Get all element level enrichment data from templates."""
        ele_enrichment_data = {key: info for key, info in
                               element_template.items()
                               if type(info) not in [list, dict]}
        return ele_enrichment_data

    def create_layer_set_from_template(self, element_template: dict,
                                       material_template: dict) -> LayerSet:
        """Create layer set from template including layers and materials."""
        layer_set = LayerSet()
        for layer_template in element_template['layer'].values():
            layer = Layer()
            layer.thickness = layer_template['thickness']
            material_name = layer_template['material']['name']
            if material_name in self.template_materials:
                material = self.template_materials[material_name]
            else:
                material = self.create_material_from_template(
                    material_template[material_name])
                self.template_materials[material_name] = material
            material.parents.append(layer)
            layer.material = material
            layer.to_layerset.append(layer_set)
            layer_set.layers.append(layer)
        self.layer_sets_added.append(layer_set)
        return layer_set

    @staticmethod
    def create_material_from_template(material_template: dict) -> Material:
        """Creates a material from template."""
        material = Material()
        material.name = material_template['material']
        material.density = (
            material_template['density'], AttributeDataSource.enrichment)
        material.spec_heat_capacity = (
            material_template['heat_capac'], AttributeDataSource.enrichment)
        material.thermal_conduc = (
            material_template['thermal_conduc'],
            AttributeDataSource.enrichment)
        material.solar_absorp = (
            material_template['solar_absorp'], AttributeDataSource.enrichment)
        return material

    def get_templates(self, elements: dict) -> object:
        """Get templates for elements and materials.

        Args:
            elements: dict[guid: element] of bim2sim elements
        Returns:
            element_templates (dict): Holds enrichment templates for each
             Building with layer set information and material reference for
              different BPSProducts
            material_templates (dict): Holds information about physical
             attributes for each material referenced in the element_templates
        """
        buildings = filter_elements(elements, Building)
        element_templates = yield from self.get_templates_for_buildings(
            buildings, self.playground.sim_settings)
        if not element_templates:
            self.logger.warning(
                "Tried to run enrichment for layers structure and materials, "
                "but no fitting templates were found. "
                "Please check your settings.")
            return elements,
        material_templates = self.get_material_templates()
        return element_templates, material_templates

    @staticmethod
    def get_material_templates(attrs: dict = None) -> dict:
        """get dict with the material templates and its respective
        attributes"""
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

    def get_templates_for_buildings(
            self, buildings: list, sim_settings: BuildingSimSettings) -> dict:
        """Return template for each building based on year of construction."""

        def _get_template_for_year(
                year_of_construction,
                construction_type,
                windows_construction_type):
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
                            template_options = element_templates[element_type][
                                i]
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
                            # for the given year.
                            new_window_construction_type = \
                                list(template_options.keys())[-1]
                            self.logger.warning(
                                f"The window_construction_type"
                                f" {windows_construction_type} is not "
                                f"available for year_of_construction "
                                f"{year_of_construction}. Using the "
                                f"window_construction_type "
                                f"{new_window_construction_type} instead.")
                            bldg_template[element_type] = \
                                template_options[new_window_construction_type]
                    else:
                        bldg_template[element_type] = \
                            template_options[construction_type]
            return bldg_template

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
            templates[building] = _get_template_for_year(
                year_of_construction, construction_type,
                windows_construction_type)
        return templates
