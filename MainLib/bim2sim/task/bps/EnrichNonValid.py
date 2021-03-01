import ast

from bim2sim.task.base import Task, ITask
from bim2sim.kernel.element import SubElement
from bim2sim.task.bps import tz_detection
from bim2sim.kernel import elements
from bim2sim.enrichment_data.data_class import DataClass
from bim2sim.decision import ListDecision, BoolDecision, RealDecision
from bim2sim.task.common.common_functions import angle_equivalent


class EnrichNonValid(ITask):
    """Prepares bim2sim instances to later export"""
    reads = ('instances', 'invalid',)
    touches = ('instances',)

    instance_template = {}

    @Task.log
    def run(self, workflow, instances, invalid):
        self.logger.info("setting verifications")
        for instance in invalid:
            self.manual_layers_creation(instance)
            print()

        return instances,

    def manual_layers_creation(self, instance, iteration=0):
        instance.layers = []
        layers_width = 0
        layers_r = 0
        layers_number_dec = RealDecision("Enter value for the number of layers \n"
                                         "Belonging Item: %s_%s | GUID: %s" %
                                         (type(instance).__name__, instance.name, instance.guid),
                                         global_key='%s_%s.layers_number_%d' %
                                                    (type(instance).__name__, instance.guid, iteration),
                                         allow_skip=False, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=False)
        layers_number_dec.decide()
        layers_number = int(layers_number_dec.value)
        layer_number = 1
        if instance.width is None:
            instance_width = RealDecision("Enter value for width of instance %d" % instance.name,
                                          global_key='%s_%s.instance_width_%d' %
                                                     (type(instance).__name__, instance.guid, iteration),
                                          allow_skip=False, allow_load=True, allow_save=True,
                                          collect=False, quick_decide=False)
            instance_width.decide()
            instance.width = instance_width.value
        while layer_number <= layers_number:
            if layer_number == layers_number:
                thickness_value = instance.width - layers_width
            else:
                layer_thickness = RealDecision("Enter value for thickness of layer %d, it muss be <= %r" %
                                               (layer_number, instance.width - layers_width),
                                               global_key='%s_%s.layer_%d_width%d' %
                                                          (type(instance).__name__, instance.guid, layer_number,
                                                           iteration),
                                               allow_skip=False, allow_load=True, allow_save=True,
                                               collect=False, quick_decide=False)
                layer_thickness.decide()
                thickness_value = layer_thickness.value
            # ToDo: Input through decision
            material_input = input(
                "Enter material for the layer %d (it will be searched or manual input)" % layer_number)
            new_layer = elements.Layer.create_additional_layer(thickness_value, material=material_input, parent=instance)
            instance.layers.append(new_layer)
            layers_width += new_layer.thickness
            layers_r += new_layer.thickness / new_layer.thermal_conduc
            if layers_width >= instance.width:
                break
            layer_number += 1

        instance.u_value = 1 / layers_r
        # check validity of new u value e
        while self.compare_with_template(instance) is False:
            self.logger.warning("The created layers does not comply with the valid u_value range, "
                                "please create new layer set")
            self.manual_layers_creation(instance, iteration)
            iteration += 1

    @staticmethod
    def compare_with_template(instance):
        template_options = []
        building = SubElement.get_class_instances('Building')[0]

        year_of_construction = building.year_of_construction
        instance_templates = dict(DataClass(used_param=3).element_bind)
        material_templates = dict(DataClass(used_param=2).element_bind)
        instance_type = type(instance).__name__
        for i in instance_templates[instance_type]:
            years = ast.literal_eval(i)
            if years[0] <= year_of_construction <= years[1]:
                for type_e in instance_templates[instance_type][i]:
                    # relev_info = instance_templates[instance_type][i][type_e]
                    # if instance_type == 'InnerWall':
                    #     layers_r = 2 / relev_info['inner_convection']
                    # else:
                    #     layers_r = 1 / relev_info['inner_convection'] + 1 / relev_info['outer_convection']
                    layers_r = 0
                    for layer, data_layer in instance_templates[instance_type][i][type_e]['layer'].items():
                        material_tc = material_templates[data_layer['material']['material_id']]['thermal_conduc']
                        layers_r += data_layer['thickness'] / material_tc
                    template_options.append(1 / layers_r)  # area?
                break

        template_options.sort()
        # check u_value
        if template_options[0] * 0.8 <= instance.u_value <= template_options[1] * 1.2:
            return True
        return False
