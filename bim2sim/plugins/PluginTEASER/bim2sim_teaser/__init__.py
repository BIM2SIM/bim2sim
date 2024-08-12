"""TEASER plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
import bim2sim.plugins.PluginTEASER.bim2sim_teaser.task as teaser_task
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginTEASER.bim2sim_teaser.models import TEASER
from bim2sim.tasks import common, bps, base
from bim2sim.sim_settings import TEASERSimSettings


class LoadLibrariesTEASER(base.ITask):
    """Load AixLib library for export"""
    touches = ('libraries', )

    def run(self, **kwargs):
        return (TEASER,),


class PluginTEASER(Plugin):
    name = 'TEASER'
    sim_settings = TEASERSimSettings
    default_tasks = [
        common.LoadIFC,
        # common.CheckIfc,
        common.CreateElementsOnIfcTypes,
        bps.CreateSpaceBoundaries,
        bps.AddSpaceBoundaries2B,
        bps.CorrectSpaceBoundaries,
        common.CreateRelations,
        bps.DisaggregationCreationAndTypeCheck,
        bps.EnrichMaterial,
        bps.EnrichUseConditions,
        bps.CombineThermalZones,
        common.Weather,
        LoadLibrariesTEASER,
        teaser_task.CreateTEASER,
        common.SerializeElements,
        teaser_task.ExportTEASER,
        teaser_task.SimulateModelEBCPy,
        teaser_task.CreateResultDF,
        bps.PlotBEPSResults,
    ]
