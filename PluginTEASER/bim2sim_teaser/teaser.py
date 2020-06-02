
from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.task import bps
from bim2sim.export.modelica import standardlibrary
from bim2sim_hkesim.models import HKESim


class HKESimManager(BIM2SIMManager):

    def __init__(self, workflow):
        super().__init__(workflow)

        self.relevant_ifc_types = bps.IFC_TYPES

    def run(self):
        prepare = bps.Prepare()
        prepare.run(bps.IFC_TYPES)

        inspect = bps.Inspect()
        if not inspect.load(PROJECT.workflow):
            inspect.run(self.ifc, bps.IFC_TYPES)
            inspect.save(PROJECT.workflow)

        #check

        libraries = (standardlibrary.StandardLibrary, HKESim)
        export = bps.Export()
        export.run(libraries, reduce.reduced_instances, reduce.connections)



