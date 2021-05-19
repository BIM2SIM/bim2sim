from bim2sim.plugin import Plugin
from bim2sim.task import common
from bim2sim.workflow import BPSMultiZoneSeparatedLayersLow
from bim2sim.kernel.elements import bps as bps_elements
from bim2sim.task import bps


class TEASERManager(Plugin):
    name = 'TEASER'
    default_workflow = BPSMultiZoneSeparatedLayersLow
    elements = {*bps_elements.items}

    def run(self, playground):
        playground.run_task(bps.SetIFCTypes())
        playground.run_task(common.LoadIFC())
        playground.run_task(common.CreateElements())
        playground.run_task(bps.CreateSpaceBoundaries())
        playground.run_task(bps.TZPrepare())
        playground.run_task(bps.EnrichUseConditions())
        playground.run_task(bps.OrientationGetter())

        playground.run_task(bps.MaterialVerification())  # LOD.full
        playground.run_task(bps.EnrichMaterial())  # LOD.full
        playground.run_task(bps.BuildingVerification())  # all LODs

        playground.run_task(bps.EnrichNonValid())  # LOD.full
        playground.run_task(bps.EnrichBuildingByTemplates())  # LOD.low

        playground.run_task(bps.Disaggregation_creation())
        playground.run_task(bps.BindThermalZones())
        playground.run_task(bps.ExportTEASER())
        pass
