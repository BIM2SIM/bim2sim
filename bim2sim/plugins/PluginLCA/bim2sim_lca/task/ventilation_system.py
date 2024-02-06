import bim2sim
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.plugins.PluginLCA.bim2sim_lca.task import DesignSupplyLCA
from bim2sim.plugins.PluginLCA.bim2sim_lca.task import DesignExaustLCA

class DesignVentilationSystem(ITask):
    """Design of the LCA

    Annahmen:
    Inputs: IFC Modell, Räume,

    Args:
        instances: bim2sim elements
    Returns:
        instances: bim2sim
    """
    reads = ('instances',)
    touches = ()

    a = "test"



    def run(self, instances):

        print("Test")