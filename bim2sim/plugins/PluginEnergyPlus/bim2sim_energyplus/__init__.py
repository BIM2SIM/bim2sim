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
        common.CreateElementsOnIfcTypes,
        bps.CreateSpaceBoundaries,
        bps.AddSpaceBoundaries2B,
        bps.CorrectSpaceBoundaries,
        common.BindStoreys,
        bps.DisaggregationCreationAndTypeCheck,
        bps.EnrichMaterial,
        bps.EnrichUseConditions,
        common.Weather,
        ep_tasks.CreateIdf,
        ep_tasks.IdfPostprocessing,
        ep_tasks.ExportIdfForCfd,
        common.SerializeElements,
        ep_tasks.RunEnergyPlusSimulation,
        ep_tasks.CreateResultDF,
        # ep_tasks.VisualizeResults,
        bps.PlotBEPSResults,
    ]
