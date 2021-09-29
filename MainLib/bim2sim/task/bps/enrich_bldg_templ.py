import ast

from bim2sim.kernel.elements import bps
from bim2sim.task.base import ITask
from bim2sim.decision import ListDecision, DecisionBunch
from bim2sim.workflow import LOD
from bim2sim.task.bps.enrich_mat import EnrichMaterial
from bim2sim.utilities.common_functions import get_type_building_elements
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.kernel.finder import TemplateFinder


class EnrichBuildingByTemplates(ITask):
    """Prepares bim2sim instances to later export"""
    reads = ('invalid_layers', 'instances')
    touches = ('enriched_layers',)

    instance_template = {}

    def __init__(self):
        super().__init__()
        self.enriched_layers = []
        pass

    def run(self, workflow, invalid_layers, instances):
        self.logger.info("setting verifications")
        if workflow.layers is LOD.low:
            construction_type = yield from self.get_construction_type()
            resumed = EnrichMaterial.get_resumed_material_templates()
            for instance in invalid_layers.values():
                yield from self.template_layers_creation(
                    instance, construction_type, instances, resumed)
                self.enriched_layers.append(instance)
            windows = filter_instances(instances, 'Window')
            for window in windows:
                yield from self.window_template_enrichment(
                    window, construction_type, instances)

        self.logger.info("enriched %d invalid layers",
                         len(self.enriched_layers))

        return self.enriched_layers,

    @staticmethod
    def get_construction_type():
        decision_template = ListDecision(
            "Choose one of the following construction types to proceed",
            choices=['heavy', 'light'],
            global_key="construction_type.bpsTemplate",
            allow_skip=True)
        yield DecisionBunch([decision_template])
        return decision_template.value

    @classmethod
    def template_layers_creation(cls, instance, construction_type, instances,
                                 resumed):
        instance.layers = []
        layers_width = 0
        layers_r = 0
        data = yield from cls.get_instance_template(
            instance, construction_type, instances)
        template = dict(data)
        if template is not None:
            for i_layer, layer_props in template['layer'].items():
                material_properties = cls.get_material_properties(
                    layer_props['material']['name'], resumed,
                    layer_props['thickness'])
                new_layer = bps.Layer(finder=TemplateFinder(),
                                      **material_properties)
                new_layer.parent = instance
                instance.layers.append(new_layer)
                layers_width += new_layer.thickness
                layers_r += new_layer.thickness / new_layer.thermal_conduc
            instance.width = layers_width
            instance.u_value = 1 / layers_r
        # with template comparison not necessary
        pass

    @staticmethod
    def get_material_properties(material, resumed, thickness):
        material_properties = resumed[material]
        material_properties['thickness'] = thickness
        return material_properties

    @classmethod
    def get_instance_template(cls, instance, construction_type, instances):
        # TODO multiple buildings #165
        building = filter_instances(instances, 'Building')[0]

        instance_type = type(instance).__name__
        instance_templates = get_type_building_elements()
        if instance_type in cls.instance_template:
            return cls.instance_template[instance_type]

        year_of_construction = int(building.year_of_construction.m)
        template_options = []
        for i in instance_templates[instance_type]:
            years = ast.literal_eval(i)
            if years[0] <= year_of_construction <= years[1]:
                template_options = instance_templates[instance_type][i]
                break
        try:
            template_value = template_options[construction_type]
            cls.instance_template[instance_type] = template_value
            return template_value
        except KeyError:
            if len(template_options.keys()) > 0:
                yield from cls.get_alternative_construction_type(
                    year_of_construction, instance_type, template_options,
                    instance)
                return cls.instance_template[instance_type]

    @classmethod
    def get_alternative_construction_type(cls, year_of_construction,
                                          instance_type, template_options,
                                          instance):
        if len(template_options) > 1:
            decision_template = ListDecision(
                "the following construction types were "
                "found for year %s and instance type %s"
                % (year_of_construction, instance_type),
                choices=list(template_options.keys()),
                global_key="%s_%s.bpsTemplate" % (type(instance).__name__,
                                                  instance.guid),
                allow_skip=True)
            yield DecisionBunch([decision_template])
            cls.instance_template[instance_type] = \
                template_options[decision_template.value]
        else:
            cls.instance_template[instance_type] = \
                template_options[next(iter(template_options))]

    def window_template_enrichment(self, window, construction_type, instances):
        enriched_attrs = ['g_value', 'a_conv', 'shading_g_total',
                          'shading_max_irr', 'inner_convection',
                          'inner_radiation', 'outer_radiation',
                          'outer_convection']
        template = yield from self.get_instance_template(
            window, construction_type, instances)
        for attr in enriched_attrs:
            value = getattr(window, attr)
            if value is None:
                setattr(window, attr, template[attr])
