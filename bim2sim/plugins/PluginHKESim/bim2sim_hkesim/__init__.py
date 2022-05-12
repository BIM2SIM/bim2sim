"""HKESim plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim.export.modelica import standardlibrary
from bim2sim.kernel.elements import hvac as hvac_elements
from bim2sim.workflow import PlantSimulation
from bim2sim.plugins import Plugin

from .models import HKESim
from task import base, common, hvac


class LoadLibrariesHKESim(base.ITask):
    """Load HKESim library for export"""
    touches = ('libraries', )

    def run(self, workflow, **kwargs):
        return (standardlibrary.StandardLibrary, HKESim),


class PluginHKESim(Plugin):
    name = 'HKESim'
    default_workflow = PlantSimulation
    tasks = {LoadLibrariesHKESim}
    elements = {*hvac_elements.items}
    default_tasks = [
        common.LoadIFC,
        hvac.CheckIfcHVAC,
        common.CreateElements,
        hvac.ConnectElements,
        hvac.MakeGraph,
        hvac.Reduce,
        hvac.DeadEnds,
        LoadLibrariesHKESim,
        hvac.Export,
    ]
