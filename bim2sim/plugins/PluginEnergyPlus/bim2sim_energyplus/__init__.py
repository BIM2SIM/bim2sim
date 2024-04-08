"""EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim.plugins import Plugin
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import EnergyPlusSimSettings

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import task as ep_tasks


class PluginEnergyPlus(Plugin):
    name = 'EnergyPlus'
    sim_settings = EnergyPlusSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.CorrectSpaceBoundaries,
        bps.FilterTZ,
        # bps.ProcessSlabsRoofs,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.VerifyLayersMaterials,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        ep_tasks.AddSpaceBoundaries2B,
        common.Weather,
        ep_tasks.CreateIdf,
        ep_tasks.IdfPostprocessing,
        ep_tasks.ExportIdfForCfd,
        ep_tasks.RunEnergyPlusSimulation,
        ep_tasks.CreateResultDF,
        # ep_tasks.VisualizeResults,
        bps.PlotBEPSResults,
    ]
