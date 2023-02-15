"""EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim.kernel.elements import bps as bps_elements
from bim2sim.plugins import Plugin
from bim2sim.task import common, bps
from bim2sim.workflow import EnergyPlusWorkflow
from bim2sim.kernel.element import Material

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task\
    .ep_ifc_validation import IfcValidation
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task\
    .ep_geom_preprocessing import EPGeomPreprocessing
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task.ep_add_2b_bounds\
    import AddSpaceBoundaries2B
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task.weather import \
    WeatherEnergyPlus
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task.ep_create_idf\
    import CreateIdf
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task.\
    ep_idf_postprocessing import IdfPostprocessing
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task.\
    ep_idf_cfd_export import ExportIdfForCfd
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task\
    .ep_run_simulation import RunEnergyPlusSimulation


class PluginEnergyPlus(Plugin):
    name = 'EnergyPlus'
    default_workflow = EnergyPlusWorkflow
    allowed_workflows = [EnergyPlusWorkflow]
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
        IfcValidation,
        EPGeomPreprocessing,
        AddSpaceBoundaries2B,
        WeatherEnergyPlus,
        CreateIdf,
        IdfPostprocessing,
        ExportIdfForCfd,
        RunEnergyPlusSimulation,
    ]
