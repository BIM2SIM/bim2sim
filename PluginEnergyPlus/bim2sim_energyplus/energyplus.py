from shutil import copyfile
from pathlib import Path

from bim2sim.task import bps
from bim2sim.task import common
from bim2sim.plugin import Plugin
from bim2sim.workflow import BPSMultiZoneSeparatedEP


class EnergyPlus(Plugin):
    name = 'EnergyPlus'
    default_workflow = BPSMultiZoneSeparatedEP

    def run(self, playground):
        weather_file = 'DEU_NW_Aachen.105010_TMYx.epw'

        # with IFCBased.finder.disable():
            # self.playground.run_task(bps.SetIFCTypesBPS())
            # self.playground.run_task(common.LoadIFC())
            # self.playground.run_task(bps.Inspect())
            # self.playground.run_task(bps.Prepare())
        playground.run_task(bps.SetIFCTypes())
        playground.run_task(common.LoadIFC())
        playground.run_task(bps.Inspect())
        playground.run_task(bps.TZInspect())
        playground.run_task(bps.EnrichUseConditions())

        # playground.run_task(bps.OrientationGetter())

        playground.run_task(bps.MaterialVerification())  # LOD.full
        playground.run_task(bps.EnrichMaterial())  # LOD.full
        playground.run_task(bps.BuildingVerification())  # all LODs

        playground.run_task(bps.EnrichNonValid())  # LOD.full
        playground.run_task(bps.EnrichBuildingByTemplates())  # LOD.low

        playground.run_task(bps.Disaggregation_creation())
        playground.run_task(bps.BindThermalZones())
        # todo own task?
        copyfile(Path(__file__).parent.parent / 'data' / weather_file,
                 playground.state['paths'].root /'resources'/ weather_file)
        playground.run_task(bps.ExportEP())

        return
