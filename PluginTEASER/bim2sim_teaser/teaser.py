from abc import ABC

from bim2sim.plugin import Plugin
from bim2sim.task import common
from bim2sim.workflow import BPSMultiZoneSeparatedLayersLow,\
    BPSMultiZoneSeparatedLayersFull, BPSMultiZoneCombinedLayersFull, \
    BPSMultiZoneCombinedLayersLow, BPSOneZoneAggregatedLayersLow
from bim2sim.kernel.elements import bps as bps_elements
from bim2sim.task import bps


class PluginTEASER(Plugin):
    name = 'TEASER'
    default_workflow = BPSMultiZoneSeparatedLayersLow
    allowed_workflows = [
        BPSOneZoneAggregatedLayersLow,
        BPSMultiZoneCombinedLayersLow,
        BPSMultiZoneCombinedLayersFull,
        BPSMultiZoneSeparatedLayersLow,
        BPSMultiZoneSeparatedLayersFull,
    ]
    elements = {*bps_elements.items}

    default_tasks = [
        bps.SetIFCTypes,
        common.LoadIFC,
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
        bps.ExportTEASER,
    ]
