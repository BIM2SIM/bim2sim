
from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.task import hvac
from bim2sim.export.modelica import standardlibrary
from bim2sim_hkesim.models import HKESim


class HKESimManager(BIM2SIMManager):

    def __init__(self, task):
        super().__init__(task)

        self.relevant_ifc_types = hvac.IFC_TYPES

    def run(self):
        prepare = hvac.Prepare()
        prepare.run(self.task, hvac.IFC_TYPES)

        inspect = hvac.Inspect()
        if not inspect.load(PROJECT.workflow):
            inspect.run(self.task, self.ifc, hvac.IFC_TYPES)
            inspect.save(PROJECT.workflow)

        makegraph = hvac.MakeGraph()
        if not makegraph.load(PROJECT.workflow):
            makegraph.run(self.task, list(inspect.instances.values()))
            makegraph.save(PROJECT.workflow)

        reduce = hvac.Reduce()
        reduce.run(self.task, makegraph.graph)

        #check

        libraries = (standardlibrary.StandardLibrary, HKESim)
        export = hvac.Export()
        export.run(self.task, libraries, reduce.reduced_instances, reduce.connections)



