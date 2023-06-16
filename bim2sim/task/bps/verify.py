from bim2sim.kernel.element import Material
from bim2sim.kernel.elements.bps import BPSProductWithLayers, LayerSet, Layer
from bim2sim.kernel.units import ureg
from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import all_subclasses, filter_instances
from bim2sim.utilities.types import LOD
from bim2sim.simulation_settings import SimSettings


class Verification(ITask):
    """Prepares bim2sim instances to later export"""

    reads = ('instances',)
    touches = ('invalid',)

    def __init__(self, playground):
        super().__init__(playground)
        self.invalid = []

    def run(self, instances: dict):
        self.logger.info("setting verifications")
        if self.playground.sim_settings.layers_and_materials is not LOD.low:
            materials = filter_instances(instances, Material)
            self.invalid.extend(self.materials_verification(materials))
            layers = filter_instances(instances, Layer)
            self.invalid.extend(self.layers_verification(layers))
            layer_sets = filter_instances(instances, LayerSet)
            self.invalid.extend(self.layer_sets_verification(layer_sets))
            self.invalid.extend(
                self.instances_with_layers_verification(instances))
            self.logger.warning("Found %d invalid instances", len(self.invalid))
        else:
            self.invalid.extend(
                self.instances_with_layers_verification(instances,
                                                        lod_low=True))
        self.invalid = {inv.guid: inv for inv in self.invalid}
        return self.invalid,

    def materials_verification(self, materials):
        """checks validity of the material property values"""
        invalid_layers = []
        for material in materials:
            invalid = False
            for attr in material.attributes:
                value = getattr(material, attr)
                if not self.value_verification(attr, value):
                    invalid = True
                    break
            if invalid:
                for layer in material.parents:
                    if layer not in invalid_layers:
                        invalid_layers.append(layer)
        sorted_layers = list(sorted(invalid_layers,
                                    key=lambda layer_e: layer_e.material.name))
        return sorted_layers

    def layers_verification(self, layers):
        """checks validity of the layer property values"""
        invalid_layers = []
        for layer in layers:
            if layer.guid not in self.invalid:
                invalid = True
                if layer.material:
                    if layer.thickness is not None:
                        invalid = False
                if invalid:
                    invalid_layers.append(layer)
        sorted_layers = list(sorted(invalid_layers,
                                    key=lambda layer_e: layer_e.material.name))
        return sorted_layers

    @staticmethod
    def layer_sets_verification(layer_sets):
        """checks validity of the layer set property values"""
        invalid_layer_sets = []
        for layer_set in layer_sets:
            invalid = True
            if len(layer_set.layers):
                if layer_set.total_thickness is not None:
                    invalid = False
            if invalid:
                invalid_layer_sets.append(layer_set)
        sorted_layer_sets = list(sorted(invalid_layer_sets,
                                        key=lambda layer_set_e:
                                        layer_set_e.name))
        return sorted_layer_sets

    @staticmethod
    def instances_with_layers_verification(instances, lod_low=False):
        invalid_instances = []
        layer_classes = list(all_subclasses(BPSProductWithLayers))
        for inst in instances.values():
            if type(inst) in layer_classes:
                if not lod_low:
                    invalid = True
                    if inst.layerset:
                        invalid = False
                    if invalid:
                        invalid_instances.append(inst)
                else:
                    invalid_instances.append(inst)
        return invalid_instances

    @staticmethod
    def value_verification(attr: str, value: ureg.Quantity):
        """checks validity of the properties if they are on the blacklist"""
        blacklist = ['density', 'spec_heat_capacity', 'thermal_conduc']
        if (value is None or value <= 0) and attr in blacklist:
            return False
        return True
