from bim2sim.manage import BIM2SIMManager
from bim2sim.task import common

from bim2sim.task import bps

from bim2sim.task.bps import Inspect

from bim2sim.task.bps import bps as bps2
# from bim2sim.task.common import common



# class LoadLibrariesTEASER(base.ITask):
#     """Load TEASER library for export"""
#     touches = ('libraries', )
#
#     def run(self, workflow, **kwargs):
#         return (standardlibrary.StandardLibrary, HKESim),


class TEASERManager(BIM2SIMManager):

    def __init__(self, workflow):
        super().__init__(workflow)

    def run(self):

        self.playground.run_task(bps.SetIFCTypes())
        self.playground.run_task(common.LoadIFC())
        self.playground.run_task(Inspect.Inspect())

        print()
        # self.playground.run_task(bps.SetIFCTypesBPS())
        # self.playground.run_task(common.LoadIFC())
        # self.playground.run_task(bps.Inspect())
        #
        # self.playground.run_task(bps.Prepare())
        # pass
        #
        # self.playground.run_task(bps.ExportTEASER())





