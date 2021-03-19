import re
import translators as ts

from bim2sim.task.base import Task, ITask
from bim2sim.decision import BoolDecision, ListDecision, RealDecision, StringDecision
from bim2sim.workflow import LOD
from functools import partial
from bim2sim.task.common.common_functions import get_material_templates
from units import ureg


class EnrichMaterial(ITask):
    """Prepares bim2sim instances to later export"""

    reads = ('instances', 'invalid',)
    touches = ('instances',)

    def __init__(self):
        super().__init__()
        self.material_selected = {}
        pass

    @Task.log
    def run(self, workflow, instances, invalid):
        self.logger.info("setting verifications")
        if workflow.layers is not LOD.low:
            for instance in invalid['materials']:
                self.get_layer_properties(instance)

        return instances,

    def get_layer_properties(self, instance):
        if hasattr(instance, 'layers'):
            for layer in instance.layers:
                self.set_material_properties(layer)

    def set_material_properties(self, layer):
        values, units = self.get_layer_attributes(layer)
        new_attributes = self.get_material_properties(layer, units)
        for attr, value in values.items():
            if value == 'invalid':
                if attr != 'thickness':
                    if not self.validate_manual_attribute(new_attributes[attr]):
                        self.manual_attribute_value(attr, units[attr], layer)
                    setattr(layer, attr, new_attributes[attr])
                else:
                    if not self.validate_thickness(layer, new_attributes[attr]):
                        self.manual_thickness_value(attr, units[attr], layer)
                    setattr(layer, attr, new_attributes[attr])

    def get_material_properties(self, layer, attributes):
        material = re.sub('[!@#$-_1234567890]', '', layer.material.lower())
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
                             % (new_material, layer.parent.name, layer.parent.guid),
                    collect=False, global_key='%s_layer_enriched' % layer.material,
                    allow_load=True, allow_save=True, context=layer.parent.name, related=layer.parent.guid)
                first_decision.decide()
                if first_decision.value:
                    selected_material = self.material_selection_decision(new_material, layer.parent, material_options)
                    if material is None:
                        layer.material = selected_material
                    self.material_selected[material] = resumed[selected_material]
                else:
                    self.material_selected[material] = {}
                    for attr in attributes:
                        self.manual_attribute_value(attr, attributes[attr], layer)
            else:
                self.material_selected[material] = selected_properties
        return self.material_selected[material]

    @staticmethod
    def get_layer_attributes(layer):
        values = {}
        units = {}
        for attr in layer.attributes:
            value = getattr(layer, attr)
            values[attr] = value.m
            # values[attr] = 'invalid'
            units[attr] = value.u

        return values, units

    def manual_attribute_value(self, attr, unit, layer):
        material = re.sub('[!@#$-_1234567890]', '', layer.material.lower())
        attr_decision = RealDecision("Enter value for the material %s for: \n"
                                     "Belonging Item: %s | GUID: %s"
                                     % (attr, layer.material, layer.guid),
                                     global_key="Layer_%s.%s" % (layer.guid, attr),
                                     allow_skip=False, allow_load=True, allow_save=True,
                                     collect=False, quick_decide=False, unit=unit,
                                     validate_func=self.validate_manual_attribute,
                                     context=layer.material, related=layer.guid)  # unit missing
        attr_decision.decide()
        self.material_selected[material][attr] = attr_decision.value

    @staticmethod
    def validate_manual_attribute(value):
        if value <= 0.0:
            return False
        return True

    @classmethod
    def validate_new_material(cls, resumed_keys, value):
        if len(cls.get_matches_list(value, resumed_keys)) == 0:
            return False
        return True

    def validate_thickness(self, layer, value):
        material = re.sub('[!@#$-_1234567890]', '', layer.material.lower())
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
            if 0 < value <= available_width:
                return True
            return False

    def manual_thickness_value(self, attr, unit, layer):
        material = re.sub('[!@#$-_1234567890]', '', layer.material.lower())
        attr_decision = RealDecision("Enter value for the material %s for: \n"
                                     "it must be < %s"
                                     "Belonging Item: %s | GUID: %s"
                                     % (attr, layer.parent.width, layer.material, layer.guid),
                                     global_key="Layer_%s.%s" % (layer.guid, attr),
                                     allow_skip=False, allow_load=True, allow_save=True,
                                     collect=False, quick_decide=False, unit=unit,
                                     validate_func=partial(self.validate_thickness, layer),
                                     context=layer.material, related=layer.guid)  # unit missing
        attr_decision.decide()
        self.material_selected[material][attr] = attr_decision.value

    @staticmethod
    def get_resumed_material_templates(attrs=None):
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
                    else:
                        resumed[material_templates[k]['name']][attr] = material_templates[k][attr]
        return resumed

    @staticmethod
    def get_matches_list(search_words, search_list, transl=True):
        """get patterns for a material name in both english and original language,
        and get afterwards the related elements from list"""

        material_ref = []

        if type(search_words) is str:
            pattern_material = search_words.split()
            if transl:
                # use of yandex, bing--- https://pypi.org/project/translators/#features
                pattern_material.extend(ts.bing(search_words).split())

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
    def material_options_decision(cls, resumed, layer, material):
        material_options = cls.get_matches_list(material, list(resumed.keys()))
        if len(material_options) == 0:
            material_decision = StringDecision(
                "Material not found, enter  more common name for the material %s:\n"
                "Belonging Item: %s | GUID: %s \n"
                "Enter 'n' for manual input"
                % (layer.material, layer.parent.name, layer.parent.guid),
                global_key='Layer_Material_%s' % layer.guid,
                allow_skip=True, allow_load=True, allow_save=True,
                collect=False, quick_decide=not True,
                validate_func=partial(cls.validate_new_material, list(resumed.keys())),
                context=layer.parent.name, related=layer.parent.guid)
            material_decision.decide()
            material_options = cls.get_matches_list(material_decision.value, list(resumed.keys()))
            material = material_decision.value
        return material_options, material

    @classmethod
    def material_selection_decision(cls, material_input, parent, material_options):
        material_selection = ListDecision(
            "Multiple possibilities found for material %s\n"
            "Belonging Item: %s | GUID: %s \n"
            "Enter 'n' for manual input"
            % (material_input, parent.name, parent.guid),
            choices=list(material_options), global_key='%s_material_enrichment' % material_input,
            allow_skip=True, allow_load=True, allow_save=True,
            collect=False, quick_decide=not True, context=parent.name, related=parent.guid)
        material_selection.decide()
        return material_selection.value
