
"""EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim.task.base import ITask
from bim2sim.kernel.elements import bps as bps_elements
from bim2sim.plugins import Plugin
from bim2sim.task import common, bps
from bim2sim.workflow import EnergyPlusWorkflow, WorkflowSetting
from bim2sim.kernel.element import Material

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import task as ep_tasks
from bim2sim.plugins.PluginComfort.bim2sim_comfort import task as comfort_tasks

from bim2sim.workflow import EnergyPlusWorkflow


class ComfortWorkflow(EnergyPlusWorkflow):
    pass


class PluginComfort(Plugin):
    name = 'comfort'
    default_workflow = ComfortWorkflow
    allowed_workflows = [ComfortWorkflow]
    elements = {*bps_elements.items, Material} - {bps_elements.Plate}
    default_tasks = [
        common.LoadIFC,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.Prepare,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.Verification,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        bps.DisaggregationCreation,
        bps.BindThermalZones,
        ep_tasks.IfcValidation,
        ep_tasks.EPGeomPreprocessing,
        ep_tasks.AddSpaceBoundaries2B,
        ep_tasks.WeatherEnergyPlus,
        ep_tasks.CreateIdf,
        comfort_tasks.ComfortSettings,
        ep_tasks.ExportIdfForCfd,
        ep_tasks.RunEnergyPlusSimulation,
        comfort_tasks.ComfortVisualization,
    ]