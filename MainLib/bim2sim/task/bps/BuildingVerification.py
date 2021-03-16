import ast

from bim2sim.task.base import Task, ITask
from bim2sim.kernel.element import SubElement
from bim2sim.task.common.common_functions import get_type_building_elements, get_material_templates


class BuildingVerification(ITask):
    """Prepares bim2sim instances to later export"""

    reads = ('instances', 'invalid')
    touches = ('instances', 'invalid')

    def __init__(self):
        super().__init__()
        pass

    @Task.log
    def run(self, workflow, instances, invalid):
        invalid['layers'] = []
        self.logger.info("setting verifications")
        for guid, ins in instances.items():
            if not self.layers_verification(ins):
                invalid['layers'].append(ins)
        self.logger.warning("Found %d invalid layers", len(invalid['layers']))

        return instances, invalid,

    def layers_verification(self, instance):
        supported_classes = {'OuterWall', 'Wall', 'InnerWall', 'Door', 'InnerDoor', 'OuterDoor', 'Roof', 'Floor',
                             'GroundFloor', 'Window'}
        instance_type = type(instance).__name__
        if instance_type in supported_classes:
            if len(instance.layers) == 0:  # no layers given
                return False
            # layers_width, layers_u = self.get_layers_properties(instance)
            # if not self.width_comparison(instance, layers_width):
            #     return False
            # if not self.u_value_comparison(instance, layers_u):
            #     return False
            if not self.compare_with_template(instance):
                return False

        return True

    @staticmethod
    def get_layers_properties(instance):
        layers_width = 0
        layers_r = 0
        layers_u = 0
        for layer in instance.layers:
            layers_width += layer.thickness
            if layer.thermal_conduc is not None:
                if layer.thermal_conduc > 0:
                    layers_r += layer.thickness / layer.thermal_conduc

        if layers_r > 0:
            layers_u = 1 / layers_r

        if instance.u_value is None:
            instance.u_value = 0

        return layers_width, layers_u

    @staticmethod
    def width_comparison(instance, layers_width):
        # critical failure
        width_discrepancy = abs(instance.width - layers_width) / instance.width if \
            (instance.width is not None and instance.width > 0) else 9999
        if width_discrepancy > 0.2:
            return False
        return True

    @staticmethod
    def u_value_comparison(instance, layers_u):
        # critical failure
        if instance.u_value == 0 and layers_u == 0:
            return False
        elif instance.u_value == 0 and layers_u > 0:
            instance.u_value = layers_u
        elif instance.u_value > 0 and layers_u > 0:
            instance.u_value = max(instance.u_value, layers_u)
        return True

    def compare_with_template(self, instance):
        template_options = []
        building = SubElement.get_class_instances('Building')[0]

        year_of_construction = building.year_of_construction.m
        instance_templates = get_type_building_elements()
        material_templates = get_material_templates()
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
        if template_options[0] * 0.8 <= instance.u_value.m <= template_options[1] * 1.2:
            return True
        return False
