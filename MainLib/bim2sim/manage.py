"""Managing related"""

import logging
from abc import ABCMeta, abstractmethod

from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python.element import Element

def log(name):
    """Decorator for logging of entering and leaving method"""
    logger = logging.getLogger(__name__)
    def log_decorator(func):
        def wrapper(*args, **kwargs):
            logger.info("Started %s ...", name)
            func(*args, **kwargs)
            logger.info("Done %s.", name)
        return wrapper
    return log_decorator

class BIM2SIMManager():
    """Base class of overall bim2sim managing instance"""
    __metaclass__ = ABCMeta

    def __init__(self, task, ifc_path):
        self.logger = logging.getLogger(__name__)

        self.task = task
        self.ifc_path = ifc_path
        self.ifc = ifc2python.load_ifc(self.ifc_path)

        self.relevant_ifc_types = []
        self.raw_instances = {} # directly made from IFC
        self.reduced_instances = []
        self.instances = [] # processed for custom needs
        self.export_instances = []

        self.filters = []
        self.tests = []

        self.logger.info("BIM2SIMManager '%s' initialized", self.__class__.__name__)


    def run(self):
        """Run the manager"""
        self.prepare()
        self.inspect()
        self.enrich()
        self.reduce()
        self.process()
        self.check()
        self.export()

    @abstractmethod
    def prepare(self):
        """Step 1"""
        pass

    @log("inspecting IFC")
    def inspect(self):
        """Step 2"""

        for ifc_type in self.relevant_ifc_types:
            elements = self.ifc.by_type(ifc_type)
            for element in elements:
                representation = Element.factory(element)
                self.raw_instances[representation.guid] = representation

        self.logger.info("Found %d relevant elements", len(self.raw_instances))

    @log("enriching data")
    def enrich(self):
        """Step 3"""

        self.logger.warning("Not implemented!")

    @log("reducing data")
    def reduce(self):
        """Step 4"""

        self.logger.warning("Not implemented!")

    @log("processing")
    def process(self):
        """Step 5"""

        self.logger.warning("Not implemented!")

    @log("checking results")
    def check(self):
        """Step 6"""

        self.logger.warning("Not implemented!")

    @log("exporting")
    def export(self):
        """Step 7"""

        self.logger.warning("Not implemented!")

    def __repr__(self):
        return "<%s>"%(self.__class__.__name__)
