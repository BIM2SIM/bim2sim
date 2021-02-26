
from bim2sim.manage import BIM2SIMManager
from bim2sim.task import base
from bim2sim.task import common
from bim2sim.task import hvac
from bim2sim.task.hvac import dead_ends
from bim2sim.export.modelica import standardlibrary
from bim2sim_hkesim.models import HKESim


class LoadLibrariesHKESim(base.ITask):
    """Load HKESim library for export"""
    touches = ('libraries', )

    def run(self, workflow, **kwargs):
        return (standardlibrary.StandardLibrary, HKESim),


class HKESimManager(BIM2SIMManager):

    def run(self):

        self.playground.run_task(hvac.SetIFCTypesHVAC())
        self.playground.run_task(common.LoadIFC())
        self.playground.run_task(hvac.Prepare())
        self.playground.run_task(hvac.Inspect())
        self.playground.run_task(hvac.MakeGraph())
        self.playground.run_task(hvac.Reduce())
        self.playground.run_task(dead_ends.DeadEnds())
        self.playground.run_task(LoadLibrariesHKESim())
        self.playground.run_task(hvac.Export())
