from abc import ABCMeta, abstractmethod
import logging

class SimulationBase():
    'Base class for Simulation'
    __metaclass__ = ABCMeta

    def __init__(self):
        self.logger = logging.getLogger('bim2sim.plugin.' + self.__class__.__name__)
        return

    @abstractmethod
    def prepare(self, model):
        pass


    @abstractmethod
    def run(self):
        pass
