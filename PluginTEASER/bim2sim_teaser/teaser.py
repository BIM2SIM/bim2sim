
from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.task import bps, base, common, hvac
from bim2sim.task.sub_tasks import tz_detection

# from bim2sim.export.modelica import standardlibrary
# from bim2sim_hkesim.models import HKESim
#
#
# class LoadLibrariesHKESim(base.ITask):
#     """Load HKESim library for export"""
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

        self.playground.run_task(bps.ExportTEASER())
        print()
        #self.playground.run_task(bps.ExportTEASERMultizone())

        # export = bps.ExportTEASERMultizone()
        # # export = bps.ExportTEASERSingleZone()
        # export.run(self.playground.workflow, self.playground.history[2])
        # print()


        # libraries = (standardlibrary.StandardLibrary, HKESim)
        # export = bps.Export()
        # export.run(libraries, reduce.reduced_instances, reduce.connections)



