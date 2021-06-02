from functools import partial

from bim2sim.task.base import ITask
from bim2sim.decision import RealDecision, StringDecision, DecisionBunch
from bim2sim.workflow import LOD
from bim2sim.task.bps.enrich_bldg_templ import EnrichBuildingByTemplates
from bim2sim.task.bps.enrich_mat import EnrichMaterial
from bim2sim.kernel.units import ureg
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.kernel.elements import bps
from bim2sim.kernel.finder import TemplateFinder


class EnrichNonValid(ITask):
    """Prepares bim2sim instances to later export"""
    reads = ('invalid_layers', 'instances')
    touches = ('enriched_layers',)

    def __init__(self):
        super().__init__()
        self.material_selected = {}
        self.enriched_layers = []
        self.enriched_class = {}
        self.window_enrichment = {}
        pass

    def run(self, workflow, invalid_layers, instances):
        self.logger.info("setting verifications")
        if workflow.layers is not LOD.low:
            construction_type = EnrichBuildingByTemplates.get_construction_type()
            for instance in invalid_layers.values():
                yield from self.layers_creation(
                    instance, construction_type, instances)
                self.enriched_layers.append(instance)
            windows = filter_instances(instances, 'Window')
            for window in windows:
                yield from self.window_manual_enrichment(window)

        self.logger.info("enriched %d invalid layers", len(self.enriched_layers))

        return self.enriched_layers,

    def layers_creation(self, instance, construction_type, instances):
        if len(instance.layers) == 0:
            EnrichBuildingByTemplates.template_layers_creation(instance, construction_type, instances)
        else:
            yield from self.manual_layers_creation(instance)

    def manual_layers_creation(self, instance):
        instance_class = type(instance).__name__
        if instance_class in self.enriched_class:
            instance.width = self.enriched_class[instance_class]['width']
            instance.layers = self.enriched_class[instance_class]['layers']
            instance.u_value = self.enriched_class[instance_class]['u_value']
        else:
            instance.layers = []
            layers_width = 0
            layers_r = 0
            layers_number = yield from self.layers_numbers_decision(instance)
            layer_number = 1
            if instance.width is None:
                instance.width = yield from self.instance_width_decision(
                    instance)
            while layer_number <= layers_number:
                if layer_number == layers_number:
                    thickness_value = instance.width - layers_width
                else:
                    thickness_value = yield from self.layers_thickness_decision(
                        instance, layer_number, layers_width)
                material_input = yield from self.material_input_decision(
                    instance, layer_number)
                if material_input not in self.material_selected:
                    yield from self.store_new_material(instance, material_input)
                new_layer = bps.Layer(finder=TemplateFinder(), **self.material_selected[material_input],
                                      thickness=thickness_value)
                new_layer.parent = instance
                instance.layers.append(new_layer)
                layers_width += new_layer.thickness
                layers_r += new_layer.thickness / new_layer.thermal_conduc
                if layers_width >= instance.width:
                    break
                layer_number += 1
            instance.u_value = 1 / layers_r
            self.enriched_class[instance_class] = {}
            self.enriched_class[instance_class]['width'] = instance.width
            self.enriched_class[instance_class]['layers'] = instance.layers
            self.enriched_class[instance_class]['u_value'] = instance.u_value

    @classmethod
    def layers_numbers_decision(cls, instance):
        layers_number_dec = RealDecision(
            "Enter value for the number of layers \n"
            "Belonging Item: %s_%s | GUID: %s" %
            (type(instance).__name__, instance.key, instance.guid),
            global_key='%s_%s.layers_number' %
                       (type(instance).__name__, instance.guid),
            allow_skip=False,
            validate_func=cls.validate_positive,
            context=instance.key, related=instance.guid)
        yield DecisionBunch([layers_number_dec])
        return int(layers_number_dec.value)

    @classmethod
    def instance_width_decision(cls, instance):
        instance_width = RealDecision(
            "Enter value for width of instance %d" % instance.key,
            global_key='%s_%s.instance_width' %
                       (type(instance).__name__, instance.guid),
            allow_skip=False,
            unit=ureg.meter,
            validate_func=cls.validate_positive)
        yield DecisionBunch([instance_width])
        return instance_width.value

    @classmethod
    def layers_thickness_decision(cls, instance, layer_number, layers_width):
        layer_thickness = RealDecision(
            "Enter value for thickness of layer %d, it muss be <= %r" %
            (layer_number, instance.width - layers_width),
            global_key='%s_%s.layer_%d_width' %
                       (type(instance).__name__, instance.guid, layer_number),
            allow_skip=False,
            unit=ureg.meter,
            validate_func=partial(cls.validate_thickness, instance))
        yield DecisionBunch([layer_thickness])
        return layer_thickness.value

    @classmethod
    def material_input_decision(cls, instance, layer_number):
        resumed = EnrichMaterial.get_resumed_material_templates()
        material_input = StringDecision(
            "Enter material for the layer %d (it will be searched or manual input)\n"
            "Belonging Item: %s | GUID: %s \n"
            "Enter 'n' for manual input"
            % (layer_number, instance.key, instance.guid),
            global_key='Layer_Material%d_%s' % (layer_number, instance.guid),
            allow_skip=True,
            validate_func=partial(EnrichMaterial.validate_new_material, list(resumed.keys())),
            context=instance.key, related=instance.guid)
        yield DecisionBunch([material_input])
        return material_input.value

    def store_new_material(self, instance, material_input):
        resumed = EnrichMaterial.get_resumed_material_templates()
        material_options = EnrichMaterial.get_matches_list(material_input, list(resumed.keys()))
        if len(material_options) > 1:
            material_selected = yield from \
                EnrichMaterial.material_selection_decision(
                    material_input, instance, material_options)
        else:
            material_selected = material_options[0]
        material_dict = dict(resumed[material_selected])
        del material_dict['thickness']
        self.material_selected[material_input] = material_dict

    @staticmethod
    def validate_positive(value):
        if value <= 0.0:
            return False
        return True

    @staticmethod
    def validate_thickness(instance, value):
        if value <= 0.0 or value > instance.width:
            return False
        return True

    def window_manual_enrichment(self, window):
        enriched_attrs = ['g_value', 'a_conv', 'shading_g_total', 'shading_max_irr', 'inner_convection',
                          'inner_radiation', 'outer_radiation', 'outer_convection']
        for attr in enriched_attrs:
            value = getattr(window, attr)
            if value is None:
                if attr not in self.window_enrichment:
                    new_value = yield from self.manual_attribute_enrichment(window, attr).m
                    self.window_enrichment[attr] = new_value
                setattr(window, attr, self.window_enrichment[attr])

    @classmethod
    def manual_attribute_enrichment(cls, instance, attribute):
        new_attribute = RealDecision(
            "Enter value for %s of instance %s" %
            (attribute, type(instance).__name__),
            global_key='%s_%s' % (type(instance).__name__, attribute),
            allow_skip=False, allow_load=True, allow_save=True,
            collect=False, quick_decide=False,
            validate_func=cls.validate_positive)
        yield DecisionBunch([new_attribute])
        return new_attribute.value
