"""Managing related"""
import os
import sys
import logging
from abc import ABCMeta, abstractmethod
import subprocess
import shutil
import configparser
from bim2sim.decorators import log
from bim2sim.project import PROJECT, get_config
from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python.element import Element
from bim2sim.ifc2python import hvac
from bim2sim.ifc2python.hvac.hvac_graph import HvacGraph



class BIM2SIMManager():
    """Base class of overall bim2sim managing instance"""
    __metaclass__ = ABCMeta

    def __init__(self, task):
        self.logger = logging.getLogger(__name__)

        assert PROJECT.is_project_folder(), "PROJECT ist not set correctly!"

        if not os.path.samefile(PROJECT.root, os.getcwd()):
            self.logger.info("Changing working directory to '%s'", PROJECT.root)
            os.chdir(PROJECT.root)
        self.init_project()
        self.config = get_config()

        self.task = task
        self.ifc_path = self.get_ifc() # actual ifc # TODO: use multiple ifs files
        assert self.ifc_path, "No ifc found. Check '%s'"%(PROJECT.ifc)
        self.ifc = ifc2python.load_ifc(os.path.abspath(self.ifc_path))
        self.representations = []  # representations like graphs etc.
        self.relevant_ifc_types = []
        self.raw_instances = {}  # directly made from IFC
        self.reduced_instances = []
        self.instances = []  # processed for custom needs
        self.export_instances = []  # Todo @CWA whats the purpose?

        self.filters = []
        self.tests = []

        self.logger.info("BIM2SIMManager '%s' initialized", self.__class__.__name__)

    def init_project(self):
        """Check project folder and create it if necessary"""
        if not PROJECT.is_project_folder():
            self.logger.info("Creating project folder in '%s'", PROJECT.root)
            PROJECT.create_project_folder()
        else:
            PROJECT.complete_project_folder()

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
        self.logger.info("Connecting the relevant elements")
        nr_connections = hvac.connect_instances(self.raw_instances.values())
        self.logger.info("Found %d connections", nr_connections)

    @log("enriching data")
    def enrich(self):
        """Step 3"""
        hvacgraph = HvacGraph(self.raw_instances, self)
        hvacgraph.create_cycles()
        self.logger.warning("Not implemented!")

    @log("reducing data")
    def reduce(self):
        """Step 4"""

        self.logger.warning("Not implemented!")

    @log("processing")
    def process(self):
        """Step 5"""
        # HVACSystem(self)
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

    def get_ifc(self):
        """Returns first ifc from ifc folder"""
        lst = []
        for file in os.listdir(PROJECT.ifc):
            if file.lower().endswith(".ifc"):
                lst.append(file)

        if len(lst) == 1:
            return os.path.join(PROJECT.ifc, lst[0])
        if len(lst) > 1:
            self.logger.warning("Found multiple ifc files. Selected '%s'.", lst[0])
            return os.path.join(PROJECT.ifc, lst[0])

        self.logger.error("No ifc found in project folder.")
        return None

    def read_config(self):
        """Read config file"""
        self.config = get_config()

    def save_config(self):
        """Write config file"""
        with open(PROJECT.config, "w") as file:
            self.config.write(file)
