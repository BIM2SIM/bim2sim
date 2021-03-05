import re
import translators as ts

from bim2sim.task.base import Task, ITask
from bim2sim.decision import BoolDecision, ListDecision, RealDecision, StringDecision
from bim2sim.enrichment_data.data_class import DataClass
from bim2sim.workflow import LOD


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
        if workflow.layers is LOD.full:
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
                if not self.validate_manual_attribute(new_attributes[attr]):
                    self.manual_attribute_value(attr, units[attr], layer)
                setattr(layer, attr, new_attributes[attr])

    def get_material_properties(self, layer, attributes):
        material = layer.material
        if material not in self.material_selected:
            resumed = self.get_resumed_material_templates(attributes)
            try:
                selected_properties = resumed[material]
            except KeyError:
                first_decision = BoolDecision(
                    question="Do you want to enrich the layers with the material %s by using available templates? \n"
                             "Belonging Item: %s | GUID: %s \n"
                             "Enter 'n' for manual input"
                             % (layer.material, layer.parent.name, layer.parent.guid),
                    collect=False, global_key='%s_layer_enriched' % layer.material,
                    allow_load=True, allow_save=True)
                first_decision.decide()
                first_decision.stored_decisions.clear()

                if first_decision.value:
                    material_options = self.get_matches_list(layer.material, list(resumed.keys()))
                    while len(material_options) == 0:
                        material_decision = StringDecision(
                            "Material not found, enter value for the material %s:\n"
                            "Belonging Item: %s | GUID: %s \n"
                            "Enter 'n' for manual input"
                            % (layer.material, layer.parent.name, layer.parent.guid),
                            global_key='Layer_Material_%s' % layer.guid,
                            allow_skip=True, allow_load=True, allow_save=True,
                            collect=False, quick_decide=not True)
                        material_decision.decide()
                        material_options = self.get_matches_list(material_decision.value, list(resumed.keys()))

                    decision1 = ListDecision(
                        "Multiple possibilities found for material %s\n"
                        "Belonging Item: %s | GUID: %s \n"
                        "Enter 'n' for manual input"
                        % (layer.material, layer.parent.name, layer.parent.guid),
                        choices=list(material_options), global_key='%s_material_enrichment' % layer.material,
                        allow_skip=True, allow_load=True, allow_save=True,
                        collect=False, quick_decide=not True)
                    decision1.decide()

                    if material is None:
                        layer.material = decision1.value
                    self.material_selected[layer.material] = resumed[decision1.value]
                else:
                    self.material_selected[layer.material] = {}
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
        attr_decision = RealDecision("Enter value for the %s for: \n"
                                     "Belonging Item: %s | GUID: %s"
                                     % (attr, layer.material, layer.guid),
                                     global_key="Layer_%s.%s" % (layer.guid, attr),
                                     allow_skip=False, allow_load=True, allow_save=True,
                                     collect=False, quick_decide=False, unit=unit,
                                     validate_func=self.validate_manual_attribute)  # unit missing
        attr_decision.decide()
        self.material_selected[layer.material][attr] = attr_decision.value

    @staticmethod
    def validate_manual_attribute(value):
        if value <= 0.0:
            return False
        return True

    @staticmethod
    def get_resumed_material_templates(attrs):
        material_templates = dict(DataClass(used_param=2).element_bind)
        del material_templates['version']

        resumed = {}
        for k in material_templates:
            resumed[material_templates[k]['name']] = {}
            for attr in attrs:
                if attr == 'thickness':
                    resumed[material_templates[k]['name']][attr] = material_templates[k]['thickness_default']
                else:
                    resumed[material_templates[k]['name']][attr] = material_templates[k][attr]

        return resumed

    @staticmethod
    def get_matches_list(search_words, search_list, transl=True):
        """get patterns for a material name in both english and original language,
        and get afterwards the related elements from list"""

        material_ref = []

        if type(search_words) is str:
            pattern_material = re.sub('[!@#$-_1234567890]', '', search_words.lower()).split()
            if transl:
                # use of yandex, bing--- https://pypi.org/project/translators/#features
                pattern_material.extend(ts.bing(re.sub('[!@#$-_1234567890]', '', search_words.lower())).split())

            for i in pattern_material:
                material_ref.append(re.compile('(.*?)%s' % i, flags=re.IGNORECASE))

        material_options = []
        for ref in material_ref:
            for mat in search_list:
                if ref.match(mat):
                    if mat not in material_options:
                        material_options.append(mat)

        if len(material_options) == 0:
            return search_list

        return material_options
