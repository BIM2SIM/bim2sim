"""HKESim plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim.export.modelica import standardlibrary
from bim2sim.kernel.element import Material
from bim2sim.kernel.elements import hvac as hvac_elements
from bim2sim.plugins import Plugin
from bim2sim.task import base, common, hvac
from bim2sim.simulation_type import PlantSimulation
from .models import HKESim


class LoadLibrariesHKESim(base.ITask):
    """Load HKESim library for export"""
    touches = ('libraries', )

    def run(self, **kwargs):
        return (standardlibrary.StandardLibrary, HKESim),


class PluginHKESim(Plugin):
    name = 'HKESim'
    default_workflow = PlantSimulation
    tasks = {LoadLibrariesHKESim}
    elements = {*hvac_elements.items, Material}
    default_tasks = [
        common.LoadIFC,
        hvac.CheckIfcHVAC,
        common.CreateElements,
        hvac.ConnectElements,
        hvac.MakeGraph,
        hvac.ExpansionTanks,
        hvac.Reduce,
        hvac.DeadEnds,
        LoadLibrariesHKESim,
        hvac.Export,
    ]
