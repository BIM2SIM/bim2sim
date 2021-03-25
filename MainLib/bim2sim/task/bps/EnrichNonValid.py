from bim2sim.task.base import Task, ITask
from bim2sim.kernel import elements
from bim2sim.decision import RealDecision, StringDecision
from bim2sim.workflow import LOD
from bim2sim.task.bps.EnrichBuildingByTemplates import EnrichBuildingByTemplates
from bim2sim.task.bps.EnrichMaterial import EnrichMaterial
from bim2sim.task.bps.BuildingVerification import BuildingVerification
from functools import partial
from bim2sim.kernel.units import ureg


class EnrichNonValid(ITask):
    """Prepares bim2sim instances to later export"""
    reads = ('invalid_layers',)
    touches = ('enriched_layers',)

    def __init__(self):
        super().__init__()
        self.material_selected = {}
        self.enriched_layers = []
        pass

    @Task.log
    def run(self, workflow, invalid_layers):
        self.logger.info("setting verifications")
        if workflow.layers is not LOD.low:
            construction_type = EnrichBuildingByTemplates.get_construction_type()
            for instance in invalid_layers:
                self.layers_creation(instance, construction_type)
                self.enriched_layers.append(instance)

        return self.enriched_layers,

    def layers_creation(self, instance, construction_type):
        if len(instance.layers) == 0:
            EnrichBuildingByTemplates.template_layers_creation(instance, construction_type)
        else:
            self.manual_layers_creation(instance)

    def manual_layers_creation(self, instance, iteration=0):
        instance.layers = []
        layers_width = 0
        layers_r = 0
        layers_number = self.layers_numbers_decision(instance, iteration)
        layer_number = 1
        if instance.width is None:
            instance.width = self.instance_width_decision(instance, iteration)
        while layer_number <= layers_number:
            if layer_number == layers_number:
                thickness_value = instance.width - layers_width
            else:
                thickness_value = self.layers_thickness_decision(instance, iteration, layer_number, layers_width)
            material_input = self.material_input_decision(instance, layer_number, iteration)
            if material_input not in self.material_selected:
                self.store_new_material(instance, material_input)
            new_layer = elements.Layer.create_additional_layer(thickness_value, material=material_input,
                                                               parent=instance,
                                                               material_properties=self.material_selected[
                                                                   material_input])
            instance.layers.append(new_layer)
            layers_width += new_layer.thickness
            layers_r += new_layer.thickness / new_layer.thermal_conduc
            if layers_width >= instance.width:
                break
            layer_number += 1

        instance.u_value = 1 / layers_r
        iteration += 1
        # check validity of new u value e
        # while BuildingVerification.compare_with_template(instance) is False:
        #     self.logger.warning("The created layers does not comply with the valid u_value range, "
        #                         "please create new layer set")
        #     self.manual_layers_creation(instance, iteration)

    @classmethod
    def layers_numbers_decision(cls, instance, iteration):
        layers_number_dec = RealDecision("Enter value for the number of layers \n"
                                         "Belonging Item: %s_%s | GUID: %s" %
                                         (type(instance).__name__, instance.name, instance.guid),
                                         global_key='%s_%s.layers_number_%d' %
                                                    (type(instance).__name__, instance.guid, iteration),
                                         allow_skip=False, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=False,
                                         validate_func=cls.validate_positive,
                                         context=instance.name, related=instance.guid)
        layers_number_dec.decide()
        return int(layers_number_dec.value)

    @classmethod
    def instance_width_decision(cls, instance, iteration):
        instance_width = RealDecision("Enter value for width of instance %d" % instance.name,
                                      global_key='%s_%s.instance_width_%d' %
                                                 (type(instance).__name__, instance.guid, iteration),
                                      allow_skip=False, allow_load=True, allow_save=True,
                                      collect=False, quick_decide=False,
                                      unit=ureg.meter,
                                      validate_func=cls.validate_positive)
        instance_width.decide()
        return instance_width.value

    @classmethod
    def layers_thickness_decision(cls, instance, iteration, layer_number, layers_width):
        layer_thickness = RealDecision("Enter value for thickness of layer %d, it muss be <= %r" %
                                       (layer_number, instance.width - layers_width),
                                       global_key='%s_%s.layer_%d_width%d' %
                                                  (type(instance).__name__, instance.guid, layer_number,
                                                   iteration),
                                       allow_skip=False, allow_load=True, allow_save=True,
                                       collect=False, quick_decide=False,
                                       unit=ureg.meter,
                                       validate_func=partial(cls.validate_thickness, instance))
        layer_thickness.decide()
        return layer_thickness.value

    @classmethod
    def material_input_decision(cls, instance, layer_number, iteration):
        resumed = EnrichMaterial.get_resumed_material_templates()
        material_input = StringDecision(
            "Enter material for the layer %d (it will be searched or manual input)\n"
            "Belonging Item: %s | GUID: %s \n"
            "Enter 'n' for manual input"
            % (layer_number, instance.name, instance.guid),
            global_key='Layer_Material%d_%s%d' % (layer_number, instance.guid, iteration),
            allow_skip=True, allow_load=True, allow_save=True,
            collect=False, quick_decide=not True,
            validate_func=partial(EnrichMaterial.validate_new_material, list(resumed.keys())),
            context=instance.name, related=instance.guid)
        material_input.decide()
        return material_input.value

    def store_new_material(self, instance, material_input):
        resumed = EnrichMaterial.get_resumed_material_templates()
        material_options = EnrichMaterial.get_matches_list(material_input, list(resumed.keys()))
        material_selected = EnrichMaterial.material_selection_decision(material_input, instance, material_options)
        self.material_selected[material_input] = resumed[material_selected]

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
