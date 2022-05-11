"""EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim.kernel.elements import bps as bps_elements
from bim2sim.plugins import Plugin
from bim2sim.task import common, bps
from bim2sim.workflow import BPSMultiZoneSeparatedEP

import task as ep_tasks


class EnergyPlus(Plugin):
    name = 'EnergyPlus'
    default_workflow = BPSMultiZoneSeparatedEP
    elements = {*bps_elements.items}
    default_tasks = [
        common.LoadIFC,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.Prepare,
        bps.EnrichUseConditions,
        bps.OrientationGetter,
        bps.MaterialVerification,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        bps.BuildingVerification,  # all LODs
        bps.EnrichNonValid,  # LOD.full
        bps.EnrichBuildingByTemplates,  # LOD.low
        bps.DisaggregationCreation,
        bps.BindThermalZones,
        ep_tasks.IfcValidation,
        ep_tasks.EPGeomPreprocessing,
        ep_tasks.AddSpaceBoundaries2B,
        ep_tasks.WeatherEnergyPlus,
        ep_tasks.CreateIdf,
        ep_tasks.IdfPostprocessing,
        ep_tasks.ExportIdfForCfd,
        ep_tasks.RunEnergyPlusSimulation,
    ]