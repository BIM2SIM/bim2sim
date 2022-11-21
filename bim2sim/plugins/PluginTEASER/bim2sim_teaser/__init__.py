"""TEASER plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim.kernel.elements import bps as bps_elements
from bim2sim.kernel.element import Material
from bim2sim.plugins import Plugin
from bim2sim.workflow import BuildingSimulation
from bim2sim.task import common, bps, base
from bim2sim_teaser import task as teaser_task
from bim2sim_teaser.models import TEASER


class LoadLibrariesTEASER(base.ITask):
    """Load AixLib library for export"""
    touches = ('libraries', )

    def run(self, workflow, **kwargs):
        return (TEASER,),


class TEASERManager(Plugin):
    name = 'TEASER'
    default_workflow = BuildingSimulation
    elements = {*bps_elements.items, Material} - {bps_elements.Plate}
    allowed_workflows = [
        BuildingSimulation,
    ]
    default_tasks = [
        common.LoadIFC,
        bps.CheckIfcBPS,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.Prepare,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.Verification,
        bps.EnrichMaterial,
        bps.DisaggregationCreation,
        bps.BindThermalZones,
        teaser_task.WeatherTEASER,
        LoadLibrariesTEASER,
        teaser_task.ExportTEASER,
        teaser_task.SimulateModel,
    ]
