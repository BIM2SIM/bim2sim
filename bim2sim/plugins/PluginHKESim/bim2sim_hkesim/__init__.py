"""HKESim plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim.export.modelica import standardlibrary
from bim2sim.plugins import Plugin
from bim2sim.tasks import base, hvac, common
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
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElementsOnIfcTypes,
        hvac.ConnectElements,
        hvac.MakeGraph,
        hvac.ExpansionTanks,
        hvac.Reduce,
        hvac.DeadEnds,
        LoadLibrariesHKESim,
        hvac.CreateModelicaModel,
        hvac.Export,
    ]
