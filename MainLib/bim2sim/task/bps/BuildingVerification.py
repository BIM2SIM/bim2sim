import ast

from bim2sim.task.base import Task, ITask
from bim2sim.kernel.element import SubElement
from bim2sim.enrichment_data.data_class import DataClass
from bim2sim.decision import RealDecision
from bim2sim.task.common.common_functions import angle_equivalent


class BuildingVerification(ITask):
    """Prepares bim2sim instances to later export"""

    reads = ('instances',)
    touches = ('instances', 'invalid')

    def __init__(self):
        super().__init__()
        self.invalid = []
        pass

    @Task.log
    def run(self, workflow, instances):
        self.logger.info("setting verifications")
        self.check_building_year()

        for guid, ins in instances.items():
            if not self.layers_verification(ins):
                self.invalid.append(ins)
            new_orientation = self.orientation_verification(ins)
            if new_orientation is not None:
                ins.orientation = new_orientation
        self.logger.warning("Found %d invalid instances", len(self.invalid))

        return instances, self.invalid

    @staticmethod
    def check_building_year():
        building = SubElement.get_class_instances('Building')[0]
        if building.year_of_construction is None:
            year_decision = RealDecision("Enter value for the buildings year of construction",
                                         global_key="Building_%s.year_of_construction" % building.guid,
                                         allow_skip=False, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=False)
            year_decision.decide()
            building.year_of_construction = int(year_decision.value.m)

    @staticmethod
    def orientation_verification(instance):
        supported_classes = {'Window', 'OuterWall', 'OuterDoor', 'Wall', 'Door'}
        instance_type = type(instance).__name__
        if instance_type in supported_classes:
            new_angles = list(set([space_boundary.orientation for space_boundary in instance.space_boundaries]))
            # new_angles = list(set([space_boundary.orientation - space_boundary.thermal_zones[0].orientation for space_boundary in instance.space_boundaries]))
            if len(new_angles) > 1:
                return None
            # no true north necessary
            new_angle = angle_equivalent(new_angles[0])
            # new angle return
            if new_angle - instance.orientation > 0.1:
                return new_angle

    def layers_verification(self, instance):
        supported_classes = {'OuterWall', 'Wall', 'InnerWall', 'Door', 'InnerDoor', 'OuterDoor', 'Roof', 'Floor',
                             'GroundFloor', 'Window'}
        building = SubElement.get_class_instances('Building')[0]
        instance_type = type(instance).__name__
        if instance_type in supported_classes:
            # comparison with templates value
            layers_width, layers_u = self.get_layers_properties(instance)
            if not self.compare_instance_with_layers(instance, layers_u, layers_width):
                return False
            if not self.compare_with_template(instance, building):
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
    def compare_with_template(instance, building):
        template_options = []

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

    @staticmethod
    def compare_instance_with_layers(instance, layers_u, layers_width):
        # critical failure // u value comparison
        if instance.u_value == 0 and layers_u == 0:
            return False
        elif instance.u_value == 0 and layers_u > 0:
            instance.u_value = layers_u
        elif instance.u_value > 0 and layers_u > 0:
            instance.u_value = max(instance.u_value, layers_u)

        # critical failure // check units again
        width_discrepancy = abs(instance.width - layers_width) / instance.width if \
            (instance.width is not None and instance.width > 0) else 9999
        if width_discrepancy > 0.2:
            return False
        return True
