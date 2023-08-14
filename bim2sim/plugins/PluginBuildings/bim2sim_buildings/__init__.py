import re
from ast import literal_eval

from bim2sim.export.modelica import standardlibrary
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginBuildings.bim2sim_buildings.models import Buildings
from bim2sim.tasks import base, common, hvac
from bim2sim.sim_settings import BuildingSimSettings
import bim2sim.plugins.PluginSpawn.bim2sim_spawn.tasks as spawn_tasks


class LoadLibrariesBuildings(base.ITask):
    """Load AixLib library for export"""
    touches = ('libraries', )

    def run(self, **kwargs):
        return (standardlibrary.StandardLibrary, Buildings),

    def overwrite_standarlib_models(self):
        pass


class PluginBuildings(Plugin):
    name = 'Buildings'
    sim_settings = BuildingSimSettings
    tasks = {LoadLibrariesBuildings}
    default_tasks = [
        # common.LoadIFC,
        # common.CreateElements,
        spawn_tasks.CreateSpawnElements,
        LoadLibrariesBuildings,
        spawn_tasks.ExportModelicaSpawn,
    ]
