

import bim2sim
from bim2sim.plugin import Plugin


class EnergyPlus(Plugin):
    name = 'EnergyPlus'

    def prepare(self, model):
        
        self.logger.info('preparing stuff')

        return

    def run(self):

        self.logger.info('doing stuff')

        return
