
import bim2sim

from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.tasks import LOD, PlantSimulation
from bim2sim.workflow import hvac

from bim2sim_hkesim import models

class HKESimManager(BIM2SIMManager):

    def __init__(self, task):
        super().__init__(task)

        self.relevant_ifc_types = hvac.IFC_TYPES

    def run(self):

        prepare = hvac.Prepare()
        prepare.run(hvac.IFC_TYPES)

        inspect = hvac.Inspect()
        inspect.run(self.ifc, hvac.IFC_TYPES)

        detectcycles = hvac.DetectCycles()
        detectcycles.run(list(inspect.instances.values()))

        reduce = hvac.Reduce()
        reduce.run(detectcycles.graph)

        #check

        #TODO reduced_instances hold only aggregations, not aggregated are missing
        export = hvac.Export()
        export.run(reduce.reduced_instances)

