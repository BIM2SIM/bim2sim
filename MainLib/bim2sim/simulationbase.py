from abc import ABCMeta, abstractmethod
import logging

class SimulationBase():
    """Base class for Simulation"""
    __metaclass__ = ABCMeta

    def __init__(self, name):
        self.name = name
        self.logger = logging.getLogger('bim2sim.plugin.' + self.name)
        self.logger.info("Initializing backend for %s", self.name)
        return

    @abstractmethod
    def prepare(self, model):
        pass


    @abstractmethod
    def run(self):
        pass
