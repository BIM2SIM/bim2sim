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
    reads = ('instances', 'ifc',)
    touches = ('instances',)

    # materials = {}
    # property_error = {}
    instance_template = {}

    @Task.log
    def run(self, workflow, instances, ifc):
        self.logger.info("setting verifications")
        building = SubElement.get_class_instances('Building')[0]
        for guid, ins in instances.items():
            self.layers_verification(ins, building)

        storeys = SubElement.get_class_instances('Storey')

        tz_inspect = tz_detection.Inspect(self, workflow)
        tz_inspect.run(ifc, instances, storeys)
        instances.update(tz_inspect.instances)

        for guid, ins in instances.items():
            new_orientation = self.orientation_verification(ins)
            if new_orientation is not None:
                ins.orientation = new_orientation

        tz_bind = tz_detection.Bind(self, workflow)
        tz_bind.run(instances)

        return instances,

    @staticmethod
    def orientation_verification(instance):
        supported_classes = {'Window', 'OuterWall', 'OuterDoor', 'Wall', 'Door'}
        if instance.__class__.__name__ in supported_classes:
            new_angles = list(set([space_boundary.orientation for space_boundary in instance.space_boundaries]))
            # new_angles = list(set([space_boundary.orientation - space_boundary.thermal_zones[0].orientation for space_boundary in instance.space_boundaries]))
            if len(new_angles) > 1:
                return None
            # no true north necessary
            new_angle = angle_equivalent(new_angles[0])
            # new angle return
            if new_angle - instance.orientation > 0.1:
                return new_angle

    # @classmethod
    # def layers_verification(cls, instance, building):
    #     supported_classes = {'OuterWall', 'Wall', 'InnerWall', 'Door', 'InnerDoor', 'OuterDoor', 'Roof', 'Floor',
    #                          'GroundFloor', 'Window'}
    #     instance_type = instance.__class__.__name__
    #     if instance_type in supported_classes:
    #         # through the type elements enrichment without comparisons
    #         if instance_type not in cls.instance_template:
    #             type_elements_decision = BoolDecision(
    #                 question="Do you want for all %ss to be enriched before any calculation "
    #                          "with the type elements template," % type(instance).__name__,
    #                 global_key="type_elements_%s" % type(instance).__name__,
    #                 collect=False)
    #             type_elements_decision.decide()
    #             if type_elements_decision.value:
    #                 return cls.template_layers_creation(instance, building)
    #         else:
    #             return cls.template_layers_creation(instance, building)
    #         u_value_verification = cls.compare_with_template(instance, building)
    #         # comparison with templates value
    #         if u_value_verification is False:
    #             # ToDo logger
    #             print("u_value verification failed, the %s u value is "
    #                                 "doesn't correspond to the year of construction. Please create new layer set" %
    #                                 type(instance).__name__)
    #             # cls.logger.warning("u_value verification failed, the %s u value is "
    #             #                     "doesn't correspond to the year of construction. Please create new layer set" %
    #             #                     type(instance).__name__)
    #             return cls.layer_creation(instance, building)
    #         # instance.layers = [] # probe
    #         layers_width = 0
    #         layers_r = 0
    #         for layer in instance.layers:
    #             layers_width += layer.thickness
    #             if layer.thermal_conduc is not None:
    #                 if layer.thermal_conduc > 0:
    #                     layers_r += layer.thickness / layer.thermal_conduc
    #
    #         # critical failure // check units again
    #         width_discrepancy = abs(instance.width - layers_width) / instance.width if \
    #             (instance.width is not None and instance.width > 0) else 9999
    #         u_discrepancy = abs(instance.u_value - 1 / layers_r) / instance.u_value if \
    #             (instance.u_value is not None and instance.u_value > 0) else 9999
    #         if width_discrepancy > 0.2 or u_discrepancy > 0.2:
    #             # ToDo Logger
    #             print("Width or U Value discrepancy found. Please create new layer set")
    #             # cls.logger.warning("Width or U Value discrepancy found. Please create new layer set")
    #             cls.layer_creation(instance, building)

    def layers_verification(self, instance, building):
        supported_classes = {'OuterWall', 'Wall', 'InnerWall', 'Door', 'InnerDoor', 'OuterDoor', 'Roof', 'Floor',
                             'GroundFloor', 'Window'}
        instance_type = instance.__class__.__name__
        if instance_type in supported_classes:
            # through the type elements enrichment without comparisons
            if instance_type not in self.instance_template:
                type_elements_decision = BoolDecision(
                    question="Do you want for all %s's to be enriched before any calculation "
                             "with the type elements template," % type(instance).__name__,
                    global_key="%s_type_elements_used" % type(instance).__name__,
                    collect=False, allow_load=True, allow_save=True,
                    quick_decide=not True)
                type_elements_decision.decide()
                if type_elements_decision.value:
                    return self.template_layers_creation(instance, building)
            else:
                return self.template_layers_creation(instance, building)
            u_value_verification = self.compare_with_template(instance, building)
            # comparison with templates value
            if u_value_verification is False:
                self.logger.warning("u_value verification failed, the %s u value is "
                                    "doesn't correspond to the year of construction. Please create new layer set" %
                                    type(instance).__name__)
                return self.layer_creation(instance, building)
            # instance.layers = [] # probe
            layers_width = 0
            layers_r = 0
            for layer in instance.layers:
                layers_width += layer.thickness
                if layer.thermal_conduc is not None:
                    if layer.thermal_conduc > 0:
                        layers_r += layer.thickness / layer.thermal_conduc

            # critical failure // check units again
            width_discrepancy = abs(instance.width - layers_width) / instance.width if \
                (instance.width is not None and instance.width > 0) else 9999
            u_discrepancy = abs(instance.u_value - 1 / layers_r) / instance.u_value if \
                (instance.u_value is not None and instance.u_value > 0) else 9999
            if width_discrepancy > 0.2 or u_discrepancy > 0.2:
                self.logger.warning("Width or U Value discrepancy found. Please create new layer set")
                self.layer_creation(instance, building)

    def layer_creation(self, instance, building, iteration=0):
        decision_layers = ListDecision("the following layer creation methods were found for \n"
                                       "Belonging Item: %s | GUID: %s \n" % (instance.name, instance.guid),
                                       choices=['Manual layers creation (from zero)',
                                                'Template layers creation (based on given u value)'],
                                       global_key='%s_%s.layer_creation_method_%d' %
                                                  (type(instance).__name__, instance.guid, iteration),
                                       allow_skip=True, allow_load=True, allow_save=True,
                                       collect=False, quick_decide=not True)
        decision_layers.decide()
        if decision_layers.value == 'Manual layers creation (from zero)':
            self.manual_layers_creation(instance, building, iteration)
        elif decision_layers.value == 'Template layers creation (based on given u value)':
            self.template_layers_creation(instance, building)

    def manual_layers_creation(self, instance, building, iteration):
        instance.layers = []
        layers_width = 0
        layers_r = 0
        layers_number_dec = RealDecision("Enter value for the number of layers",
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
        iteration = 1
        while self.compare_with_template(instance, building) is False:
            self.logger.warning("The created layers does not comply with the valid u_value range, "
                                "please create new layer set")
            self.layer_creation(instance, building, iteration)
            iteration += 1
        pass

    @classmethod
    def template_layers_creation(cls, instance, building):
        instance.layers = []
        layers_width = 0
        layers_r = 0
        template = cls.get_instance_template(instance, building)
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
    def compare_with_template(cls, instance, building):
        template_options = []
        if instance.u_value is None:
            return False
        year_of_construction = building.year_of_construction
        if year_of_construction is None:
            year_decision = RealDecision("Enter value for the buildings year of construction",
                                         global_key="Building_%s.year_of_construction" % building.guid,
                                         allow_skip=False, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=False)
            year_decision.decide()
            year_of_construction = int(year_decision.value.m)
        else:
            year_of_construction = int(building.year_of_construction)

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

    @classmethod
    def get_instance_template(cls, instance, building):

        instance_type = type(instance).__name__
        instance_templates = dict(DataClass(used_param=3).element_bind)
        if instance_type in cls.instance_template:
            return cls.instance_template[instance_type]

        year_of_construction = building.year_of_construction
        if year_of_construction is None:
            year_decision = RealDecision("Enter value for the buildings year of construction",
                                         global_key="Building_%s.year_of_construction" % building.guid,
                                         allow_skip=False, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=False)
            year_decision.decide()
            building.year_of_construction = int(year_decision.value.m)

        year_of_construction = int(building.year_of_construction)
        template_options = []
        for i in instance_templates[instance_type]:
            years = ast.literal_eval(i)
            if years[0] <= year_of_construction <= years[1]:
                template_options = instance_templates[instance_type][i]
                break

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