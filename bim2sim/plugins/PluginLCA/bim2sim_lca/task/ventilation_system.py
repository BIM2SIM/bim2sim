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
    reads = ('druckverlust_zuluft',
             'datenbank_raeume_zuluft',
             'datenbank_verteilernetz_zuluft',
             'druckverlust_exhaust', 'datenbank_raeume_exhaust',
             'datenbank_verteilernetz_exhaust')
    touches = ()

    def run(self, druckverlust_zuluft,
            datenbank_raeume_zuluft,
            datenbank_verteilernetz_zuluft,
            druckverlust_exhaust,
            datenbank_raeume_exhaust,
            datenbank_verteilernetz_exhaust
            ):
        print(druckverlust_exhaust)
