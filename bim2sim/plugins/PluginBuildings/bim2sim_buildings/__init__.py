import re
from ast import literal_eval

from bim2sim.export.modelica import standardlibrary
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginBuildings.bim2sim_buildings.models import Buildings
from bim2sim.tasks import base, common, hvac, bps
from bim2sim.sim_settings import BuildingSimSettings, EnergyPlusSimSettings
import bim2sim.plugins.PluginSpawn.bim2sim_spawn.tasks as spawn_tasks
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import task as ep_tasks


class LoadLibrariesBuildings(base.ITask):
    """Load AixLib library for export"""
    touches = ('libraries', )

    def run(self, **kwargs):
        return (standardlibrary.StandardLibrary, Buildings),

    def overwrite_standarlib_models(self):
        pass


class PluginBuildings(Plugin):
    name = 'Buildings'
    sim_settings = EnergyPlusSimSettings
    tasks = {LoadLibrariesBuildings}
    default_tasks = [
        common.LoadIFC,
        # common.CheckIfc,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.FilterTZ,
        bps.ProcessSlabsRoofs,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.VerifyLayersMaterials,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        ep_tasks.EPGeomPreprocessing,
        ep_tasks.AddSpaceBoundaries2B,
        common.Weather,
        ep_tasks.CreateIdf,
        # ep_tasks.IdfPostprocessing,
        # ep_tasks.ExportIdfForCfd,
        # ep_tasks.RunEnergyPlusSimulation,
        spawn_tasks.CreateSpawnElements,
        LoadLibrariesBuildings,
        spawn_tasks.ExportModelicaSpawn,
    ]
