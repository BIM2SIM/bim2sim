import re

from bim2sim.task.base import Task, ITask
from bim2sim.decision import BoolDecision, ListDecision, RealDecision, StringDecision
from bim2sim.workflow import LOD
from functools import partial
from bim2sim.utilities.common_functions import get_material_templates, translate_deep
from bim2sim.kernel.units import ureg
from bim2sim.workflow import Workflow
from bim2sim.kernel.element import ProductBased
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

    @Task.log
    def run(self, workflow: Workflow, instances: dict, invalid_materials: dict):
        self.logger.info("setting verifications")
        if workflow.layers is not LOD.low:
            for instance_guid, layers in invalid_materials.items():
                for layer in layers:
                    self.set_material_properties(layer)
                    self.enriched_materials.append(layer)
            self.logger.info("enriched %d invalid materials", len(self.enriched_materials))

        return self.enriched_materials,

    def set_material_properties(self, layer: Layer):
        """enrich layer properties that are invalid"""
        values, units = self.get_layer_attributes(layer)
        new_attributes = self.get_material_properties(layer, units)
        for attr, value in values.items():
            if value == 'invalid':
                # case all other properties
                if attr != 'thickness':
                    if not self.validate_manual_attribute(new_attributes[attr]):
                        self.manual_attribute_value(attr, units[attr], layer)
                    # todo check with christian if this is clean
                    setattr(layer, attr, new_attributes[attr])
                # case thickness
                else:
                    if not self.validate_thickness(layer, new_attributes[attr]):
                        self.manual_thickness_value(attr, units[attr], layer)
                    # todo check with christian if this is clean
                    setattr(layer, attr, new_attributes[attr])

    def get_material_properties(self, layer: Layer, attributes: dict):
        """get new attribute value, based on template or manual enrichment"""
        material = re.sub(r'[^\w]*?[0-9]', '', layer.material)
        if material not in self.material_selected:
            resumed = self.get_resumed_material_templates(attributes)
            try:
                selected_properties = resumed[material]
            except KeyError:
                material_options, new_material = self.material_options_decision(resumed, layer, material)
                first_decision = BoolDecision(
                    question="Do you want to enrich the layers with the material \'%s\' "
                             "by using available templates? \n"
                             "Belonging Item: %s | GUID: %s \n"
                             "Enter 'n' for manual input"
                             % (new_material, layer.parent.key, layer.parent.guid),
                    collect=False, global_key='%s_layer_enriched' % layer.material,
                    allow_load=True, allow_save=True, context=layer.parent.key, related=layer.parent.guid)
                first_decision.decide()
                if first_decision.value:
                    selected_material = self.material_selection_decision(new_material, layer.parent, material_options)
                    if material is None:
                        layer.material = selected_material
                    self.material_selected[material] = resumed[selected_material]
                else:
                    self.material_selected[material] = {}
                    for attr in attributes:
                        if attr != 'thickness':
                            self.manual_attribute_value(attr, attributes[attr], layer)
                        else:
                            self.manual_thickness_value(attr, attributes[attr], layer)
            else:
                self.material_selected[material] = selected_properties
        return self.material_selected[material]

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

    def manual_attribute_value(self, attr: str, unit: ureg.Unit, layer: Layer):
        """manual enrichment of attribute, with unit handling"""
        material = re.sub(r'[^\w]*?[0-9]', '', layer.material)
        attr_decision = RealDecision("Enter value for the material %s for: \n"
                                     "Belonging Item: %s | GUID: %s"
                                     % (attr, layer.material, layer.guid),
                                     global_key="Layer_%s.%s" % (layer.guid, attr),
                                     allow_skip=False, allow_load=True, allow_save=True,
                                     collect=False, quick_decide=False, unit=unit,
                                     validate_func=self.validate_manual_attribute,
                                     context=layer.material, related=layer.guid)
        attr_decision.decide()
        self.material_selected[material][attr] = attr_decision.value

    @staticmethod
    def validate_manual_attribute(value):
        """validation function of manual enrichment and attribute setting - not thickness"""
        if value <= 0.0:
            return False
        return True

    @classmethod
    def validate_new_material(cls, resumed_keys: list, value: str):
        """validation function of str new material, if it matches with templates"""
        if len(cls.get_matches_list(value, resumed_keys)) == 0:
            return False
        return True

    def validate_thickness(self, layer: Layer, value):
        """validation function of manual enrichment and attribute setting - thickness"""
        material = re.sub(r'[^\w]*?[0-9]', '', layer.material)
        instance_width = layer.parent.width
        layers_list = layer.parent.layers
        layer_index = layers_list.index(layer)
        thickness_sum = ureg.Quantity(
            sum(layer.thickness.m for layer in layers_list[:layer_index] if type(layer.thickness.m) is float), ureg.m)
        available_width = instance_width.m - thickness_sum.m
        if layer_index + 1 == len(layers_list):
            self.material_selected[material]['thickness'] = available_width
            return True
        else:
            if isinstance(value, ureg.Quantity):
                value = value.m
            if 0 < value < available_width:
                return True
            return False

    def manual_thickness_value(self, attr: str, unit: ureg.Unit, layer: Layer):
        """decision to enrich an attribute by manual"""
        material = re.sub(r'[^\w]*?[0-9]', '', layer.material)
        attr_decision = RealDecision("Enter value for the material %s "
                                     "it must be < %s\n"
                                     "Belonging Item: %s | GUID: %s"
                                     % (attr, layer.parent.width, layer.material, layer.guid),
                                     global_key="Layer_%s.%s" % (layer.guid, attr),
                                     allow_skip=False, allow_load=True, allow_save=True,
                                     collect=False, quick_decide=False, unit=unit,
                                     validate_func=partial(self.validate_thickness, layer),
                                     context=layer.material, related=layer.guid)
        attr_decision.decide()
        self.material_selected[material][attr] = attr_decision.value

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
                        resumed[material_templates[k]['name']][attr] = material_templates[k]['thickness_default']
                    else:
                        resumed[material_templates[k]['name']][attr] = material_templates[k][attr]
            else:
                for attr in material_templates[k]:
                    if attr == 'thickness_default':
                        resumed[material_templates[k]['name']]['thickness'] = material_templates[k][attr]
                    elif attr == 'name':
                        resumed[material_templates[k]['name']]['material'] = material_templates[k][attr]
                    elif attr == 'thickness_list':
                        continue
                    else:
                        resumed[material_templates[k]['name']][attr] = material_templates[k][attr]
        return resumed

    @staticmethod
    def get_matches_list(search_words: str, search_list: list, transl: bool = True) -> list:
        """get patterns for a material name in both english and original language,
        and get afterwards the related elements from list"""

        material_ref = []

        if type(search_words) is str:
            pattern_material = search_words.split()
            if transl:
                # use of yandex, bing--- https://pypi.org/project/translators/#features
                pattern_material.extend(translate_deep(search_words).split())

            for i in pattern_material:
                material_ref.append(re.compile('(.*?)%s' % i, flags=re.IGNORECASE))

        material_options = []
        for ref in material_ref:
            for mat in search_list:
                if ref.match(mat):
                    if mat not in material_options:
                        material_options.append(mat)

        return material_options

    @classmethod
    def material_options_decision(cls, resumed: dict, layer: Layer, material: str) -> [list, str]:
        """get list of matching materials
        if material has no matches, more common name necessary"""
        material_options = cls.get_matches_list(material, list(resumed.keys()))
        if len(material_options) == 0:
            material_decision = StringDecision(
                "Material not found, enter  more common name for the material %s:\n"
                "Belonging Item: %s | GUID: %s \n"
                "Enter 'n' for manual input"
                # ToDO: what happened to name?
                % (layer.material, layer.parent.key, layer.parent.guid),
                global_key='Layer_Material_%s' % layer.guid,
                allow_skip=True, allow_load=True, allow_save=True,
                collect=False, quick_decide=not True,
                validate_func=partial(cls.validate_new_material, list(resumed.keys())),
                context=layer.parent.key, related=layer.parent.guid)
            material_decision.decide()
            material_options = cls.get_matches_list(material_decision.value, list(resumed.keys()))
            material = material_decision.value
        return material_options, material

    @classmethod
    def material_selection_decision(cls, material_input: str, parent: ProductBased, material_options: list):
        """select one of the material of given matches list"""
        material_selection = ListDecision(
            "Multiple possibilities found for material %s\n"
            "Belonging Item: %s | GUID: %s \n"
            "Enter 'n' for manual input"
            % (material_input, parent.key, parent.guid),
            choices=list(material_options), global_key='%s_material_enrichment' % material_input,
            allow_skip=True, allow_load=True, allow_save=True,
            collect=False, quick_decide=not True, context=parent.key, related=parent.guid)
        if len(list(material_options)) > 1:
            material_selection.decide()
        return material_selection.value
