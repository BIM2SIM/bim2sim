"""Managing related"""
import os
import sys
import logging
from abc import ABCMeta, abstractmethod
import subprocess
import shutil
import configparser
from bim2sim.decorators import log
from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python.element import Element
from bim2sim.ifc2python import hvac
from bim2sim.ifc2python.hvac.hvac_graph import HvacGraph


class _Project():
    """Project related management"""

    CONFIG = "config.ini"
    DECISIONS = "decisions.json"
    IFC = "ifc"
    LOG = "log"
    EXPORT = "export"
    RESOURCES = "resources"

    def __init__(self):
        self._rootpath = None

    @property
    def root(self):
        """absolute rootpath"""
        if not self._rootpath:
            return None
        return os.path.abspath(self._rootpath)
    @root.setter
    def root(self, value):
        self._rootpath = value
        print("Rootpath set to '%s'"%(value))

    @property
    def config(self):
        """absolute path to config"""
        if not self._rootpath:
            return None
        return os.path.abspath(os.path.join(self._rootpath, _Project.CONFIG))

    @property
    def decisions(self):
        """absolute path to decisions"""
        return os.path.abspath(os.path.join(self._rootpath, _Project.DECISIONS))

    @property
    def log(self):
        """absolute path to log folder"""
        if not self._rootpath:
            return None
        return os.path.abspath(os.path.join(self._rootpath, _Project.LOG))
    @property
    def ifc(self):
        """absolute path to ifc folder"""
        if not self._rootpath:
            return None
        return os.path.abspath(os.path.join(self._rootpath, _Project.IFC))
    @property
    def resources(self):
        """absolute path to resources folder"""
        if not self._rootpath:
            return None
        return os.path.abspath(os.path.join(self._rootpath, _Project.RESOURCES))
    @property
    def export(self):
        """absolute path to export folder"""
        if not self._rootpath:
            return None
        return os.path.abspath(os.path.join(self._rootpath, _Project.EXPORT))

    @property
    def subdirs(self):
        """list of paths to sub folders"""
        return [self.log, self.ifc, self.resources, self.export]

    def is_project_folder(self, path=None):
        """Check if root path (or given path) is a project folder"""
        root = path or self.root
        if not root or not os.path.isdir(root):
            return False
        if os.path.isfile(os.path.join(root, _Project.CONFIG)):
            return True
        return False

    def complete_project_folder(self):
        """Adds missing sub folders to given path"""
        for subdir in self.subdirs:
            os.makedirs(subdir, exist_ok=True)

    def create_project_folder(self):
        """Creates a project folder on given path"""
        os.makedirs(self.root, exist_ok=True)

        for subdir in self.subdirs:
            os.makedirs(subdir, exist_ok=True)

        with open(self.config, "w"):
            pass

    def create(self, rootpath, ifc_path=None, target=None, open_conf=False):
        """Set root path, create project folder
        copy ifc, base config setup and open config if needed"""

        # set rootpath
        self.root = rootpath

        if self.is_project_folder():
            print("Given path is already a project folder ('%s')"%(self.root))
        else:
            self.create_project_folder()
            config_base_setup(target)

        if ifc_path:
            # copy ifc to project folder
            shutil.copy2(ifc_path, self.ifc)

        if open_conf:
            # open config for user interaction
            open_config()
        print("Project folder created.")

    def delete(self, confirm=True):
        """Delete project folder and all files in it

        :raises: AssertionError"""
        # TODO: decision system
        if confirm:
            ans = input("Delete project folder and all included files? [y/n]")
            if not ans == 'y':
                return

        if self.root:
            if os.path.exists(self.root):
                shutil.rmtree(self.root, ignore_errors=True)
                self.root = None
                print("Project folder deleted.")
            else:
                raise AssertionError("Can't delete project folder (reason: does not exist)")
        else:
            raise AssertionError("Can't delete project folder (reason: root not set)")

    def __repr__(self):
        return "<Project (root: %s)>"%(self._rootpath or "NOT SET!")

PROJECT = _Project()

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
        # todo add check if IFC has port information -> decision system
        #def _connect_instances(eps=1):
        #    nr_connections = 0
        #    for raw_instance1 in self.raw_instances.values():
        #        for port1 in raw_instance1.ports:
        #            for raw_instance2 in self.raw_instances.values():
        #                for port2 in raw_instance2.ports:
        #                    if raw_instance1 == raw_instance2:
        #                        continue
        #                    distance = list((abs(coord1 - coord2)
        #                                     for (coord1, coord2)
        #                                     in zip(port1.position,
        #                                            port2.position)))
        #                    if all(diff <= eps for diff in distance):
        #                        port1.connect(port2)
        #                        nr_connections += 1
        #    return nr_connections

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


def open_config():
    """Open config for user in default program"""
    if sys.platform.startswith('darwin'): # For MAC OS X
        subprocess.call(('open', PROJECT.config))
    elif os.name == 'nt': # For Windows
        os.startfile(PROJECT.config)
        #os.system("start " + conf_path)
    elif os.name == 'posix': # For Linux, Mac, etc.
        subprocess.call(('xdg-open', PROJECT.config))


def config_base_setup(backend=None):
    """Initial setup for config file"""
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(PROJECT.config)
    if not config.sections():
        config.add_section("Basics")
        config.add_section("Task")
        config.add_section("Backend")
        config["Backend"]["use"] = backend
        config.add_section("Modelica")
        config["Modelica"]["Version"] = "3.2.2"

    with open(PROJECT.config, "w") as file:
        config.write(file)


def get_config():
    """returns configparser instance. Basic config is done if file is not present"""
    config = configparser.ConfigParser(allow_no_value=True)
    if not config.read(PROJECT.config):
        config_base_setup(PROJECT.root)
        config.read(PROJECT.config)
    return config
