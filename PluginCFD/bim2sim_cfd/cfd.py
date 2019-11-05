from bim2sim.manage import BIM2SIMManager
from bim2sim.project import PROJECT
from bim2sim.workflow.cfd import Facade



class CFDManager(BIM2SIMManager):

    def __init__(self, task):
        super().__init__(task)

        self.facade = Facade()

    def run(self):
        print("CFD started")
        path = PROJECT.ifc # path to ifc file
        self.facade.run(path)



