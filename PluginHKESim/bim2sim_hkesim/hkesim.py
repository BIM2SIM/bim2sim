
from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.task import hvac, base
from bim2sim.export.modelica import standardlibrary
from bim2sim_hkesim.models import HKESim


class LoadLibrariesHKESim(base.ITask):

    touches = ('libraries', )

    def run(self, workflow, **kwargs):
        return (standardlibrary.StandardLibrary, HKESim),


class HKESimManager(BIM2SIMManager):

    def __init__(self, workflow):
        super().__init__(workflow)

        self.relevant_ifc_types = hvac.IFC_TYPES

    def run(self):

        playground = base.Playground(self.workflow)

        playground.run_task(hvac.SetIFCTypesHVAC())
        playground.run_task(base.LoadIFC(PROJECT.ifc))

        playground.run_task(hvac.Prepare())

        playground.run_task(hvac.Inspect())

        playground.run_task(hvac.MakeGraph())

        playground.run_task(hvac.Reduce())

        playground.run_task((LoadLibrariesHKESim()))

        playground.run_task(hvac.Export())



        # prepare = hvac.Prepare()
        # prepare.run(self.workflow, hvac.IFC_TYPES)
        #
        # inspect = hvac.Inspect()
        # if not inspect.load(PROJECT.workflow):
        #     inspect.run(self.workflow, self.ifc, prepare)
        #     inspect.save(PROJECT.workflow)
        #
        # makegraph = hvac.MakeGraph()
        # if not makegraph.load(PROJECT.workflow):
        #     makegraph.run(self.workflow, list(inspect.instances.values()))
        #     makegraph.save(PROJECT.workflow)
        #
        # reduce = hvac.Reduce()
        # reduce.run(self.workflow, makegraph.graph)
        #
        # #check
        #
        # libraries = (standardlibrary.StandardLibrary, HKESim)
        # export = hvac.Export()
        # export.run(self.workflow, libraries, reduce.reduced_instances, reduce.connections)



