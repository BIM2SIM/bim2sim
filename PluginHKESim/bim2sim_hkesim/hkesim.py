
import bim2sim
from bim2sim.ifc2python.hvac import hvacsystem

class HKESim(bim2sim.SimulationBase):

    def __init__(self):
        super().__init__(__name__)
        
        self.hvac = None
        return

    def prepare(self, model):
        
        self.logger.info('preparing stuff')

        self.hvac = hvacsystem.HVACSystem(model)

        return

    def run(self):

        self.logger.info('doing export stuff')

        #self.hvac.draw_hvac_network()
        return

