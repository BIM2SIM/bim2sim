"""HKESim plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
import bim2sim.tasks.common.check_ifc
import bim2sim.tasks.common.create_elements
import bim2sim.tasks.common.load_ifc
from bim2sim.export.modelica import standardlibrary
from bim2sim.plugins import Plugin
from bim2sim.tasks import base, common, hvac
from bim2sim.sim_settings import PlantSimSettings
from .models import HKESim


class LoadLibrariesHKESim(base.ITask):
    """Load HKESim library for export"""
    touches = ('libraries', )

    def run(self, **kwargs):
        return (standardlibrary.StandardLibrary, HKESim),


class PluginHKESim(Plugin):
    name = 'HKESim'
    sim_settings = PlantSimSettings
    tasks = {LoadLibrariesHKESim}
    default_tasks = [
        bim2sim.tasks.common.load_ifc.LoadIFC,
        bim2sim.tasks.common.check_ifc.CheckIfc,
        bim2sim.tasks.common.create_elements.CreateElements,
        hvac.ConnectElements,
        hvac.MakeGraph,
        hvac.ExpansionTanks,
        hvac.Reduce,
        hvac.DeadEnds,
        LoadLibrariesHKESim,
        hvac.Export,
    ]
