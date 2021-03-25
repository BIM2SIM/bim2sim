from shutil import copyfile
from pathlib import Path

from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.task import bps
from bim2sim.task import common
from bim2sim.kernel.element import IFCBased


class EnergyPlus(BIM2SIMManager):

    def __init__(self, workflow):
        super().__init__(workflow)

    def prepare(self, model):
        
        self.logger.info('preparing stuff')

        return

    def run(self):
        weather_file = 'DEU_NW_Aachen.105010_TMYx.epw'

        with IFCBased.finder.disable():
            # self.playground.run_task(bps.SetIFCTypesBPS())
            # self.playground.run_task(common.LoadIFC())
            # self.playground.run_task(bps.Inspect())
            # self.playground.run_task(bps.Prepare())
            self.playground.run_task(bps.SetIFCTypes())
            self.playground.run_task(common.LoadIFC())
            self.playground.run_task(bps.Inspect())
            self.playground.run_task(bps.TZInspect())
            self.playground.run_task(bps.OrientationGetter())

            self.playground.run_task(bps.MaterialVerification())  # LOD.full
            self.playground.run_task(bps.EnrichMaterial())  # LOD.full
            self.playground.run_task(bps.BuildingVerification())  # all LODs

            self.playground.run_task(bps.EnrichNonValid())  # LOD.full
            self.playground.run_task(bps.EnrichBuildingByTemplates())  # LOD.low

            self.playground.run_task(bps.Disaggregation_creation())
            self.playground.run_task(bps.BindThermalZones())
            copyfile(Path(__file__).parent.parent / 'data' / weather_file, PROJECT.root /'resources'/ weather_file) # todo
            self.playground.run_task(bps.ExportEP())

        return
