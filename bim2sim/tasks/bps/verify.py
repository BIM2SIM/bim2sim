from bim2sim.elements.base_elements import Material
from bim2sim.elements.bps_elements import BPSProductWithLayers, LayerSet, Layer
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import all_subclasses, filter_elements
from bim2sim.utilities.types import LOD


class VerifyLayersMaterials(ITask):
    """Verifies if layers and materials and their properties are meaningful."""

    reads = ('elements',)
    touches = ('invalid',)

    def __init__(self, playground):
        super().__init__(playground)
        self.invalid = []

    def run(self, elements: dict):
        self.logger.info("setting verifications")
        # TODO rework how invalids are assigned and use disaggregations instead
        #  elements if existing
        if self.playground.sim_settings.layers_and_materials is not LOD.low:
            materials = filter_elements(elements, Material)
            self.invalid.extend(self.materials_verification(materials))
            layers = filter_elements(elements, Layer)
            self.invalid.extend(self.layers_verification(layers))
            layer_sets = filter_elements(elements, LayerSet)
            self.invalid.extend(self.layer_sets_verification(layer_sets))
            self.invalid.extend(
                self.elements_with_layers_verification(elements))
            self.logger.warning("Found %d invalid elements", len(self.invalid))
        else:
            self.invalid.extend(
                self.elements_with_layers_verification(elements,
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
                if layer_set.thickness is not None:
                    invalid = False
            if invalid:
                invalid_layer_sets.append(layer_set)
        sorted_layer_sets = list(sorted(invalid_layer_sets,
                                        key=lambda layer_set_e:
                                        layer_set_e.name))
        return sorted_layer_sets

    @staticmethod
    def elements_with_layers_verification(elements, lod_low=False):
        invalid_elements = []
        layer_classes = list(all_subclasses(BPSProductWithLayers))
        for inst in elements.values():
            if type(inst) in layer_classes:
                if not lod_low:
                    invalid = False
                    if not inst.layerset and not inst.material_set:
                        invalid = True
                    if invalid:
                        invalid_elements.append(inst)
                else:
                    invalid_elements.append(inst)
        return invalid_elements

    @staticmethod
    def value_verification(attr: str, value: ureg.Quantity):
        """checks validity of the properties if they are on the blacklist"""
        blacklist = ['density', 'spec_heat_capacity', 'thermal_conduc']
        if (value is None or value <= 0) and attr in blacklist:
            return False
        return True
