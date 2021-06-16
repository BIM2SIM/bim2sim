from shutil import copyfile
from pathlib import Path

from bim2sim.task import bps
from bim2sim.task import common
from bim2sim.plugin import Plugin
from bim2sim.workflow import BPSMultiZoneSeparatedEP
from bim2sim.kernel.elements import bps as bps_elements


class EnergyPlus(Plugin):
    name = 'EnergyPlus'
    default_workflow = BPSMultiZoneSeparatedEP
    elements = {*bps_elements.items}

    def run(self, playground):
        weather_file = 'DEU_NW_Aachen.105010_TMYx.epw'

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

        # todo own task?
        copyfile(Path(__file__).parent.parent / 'data' / weather_file,
                 playground.paths.resources / weather_file)
        # playground.run_task(bps.ExportEP())

        return
