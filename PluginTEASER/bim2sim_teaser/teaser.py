
from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.task import bps
from bim2sim.task import tz_detection

class TEASERManager(BIM2SIMManager):

    def __init__(self, task):
        super().__init__(task)

        self.relevant_ifc_types = bps.IFC_TYPES

    def run(self):
        # prepare = bps.Prepare()
        # prepare.run(bps.IFC_TYPES)
        #
        # inspect = bps.Inspect()
        # if not inspect.load(PROJECT.workflow):
        #     inspect.run(self.ifc, bps.IFC_TYPES)
        #     inspect.save(PROJECT.workflow)
        #
        ### Thermalzones
        recognition = tz_detection.Recognition()
        recognition.run(self.ifc_arch, inspect.instances)


        # libraries = (standardlibrary.StandardLibrary, HKESim)
        # export = bps.Export()
        # export.run(libraries, reduce.reduced_instances, reduce.connections)



