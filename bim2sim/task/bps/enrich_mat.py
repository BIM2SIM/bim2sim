import re

from bim2sim.task.base import ITask
from bim2sim.decision import BoolDecision, ListDecision, RealDecision, \
    StringDecision, DecisionBunch
from bim2sim.workflow import LOD
from functools import partial
from bim2sim.utilities.common_functions import get_material_templates, \
    translate_deep
from bim2sim.kernel.units import ureg
from bim2sim.workflow import Workflow
from bim2sim.kernel.elements.bps import Layer


class EnrichMaterial(ITask):
    """Enriches material properties that were recognized as invalid
    LOD.layers = Medium & Full"""

    reads = ('instances', 'invalid_materials',)
    touches = ('enriched_materials',)

    def __init__(self):
        super().__init__()
        self.material_selected = {}
        self.enriched_materials = []
        pass

    def run(self, workflow: Workflow, instances: dict, invalid_materials: dict):
        if workflow.layers is not LOD.low:
            resumed = self.get_resumed_material_templates()
            for instance_guid, layers in invalid_materials.items():
                for layer in layers:
                    yield from self.set_material_properties(layer, resumed)
                    self.enriched_materials.append(layer)
            self.logger.info("enriched %d invalid materials",
                             len(self.enriched_materials))

        return self.enriched_materials,

    def set_material_properties(self, layer: Layer, resumed):
        """enrich layer properties that are invalid"""
        layers_list, layer_index, available_width = self.get_layers_properties(
            layer)
        values, units = self.get_layer_attributes(layer)
        validation, new_attributes = yield from self.get_material_properties(
            layer, units, resumed, layers_list, layer_index, available_width)
        for attr, value in values.items():
            if value == 'invalid':
                # case all other properties
                if attr != 'thickness':
                    if validation:
                        if not self.validate_manual_attribute(
                                new_attributes[attr]):
                            new_attributes[attr] = yield from \
                                self.manual_attribute_value(attr, units[attr],
                                                            layer)
                    # todo check with christian if this is clean
                    setattr(layer, attr, new_attributes[attr])
                # case thickness
                else:
                    if validation:
                        if not self.validate_thickness(
                                available_width, new_attributes[attr]):
                            new_attributes[attr] = yield from \
                                self.manual_thickness_value(attr, units[attr],
                                                            layer, layers_list,
                                                            layer_index,
                                                            available_width)
                    # todo check with christian if this is clean
                    setattr(layer, attr, new_attributes[attr])

    @staticmethod
    def get_layers_properties(layer):
        instance_width = layer.parent.width.m if \
            layer.parent.width and type(layer.parent.width.m) is float else 0
        layers_list = layer.parent.layers
        layer_index = layers_list.index(layer)
        thickness_sum = sum(layer.thickness.m for layer in
                            layers_list[:layer_index] if
                            type(layer.thickness.m) is float)
        available_width = instance_width - thickness_sum
        return layers_list, layer_index, available_width

    @staticmethod
    def get_layer_attributes(layer: Layer):
        """get actual values and units of layer attributes"""
        values = {}
        units = {}
        for attr in layer.attributes:
            value = getattr(layer, attr)
            values[attr] = value.m
            units[attr] = value.u

        return values, units

    def get_material_properties(self, layer: Layer, attributes: dict,
                                resumed, layers_list, layer_index,
                                available_width):
        """get new attribute value, based on template or manual enrichment"""
        material = re.sub(r'[^\w]*?[0-9]', '', layer.material)
        validation = True
        if material not in self.material_selected:
            material_options, new_material = yield from \
                self.material_options_decision(resumed, layer, material)
            first_decision = BoolDecision(
                question="Do you want to enrich the layers with the "
                         "material \'%s\' by using available templates? \n"
                         "Belonging Item: %s | GUID: %s \n"
                         "Enter 'n' for manual input"
                         % (new_material, layer.parent.key,
                            layer.parent.guid),
                global_key='%s_layer_enriched' % layer.material,
                context=layer.parent.key, related=layer.parent.guid)
            yield DecisionBunch([first_decision])
            if first_decision.value:
                selected_material = yield from \
                    self.asynchronous_material_search(material_options,
                                                      new_material, layer,
                                                      resumed)
                if material is None:
                    layer.material = selected_material
                self.material_selected[material] = \
                    resumed[selected_material]
            else:
                self.material_selected[material] = {}
                for attr in attributes:
                    if attr != 'thickness':
                        attr_value = yield from self.manual_attribute_value(
                            attr, attributes[attr], layer)
                        self.material_selected[material][
                            attr] = attr_value
                    else:
                        attr_value = yield from self.manual_thickness_value(
                            attr, attributes[attr], layer, layers_list,
                            layer_index, available_width)
                        self.material_selected[material][
                            attr] = attr_value
                validation = False

        return validation, self.material_selected[material]

    @classmethod
    def material_options_decision(cls, resumed: dict, layer: Layer,
                                  material) -> [list, str]:
        """get list of matching materials
        if material has no matches, more common name necessary"""
        material_options = cls.get_matches_list(material, list(resumed.keys()))\
            if material else []
        if len(material_options) == 0:
            material_decision = StringDecision(
                "Material not found, enter  more common name for the material "
                "%s:\n"
                "Belonging Item: %s | GUID: %s \n"
                "Enter 'n' for manual input"
                # ToDO: what happened to name?
                % (layer.material, layer.parent.key, layer.parent.guid),
                global_key='Layer_Material_new_material%s' % layer.guid,
                allow_skip=True,
                validate_func=partial(cls.validate_new_material,
                                      list(resumed.keys())),
                context=layer.parent.key, related=layer.parent.guid)
            yield DecisionBunch([material_decision])
            material_options = cls.get_matches_list(material_decision.value,
                                                    list(resumed.keys()))
            material = material_decision.value
        return material_options, material

    @classmethod
    def manual_attribute_value(cls, attr: str, unit: ureg.Unit, layer: Layer):
        """manual enrichment of attribute, with unit handling"""
        attr_decision = RealDecision(
            "Enter value for the material %s for: \n"
            "Belonging Item: %s | GUID: %s"
            % (attr, layer.material, layer.guid),
            global_key="Layer_%s.%s" % (layer.guid, attr),
            allow_skip=False, unit=unit,
            validate_func=cls.validate_manual_attribute,
            context=layer.material, related=layer.guid)
        yield DecisionBunch([attr_decision])
        return attr_decision.value

    @staticmethod
    def validate_manual_attribute(value):
        """validation function of manual enrichment and attribute setting - not
        thickness"""
        if value <= 0:
            return False
        return True

    @classmethod
    def manual_thickness_value(cls, attr: str, unit: ureg.Unit, layer: Layer,
                               layers_list, layer_index, available_width):
        """decision to enrich an attribute by manual"""
        if layer_index + 1 == len(layers_list):
            return available_width
        else:
            attr_decision = RealDecision(
                "Enter value for the material %s "
                "it must be < %s\n"
                "Belonging Item: %s | GUID: %s"
                % (attr, layer.parent.width, layer.material, layer.guid),
                global_key="Layer_%s.%s" % (layer.guid, attr),
                allow_skip=False, unit=unit,
                validate_func=partial(cls.validate_thickness, available_width),
                context=layer.material, related=layer.guid)
            yield DecisionBunch([attr_decision])
            return attr_decision.value

    @staticmethod
    def validate_thickness(available_width, value):
        """validation function of manual enrichment and attribute setting -
        thickness"""
        if isinstance(value, ureg.Quantity):
            value = value.m
        if 0 < value < available_width:
            return True
        return False

    @classmethod
    def asynchronous_material_search(cls, material_options: list,
                                     material_input: str,
                                     layer: Layer,
                                     resumed):
        if len(material_options) > 1:
            i = 0
            while True:
                decision_text = "Multiple possibilities found for search \"%s\"" \
                                "\nBelonging Item: %s | GUID: %s \n" \
                                "Enter more precise possible name in english to " \
                                "refine search\n" \
                                "enter 'none' to provide a new material input" \
                                " (in case of not desired options)" \
                                % (material_input, layer.parent.key, layer.parent.guid)
                material_decision = yield from cls.possibilities_string_decision(
                    decision_text, material_options, layer, i)
                if material_decision.value:
                    return material_decision.value
                else:
                    i += 1
                    material_options, material_input = \
                        yield from cls.material_options_decision(
                            resumed, layer, None)

        else:
            return material_options[0]

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

        return material_options

    @classmethod
    def validate_new_material(cls, resumed_keys: list, value: str):
        """validation function of str new material, if it matches with
        templates"""
        if value not in ['reset', 'back']:
            if len(cls.get_matches_list(value, resumed_keys)) == 0:
                return False
        return True

    @staticmethod
    def possibilities_string_decision(text, material_options, layer, aux_key):
        material_selection = ListDecision(
            text,
            choices=list(material_options),
            global_key='Layer_Material__search%s_%d' % (layer.guid, aux_key),
            allow_skip=True,
            context=layer.parent.key,
            related=layer.parent.guid,
            live_search=True)
        yield DecisionBunch([material_selection])
        return material_selection
