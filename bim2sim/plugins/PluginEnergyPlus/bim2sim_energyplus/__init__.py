"""EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim.kernel.elements import bps as bps_elements
from bim2sim.plugins import Plugin
from bim2sim.task import common, bps
from bim2sim.workflow import EnergyPlusWorkflow
from bim2sim.kernel.element import Material

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import task as ep_tasks


class PluginEnergyPlus(Plugin):
    name = 'EnergyPlus'
    default_workflow = EnergyPlusWorkflow
    allowed_workflows = [EnergyPlusWorkflow]
    elements = {*bps_elements.items, Material} - {bps_elements.Plate}
    default_tasks = [
        common.LoadIFC,
        bps.CheckIfcBPS,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.Prepare,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.Verification,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        bps.DisaggregationCreation,
        bps.BindThermalZones,
        ep_tasks.IfcValidation, #todo: add additional checks to CheckIfcBPS
        ep_tasks.EPGeomPreprocessing,
        ep_tasks.AddSpaceBoundaries2B,
        ep_tasks.WeatherEnergyPlus,
        ep_tasks.CreateIdf,
        ep_tasks.IdfPostprocessing,
        ep_tasks.ExportIdfForCfd,
        ep_tasks.RunEnergyPlusSimulation,
    ]
