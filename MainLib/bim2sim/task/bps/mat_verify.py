from bim2sim.workflow import LOD
from bim2sim.task.base import Task, ITask
from bim2sim.workflow import Workflow
from bim2sim.kernel.element import ProductBased
from bim2sim.kernel.units import ureg


class MaterialVerification(ITask):
    """Prepares bim2sim instances to later export"""

    reads = ('instances',)
    touches = ('invalid_materials',)

    def __init__(self):
        super().__init__()
        # self.invalid = []
        self.invalid = {}
        pass

    @Task.log
    def run(self, workflow: Workflow, instances: dict):
        self.logger.info("setting verifications")
        if workflow.layers is not LOD.low:
            for guid, ins in instances.items():
                if not self.materials_verification(ins):
                    # self.invalid.append(ins)
                    self.invalid[ins.guid] = ins
            self.logger.warning("Found %d invalid layers", len(self.invalid))
            dict_items = self.invalid.items()
            self.invalid = dict(sorted(dict_items))

        return self.invalid,

    def materials_verification(self, instance: ProductBased):
        """checks validity of the layer property values"""
        invalid = True
        if hasattr(instance, 'layers'):
            if len(instance.layers) > 0:
                for layer in instance.layers:
                    for attr in layer.attributes:
                        value = getattr(layer, attr)
                        if not self.value_verification(attr, value):
                            setattr(layer, attr, 'invalid')
                            invalid = False
        return invalid

    @staticmethod
    def value_verification(attr: str, value: ureg.Quantity):
        """checks validity of the properties if they are on the blacklist"""
        blacklist = ['density', 'thickness', 'heat_capac', 'thermal_conduc']
        if (value is None or value <= 0) and attr in blacklist:
            return False
        return True
