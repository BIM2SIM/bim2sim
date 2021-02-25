from bim2sim.manage import BIM2SIMManager
from bim2sim.task import bps
from bim2sim.task import common




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

        self.playground.run_task(bps.SetIFCTypesBPS())
        self.playground.run_task(common.LoadIFC())
        self.playground.run_task(bps.Inspect())
        pass

        self.playground.run_task(bps.ExportTEASER())





