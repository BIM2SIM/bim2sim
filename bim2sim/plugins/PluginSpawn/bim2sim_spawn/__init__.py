import bim2sim.plugins.PluginSpawn.bim2sim_spawn.tasks as spawn_tasks
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import \
    task as ep_tasks
from bim2sim.plugins.PluginSpawn.bim2sim_spawn.sim_settings import \
    SpawnOfEnergyPlusSimSettings
from bim2sim.tasks import common, hvac, bps
from bim2sim_aixlib import LoadLibrariesAixLib


class PluginSpawnOfEP(Plugin):
    """Plugin for SpawnOfEnergyPlus.

    This is the first plugin that uses tasks from different plugins together.
    We first execute the EnergyPlus related tasks to create an IDF file.
    Afterwards, we execute the HVAC tasks, using PluginAixLib (PluginHKESim
    would also work) and then execute the PluginSpawn tasks to put
    EnergyPlus IDF and Modelica model together.
    """
    name = 'spawn'
    sim_settings = SpawnOfEnergyPlusSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElementsOnIfcTypes,

        bps.CreateSpaceBoundaries,
        bps.AddSpaceBoundaries2B,
        bps.CorrectSpaceBoundaries,
        common.CreateRelations,
        bps.DisaggregationCreationAndTypeCheck,
        bps.EnrichMaterial,
        bps.EnrichUseConditions,
        common.Weather,
        ep_tasks.CreateIdf,

        hvac.ConnectElements,
        hvac.MakeGraph,
        hvac.ExpansionTanks,
        hvac.Reduce,
        hvac.DeadEnds,
        LoadLibrariesAixLib,
        hvac.CreateModelicaModel,
        hvac.Export,

        spawn_tasks.ExportSpawnBuilding,
        spawn_tasks.ExportSpawnTotal,
    ]
