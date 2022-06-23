"""TEASER plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim_teaser import task as teaser
from bim2sim.kernel.elements import bps as bps_elements
from bim2sim.plugins import Plugin
from bim2sim.task import common, bps
from bim2sim.workflow import BPSMultiZoneCombinedLayersFull


class TEASERManager(Plugin):
    name = 'TEASER'
    # default_workflow = BPSMultiZoneSeparatedLayersLow
    # default_workflow = BPSMultiZoneSeparatedLayersFull
    # default_workflow = BPSMultiZoneCombinedLayersLow
    # default_workflow = BPSOneZoneAggregatedLayersLow
    default_workflow = BPSMultiZoneCombinedLayersFull
    elements = {*bps_elements.items}

    default_tasks = [
        common.LoadIFC,
        bps.CheckIfcBPS,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.Prepare,
        bps.EnrichUseConditions,
        bps.OrientationGetter,
        bps.MaterialVerification,  # layers -> LOD.full
        bps.EnrichMaterial,  # layers -> LOD.full
        bps.BuildingVerification,  # all layers LODs
        bps.EnrichNonValid,  # spaces -> LOD.full
        bps.EnrichBuildingByTemplates,  # spaces -> LOD.low
        bps.DisaggregationCreation,
        bps.BindThermalZones,
        teaser.WeatherTEASER,
        teaser.ExportTEASER,
        teaser.SimulateModel,
    ]