"""TEASER plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
import bim2sim.plugins.PluginTEASER.bim2sim_teaser.task as teaser_task
from bim2sim.kernel.element import Material
from bim2sim.kernel.elements import bps as bps_elements
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginTEASER.bim2sim_teaser.models import TEASER
from bim2sim.task import common, bps, base
from bim2sim.simulation_settings import BuildingSimulation


class LoadLibrariesTEASER(base.ITask):
    """Load AixLib library for export"""
    touches = ('libraries', )

    def run(self, **kwargs):
        return (TEASER,),


class PluginTEASER(Plugin):
    name = 'TEASER'
    settings = BuildingSimulation
    elements = {*bps_elements.items, Material} - {bps_elements.Plate}
    allowed_workflows = [
        BuildingSimulation,
    ]
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.Prepare,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.Verification,
        bps.EnrichMaterial,
        bps.DisaggregationCreation,
        bps.CombineThermalZones,
        teaser_task.WeatherTEASER,
        LoadLibrariesTEASER,
        teaser_task.ExportTEASER,
        teaser_task.SimulateModel,
    ]
