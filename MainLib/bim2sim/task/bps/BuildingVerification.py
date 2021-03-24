import ast

from bim2sim.task.base import Task, ITask
from bim2sim.kernel.element import SubElement
from bim2sim.task.common.common_functions import get_type_building_elements, get_material_templates
from bim2sim.decision import ListDecision
from bim2sim.workflow import LOD


class BuildingVerification(ITask):
    """Prepares bim2sim instances to later export"""

    reads = ('instances',)
    touches = ('invalid_layers',)

    def __init__(self):
        super().__init__()
        self.invalid_layers = []
        pass

    @Task.log
    def run(self, workflow, instances,):
        self.logger.info("setting verifications")
        for guid, ins in instances.items():
            if not self.layers_verification(ins, workflow):
                self.invalid_layers.append(ins)
        self.logger.warning("Found %d invalid layers", self.invalid_layers)

        return self.invalid_layers,

    def layers_verification(self, instance, workflow):
        supported_classes = {'OuterWall', 'Wall', 'InnerWall', 'Door', 'InnerDoor', 'OuterDoor', 'Roof', 'Floor',
                             'GroundFloor', 'Window'}
        instance_type = type(instance).__name__
        if instance_type in supported_classes:
            if len(instance.layers) == 0:  # no layers given
                return False
            layers_width, layers_u = self.get_layers_properties(instance)
            if not self.width_comparison(workflow, instance, layers_width):
                return False
            if not self.u_value_comparison(instance, layers_u):
                return False
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
    def width_comparison(workflow, instance, layers_width):
        # critical failure
        if workflow.layers is not LOD.low:
            return True
        else:
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
            u_selection = ListDecision(
                "Multiple possibilities found for u_value\n"
                "Belonging Item: %s | GUID: %s \n"
                "Enter 'n' for manual input"
                % (instance.name, instance.guid),
                choices=[instance.u_value, layers_u], global_key='%s_u_value' % instance.name,
                allow_skip=True, allow_load=True, allow_save=True,
                collect=False, quick_decide=not True, context=instance.name, related=instance.guid)
            u_selection.decide()
            instance.u_value = u_selection.value
        return True

    @staticmethod
    def compare_with_template(instance, tolerance=0.2):
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
        if template_options[0] * (1-tolerance) <= instance.u_value.m <= template_options[1] * (1 + tolerance):
            return True
        return False
