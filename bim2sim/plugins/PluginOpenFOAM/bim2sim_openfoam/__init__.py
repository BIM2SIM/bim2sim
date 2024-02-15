"""Template plugin for bim2sim

Holds a plugin with only base tasks mostly for demonstration.
"""
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam import task as of_tasks
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import EnergyPlusSimSettings
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import \
    task as ep_tasks


class PluginOpenFOAM(Plugin):
    name = 'openfoam'
    sim_settings = EnergyPlusSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
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
        # ep_tasks.ExportIdfForCfd,
        ep_tasks.RunEnergyPlusSimulation,
        of_tasks.InitializeOpenFOAMProject
    ]
