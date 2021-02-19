

from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.task import bps, base, common, hvac
from bim2sim.task.sub_tasks import tz_detection

class EnergyPlus(BIM2SIMManager):

    def __init__(self, workflow):
        super().__init__(workflow)

    def prepare(self, model):
        
        self.logger.info('preparing stuff')

        return

    def run(self):

        self.playground.run_task(bps.SetIFCTypesBPS())
        self.playground.run_task(common.LoadIFC())
        self.playground.run_task(bps.Inspect())
        self.playground.run_task(bps.Prepare())
        self.playground.run_task(bps.ExportEP())

        return
