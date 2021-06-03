from bim2sim.plugin import Plugin
from bim2sim.task import common
from bim2sim.workflow import BPSMultiZoneSeparatedLayersLow, BPSMultiZoneSeparatedLayersFull, \
    BPSMultiZoneCombinedLayersFull, BPSMultiZoneCombinedLayersLow, BPSOneZoneAggregatedLayersLow
from bim2sim.kernel.elements import bps as bps_elements
from bim2sim.task import bps


class TEASERManager(Plugin):
    name = 'TEASER'
    # default_workflow = BPSMultiZoneSeparatedLayersLow
    # default_workflow = BPSMultiZoneSeparatedLayersFull
    # default_workflow = BPSMultiZoneCombinedLayersLow
    # default_workflow = BPSOneZoneAggregatedLayersLow
    default_workflow = BPSMultiZoneCombinedLayersFull
    elements = {*bps_elements.items}
    default_tasks = [
        bps.SetIFCTypes,
        common.LoadIFC,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.TZPrepare,
        bps.EnrichUseConditions,
        bps.OrientationGetter,
        bps.MaterialVerification,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        bps.BuildingVerification,  # all LODs
        bps.EnrichNonValid,  # LOD.full
        bps.EnrichBuildingByTemplates,  # LOD.low
        bps.DisaggregationCreation,
        bps.BindThermalZones,
        bps.ExportTEASER,
    ]

