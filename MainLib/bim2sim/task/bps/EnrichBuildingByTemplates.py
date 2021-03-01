import ast

from bim2sim.task.base import Task, ITask
from bim2sim.kernel.element import SubElement
from bim2sim.kernel import elements
from bim2sim.enrichment_data.data_class import DataClass
from bim2sim.decision import ListDecision


class EnrichBuildingByTemplates(ITask):
    """Prepares bim2sim instances to later export"""
    reads = ('instances', 'invalid',)
    touches = ('instances',)

    instance_template = {}

    @Task.log
    def run(self, workflow, instances, invalid):
        construction_type = self.get_construction_type()
        self.logger.info("setting verifications")
        for instance in invalid:
            self.template_layers_creation(instance, construction_type)
        return instances,

    @staticmethod
    def get_construction_type():
        decision_template = ListDecision("Choose one of the following construction types to proceed",
                                         choices=['heavy', 'light'],
                                         global_key="construction_type.bpsTemplate",
                                         allow_skip=True, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=not True)
        if decision_template.value is None:
            decision_template.decide()
        return decision_template.value

    @classmethod
    def template_layers_creation(cls, instance, construction_type):
        instance.layers = []
        layers_width = 0
        layers_r = 0
        template = cls.get_instance_template(instance, construction_type)
        if template is not None:
            for i_layer, layer_props in template['layer'].items():
                new_layer = elements.Layer.create_additional_layer(
                    layer_props['thickness'], instance, material=layer_props['material']['name'])
                instance.layers.append(new_layer)
                layers_width += new_layer.thickness
                layers_r += new_layer.thickness / new_layer.thermal_conduc
            instance.width = layers_width
            instance.u_value = 1 / layers_r
        # with template comparison not necessary
        pass

    @classmethod
    def get_instance_template(cls, instance, construction_type):
        building = SubElement.get_class_instances('Building')[0]

        instance_type = type(instance).__name__
        instance_templates = dict(DataClass(used_param=3).element_bind)
        if instance_type in cls.instance_template:
            return cls.instance_template[instance_type]

        year_of_construction = int(building.year_of_construction)
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
                decision_template = ListDecision("the following construction types were "
                                                 "found for year %s and instance type %s"
                                                 % (year_of_construction, instance_type),
                                                 choices=list(template_options.keys()),
                                                 global_key="%s_%s.bpsTemplate" % (type(instance).__name__, instance.guid),
                                                 allow_skip=True, allow_load=True, allow_save=True,
                                                 collect=False, quick_decide=not True)
                if decision_template.value is None:
                    decision_template.decide()
                template_value = template_options[decision_template.value]
                cls.instance_template[instance_type] = template_value
                return template_value
