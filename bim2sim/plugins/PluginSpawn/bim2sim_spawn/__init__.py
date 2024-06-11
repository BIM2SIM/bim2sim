from bim2sim.plugins import Plugin
from bim2sim.tasks import base, common, hvac, bps
from bim2sim.sim_settings import BuildingSimSettings, EnergyPlusSimSettings
import bim2sim.plugins.PluginSpawn.bim2sim_spawn.tasks as spawn_tasks
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import task as ep_tasks


# # TODO: this is just a concept and not working already
class PluginSpawnOfEP(Plugin):
    name = 'spawn'
    sim_settings = EnergyPlusSimSettings
    default_tasks = [
        common.LoadIFC,
        # common.CheckIfc,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.CorrectSpaceBoundaries,
        bps.AddSpaceBoundaries2B,
        bps.FilterTZ,
        # bps.ProcessSlabsRoofs,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.VerifyLayersMaterials,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        common.Weather,
        ep_tasks.CreateIdf,
        # ep_tasks.IdfPostprocessing,
        # ep_tasks.ExportIdfForCfd,
        # ep_tasks.RunEnergyPlusSimulation,
        spawn_tasks.ExportSpawnBuilding,
    ]
