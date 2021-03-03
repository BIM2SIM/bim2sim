import ast

from bim2sim.task.base import Task, ITask
from bim2sim.task.common.common_functions import get_matches_list, get_material_templates_resumed, \
    real_decision_user_input
from bim2sim.decision import BoolDecision, ListDecision
from bim2sim.kernel.elements import Layer


class EnrichMaterial(ITask):
    """Prepares bim2sim instances to later export"""

    reads = ('instances',)
    touches = ('instances',)

    def __init__(self):
        super().__init__()
        # self.material_selected = {}
        self.material_selected = {'Stahlbeton 2747937872': {
            'density':1, 'heat_capac':2, 'thermal_conduc':3, 'thickness':4}}

        pass

    @Task.log
    def run(self, workflow, instances):
        self.logger.info("setting verifications")
        for guid, ins in instances.items():
            self.get_layer_properties(ins)

    def get_layer_properties(self, instance):
        if hasattr(instance, 'layers'):
            for layer in instance.layers:
                self.get_material_properties(layer, 'thickness')
                print()

    def get_material_properties(self, layer, name, tc_range=None):
        attributes = self.get_layer_attributes(layer)
        material = layer.material

        if material in self.material_selected:
            for attr in attributes:

            if name in self.material_selected[material]:
                # check if range is given
                if tc_range is not None:
                    if tc_range[0] < self.material_selected[material][name] < tc_range[1]:
                        return self.material_selected[material][name]
                else:
                    return self.material_selected[material][name]

        if name == 'thickness':
            name = 'thickness_default'

        # check if material new properties are previously stored
        material = layer.material
        if material in self.material_selected:
            if name in self.material_selected[material]:
                # check if range is given
                if tc_range is not None:
                    if tc_range[0] < self.material_selected[material][name] < tc_range[1]:
                        return self.material_selected[material][name]
                else:
                    return self.material_selected[material][name]
            else:
                return real_decision_user_input(layer, name)
        else:
            resumed = get_material_templates_resumed(name, tc_range)
            try:
                selected_properties = resumed[material]
            except KeyError:
                first_decision = BoolDecision(
                    question="Do you want to enrich the layers with the material %s by using available templates? \n"
                             "Belonging Item: %s | GUID: %s \n"
                             "Enter 'n' for manual input"
                             % (layer.material, layer.parent.name, layer.parent.guid),
                    collect=False, global_key='%s_layer_enriched' % layer.material,
                    allow_load=True, allow_save=True)
                first_decision.decide()
                first_decision.stored_decisions.clear()

                if first_decision.value:
                    if layer.material in resumed:
                        self.material_selected[material] = resumed[material]
                        return self.material_selected[layer.material][name]

                    material_options = get_matches_list(layer.material, list(resumed.keys()))

                    if tc_range is None:
                        while len(material_options) == 0:
                            decision_ = input(
                                "Material not found, enter value for the material:")
                            material_options = get_matches_list(decision_, list(resumed.keys()))
                    else:
                        material_options = list(resumed.keys())

                    decision1 = ListDecision(
                        "Multiple possibilities found for material %s\n"
                        "Belonging Item: %s | GUID: %s \n"
                        "Enter 'n' for manual input"
                        % (layer.material, layer.parent.name, layer.parent.guid),
                        choices=list(material_options), global_key='%s_material_enrichment' % self.material,
                        allow_skip=True, allow_load=True, allow_save=True,
                        collect=False, quick_decide=not True)
                    decision1.decide()

                    if material is not None:
                        if material not in self.material_selected:
                            self.material_selected[material] = {}
                        self.material_selected[material] = resumed[decision1.value]
                    else:
                        layer.material = decision1.value
                        self.material_selected[layer.material] = resumed[decision1.value]
                    return self.material_selected[layer.material][name]
                else:
                    return real_decision_user_input(layer, name)
            else:
                if material not in self.material_selected:
                    self.material_selected[material] = {}
                self.material_selected[material] = selected_properties
                return self.material_selected[layer.material][name]

    @staticmethod
    def get_layer_attributes(layer):
        attributes = {}
        for attr in layer.attributes:
            attributes[attr] = getattr(layer, attr)

        return attributes
