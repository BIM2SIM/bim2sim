
"""EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from pathlib import Path

from bim2sim.elements import bps_elements
from bim2sim.elements.base_elements import Material
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginComfort.bim2sim_comfort.sim_settings import \
    ComfortSimSettings
from bim2sim.tasks import common, bps

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import \
    task as ep_tasks
from bim2sim.plugins.PluginComfort.bim2sim_comfort import task as comfort_tasks


class PluginComfort(Plugin):
    name = 'Comfort'
    sim_settings = ComfortSimSettings
    elements = {*bps_elements.items, Material}
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
        ep_tasks.IdfPostprocessing,
        comfort_tasks.ComfortSettings,
        ep_tasks.ExportIdfForCfd,
        ep_tasks.RunEnergyPlusSimulation,
        common.SerializeElements,
        ep_tasks.CreateResultDF,
        comfort_tasks.CreateResultDF,
        comfort_tasks.PlotComfortResults,
        # comfort_tasks.ComfortVisualization,
    ]
