"""Managing related"""
import os
import logging
from abc import ABCMeta, abstractmethod

from bim2sim.project import PROJECT, get_config
from bim2sim.kernel import ifc2python
from bim2sim.decision import Decision
from bim2sim.enrichment_data.data_class import DataClass
from bim2sim.export.modelica import standardlibrary
import ifcopenshell


class BIM2SIMManager:
    """Base class of overall bim2sim managing instance"""
    __metaclass__ = ABCMeta

    def __init__(self, task):
        self.logger = logging.getLogger(__name__)

        assert PROJECT.is_project_folder(), "PROJECT ist not set correctly!"

        if not os.path.samefile(PROJECT.root, os.getcwd()):
            self.logger.info("Changing working directory to '%s'", PROJECT.root)
            os.chdir(PROJECT.root)
        # self.init_project()
        self.config = get_config()

        self.task = task
        self.ifc_path = self.get_ifc() # actual ifc # TODO: use multiple ifs files
        assert self.ifc_path, "No ifc found. Check '%s'"%(PROJECT.ifc)
        self.ifc = ifc2python.load_ifc(os.path.abspath(self.ifc_path))
        self.logger.info("The exporter version of the IFC file is '%s'",
                         self.ifc.wrapped_data.header.file_name.originating_system)

        Decision.load(PROJECT.decisions)

        self.logger.info("BIM2SIMManager '%s' initialized", self.__class__.__name__)

    def init_project(self):
        """Check project folder and create it if necessary"""
        if not PROJECT.is_project_folder():
            self.logger.info("Creating project folder in '%s'", PROJECT.root)
            PROJECT.create_project_folder()
        else:
            PROJECT.complete_project_folder()



    @abstractmethod
    def run(self):
        """Run the manager"""

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
