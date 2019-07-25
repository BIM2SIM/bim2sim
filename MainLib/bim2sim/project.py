"""Project handling"""

import os
import sys
import subprocess
import shutil
from distutils.dir_util import copy_tree
import configparser


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


class _Project():
    """Project related management"""

    CONFIG = "config.ini"
    DECISIONS = "decisions.json"
    WORKFLOW = "workflow"
    FINDER = "finder"
    IFC = "ifc"
    LOG = "log"
    EXPORT = "export"
    RESOURCES = "resources"

    def __init__(self):
        self._rootpath = None
        self._src_path = os.path.join(os.path.dirname(__file__))

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
    def source(self):
        if not self._src_path:
            return None
        return os.path.abspath(self._src_path)

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
    def finder(self):
        """absolute path to decisions"""
        return os.path.abspath(os.path.join(self._rootpath, _Project.FINDER))

    @property
    def workflow(self):
        """absolute path to workflow"""
        if not self._rootpath:
            return None
        return os.path.abspath(os.path.join(self._rootpath, _Project.WORKFLOW))

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
        return [self.log, self.ifc, self.resources, self.export, self.workflow,
                self.finder]

    @staticmethod
    def copy_assets(path):
        """copy assets to project folder"""
        assets_path = os.path.join(os.path.dirname(__file__), 'assets')

        copy_tree(assets_path, path)

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

        self.copy_assets(self.root)

    def create(self, rootpath, ifc_path=None, target=None, \
                                                          open_conf=False):
        """Set root path, source path, create project folder
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
