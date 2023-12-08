
"""EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from pathlib import Path

from bim2sim.elements import bps_elements
from bim2sim.elements.base_elements import Material
from bim2sim.plugins import Plugin
from bim2sim.sim_settings import ComfortSimSettings
from bim2sim.tasks import common, bps

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import \
    task as ep_tasks, EnergyPlusSimSettings
from bim2sim.plugins.PluginComfort.bim2sim_comfort import task as comfort_tasks


class PluginComfort(Plugin):
    name = 'Comfort'
    sim_settings = ComfortSimSettings
    elements = {*bps_elements.items, Material} - {bps_elements.Plate}
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.Prepare,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.VerifyLayersMaterials,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        ep_tasks.EPGeomPreprocessing,
        ep_tasks.AddSpaceBoundaries2B,
        common.Weather,
        ep_tasks.CreateIdf,
        comfort_tasks.ComfortSettings,
        ep_tasks.ExportIdfForCfd,
        ep_tasks.RunEnergyPlusSimulation,
        # comfort_tasks.ComfortVisualization,
    ]
