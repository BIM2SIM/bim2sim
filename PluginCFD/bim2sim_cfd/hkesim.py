
from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.workflow import hvac
from bim2sim.export.modelica import standardlibrary
from bim2sim_hkesim.models import HKESim


class CFDManager(CFDManager):

    def __init__(self, task):
        super().__init__(task)

        self.relevant_ifc_types = cfd.IFC_TYPES

    def run(self):
        print("CFD started")



