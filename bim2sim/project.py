"""Project handling"""
import logging
import os
import sys
import subprocess
import shutil
from distutils.dir_util import copy_tree
from pathlib import Path
from typing import Union
import configparser

from bim2sim.decision import Decision, ListDecision, DecisionBunch, save, load
from bim2sim.task.base import Playground
from bim2sim.plugins import load_plugin, Plugin

logger = logging.getLogger(__name__)


def open_config(path):
    """Open config for user in default program"""
    if sys.platform.startswith('darwin'):  # For MAC OS X
        subprocess.call(('open', path))
    elif os.name == 'nt':  # For Windows
        os.startfile(path)
        # os.system("start " + conf_path)
    elif os.name == 'posix':  # For Linux, Mac, etc.
        subprocess.call(('xdg-open', path))


def config_base_setup(path, backend=None):
    """Initial setup for config file"""
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(path)
    if not config.sections():
        config.add_section("Basics")
        config.add_section("Task")
        config.add_section("Aggregation")
        config.add_section("Backend")
        config["Backend"]["use"] = backend
        config.add_section("Frontend")
        config["Frontend"]["use"] = 'ConsoleFrontEnd'
        config.add_section("Modelica")
        config["Modelica"]["Version"] = "3.2.2"

    with open(path, "w") as file:
        config.write(file)


# def get_default_backends():
#     path = Path(__file__).parent / 'backends'
#     backends = []
#     for pkg in [item for item in path.glob('**/*') if item.is_dir()]:
#         if pkg.name.startswith('bim2sim_'):
#             backends.append(pkg)
#     return backends
#
#
# def get_dev_backends():
#     path = Path(__file__).parent.parent.parent
#     backends = []
#     for plugin in [item for item in path.glob('**/*') if item.is_dir()]:
#         if plugin.name.startswith('Plugin'):
#             for pkg in [item for item in plugin.glob('**/*') if item.is_dir()]:
#                 if pkg.name.startswith('bim2sim_'):
#                     backends.append(pkg)
#     return backends
#
#
# def get_plugins(by_entrypoint=False):
#     """load all possible plugins"""
#     logger = logging.getLogger(__name__)
#
#     default = get_default_backends()
#     dev = get_dev_backends()
#
#     # add all plugins to PATH
#     sys.path.extend([str(path.parent) for path in default + dev])
#
#     if by_entrypoint:
#         sim = {}
#         for entry_point in pkg_resources.iter_entry_points('bim2sim'):
#             sim[entry_point.name] = entry_point.load()
#     else:
#         sim = {}
#         for finder, name, ispkg in pkgutil.iter_modules():
#             if name.startswith('bim2sim_'):
#                 module = importlib.import_module(name)
#                 contend = getattr(module, 'CONTEND', None)
#                 if not contend:
#                     logger.warning("Found potential plugin '%s', but CONTEND is missing", name)
#                     continue
#
#                 for key, getter in contend.items():
#                     sim[key] = getter
#                     logger.debug("Found plugin '%s'", name)
#
#     return sim


class FolderStructure:
    """Project related file and folder handling."""

    CONFIG = "config.ini"
    DECISIONS = "decisions.json"
    WORKFLOW = "task"
    FINDER = "finder"
    IFC = "ifc"
    LOG = "log"
    EXPORT = "export"
    RESOURCES = "resources"

    _src_path = Path(__file__).parent  # base path to bim2sim assets

    def __init__(self, path=None):
        self._root_path = None
        self.root = path or os.getcwd()

    @property
    def root(self):
        """absolute root path"""
        return self._root_path

    @root.setter
    def root(self, value: str):
        self._root_path = Path(value).absolute().resolve()

    @property
    def assets(self):
        return self._src_path / 'assets'

    @property
    def enrichment(self):
        return self._src_path / 'enrichment_data'

    @property
    def config(self):
        """absolute path to config"""
        return self._root_path / self.CONFIG

    @property
    def decisions(self):
        """absolute path to decisions"""
        return self._root_path / self.DECISIONS

    @property
    def finder(self):
        """absolute path to decisions"""
        return self._root_path / self.FINDER

    @property
    def workflow(self):
        """absolute path to task"""
        return self._root_path / self.WORKFLOW

    @property
    def log(self):
        """absolute path to log folder"""
        return self._root_path / self.LOG

    @property
    def ifc(self):
        """absolute path to ifc folder"""
        return self._root_path / self.IFC

    @property
    def resources(self):
        """absolute path to resources folder"""
        return self._root_path / self.RESOURCES

    @property
    def export(self):
        """absolute path to export folder"""
        return self._root_path / self.EXPORT

    @property
    def b2sroot(self):
        """absolute path of bim2sim root folder"""
        return self._src_path.parent.parent

    @property
    def sub_dirs(self):
        """list of paths to sub folders"""
        return [self.log, self.ifc, self.resources, self.export, self.workflow,
                self.finder]

    def copy_assets(self, path):
        """copy assets to project folder"""
        copy_tree(str(self.assets), str(path))

    def is_project_folder(self, path=None):
        """Check if root path (or given path) is a project folder"""
        root = path or self.root
        if not root:
            return False
        root = Path(root)
        if not root.is_dir():
            return False
        if (root / self.CONFIG).is_file():
            return True
        return False

    def complete_project_folder(self):
        """Adds missing sub folders to given path"""
        for subdir in self.sub_dirs:
            os.makedirs(subdir, exist_ok=True)

    def create_project_folder(self):
        """Creates a project folder on given path"""
        os.makedirs(self.root, exist_ok=True)
        self.complete_project_folder()

        # create empty config file
        with open(self.config, "w"):
            pass

        self.copy_assets(self.root)

    @classmethod
    def create(cls, rootpath: str, ifc_path: str = None, target: str = None, open_conf=False):
        """Create ProjectFolder and set it up.

        Create instance, set source path, create project folder
        copy ifc, base config setup and open config if needed.

        Args:
            rootpath: path of root folder
            ifc_path: path to copy ifc file from
            target: the target simulation tool
            open_conf: flag to open the config file in default application
        """

        # set rootpath
        self = cls(rootpath)

        if self.is_project_folder():
            print("Given path is already a project folder ('%s')" % self.root)
        else:
            self.create_project_folder()
            config_base_setup(self.config, target)

        if ifc_path:
            # copy ifc to project folder
            shutil.copy2(ifc_path, self.ifc)

        if open_conf:
            # open config for user interaction
            open_config(self.config)
        print("Project folder created.")
        return self

    def delete(self, confirm=True):
        """Delete project folder and all files in it.

        Raises:
            AssertionError: if not existing on file system
        """
        # TODO: decision system
        if confirm:
            ans = input("Delete project folder and all included files? [y/n]")
            if not ans == 'y':
                return

        if os.path.exists(self.root):
            shutil.rmtree(self.root, ignore_errors=True)
            print("Project folder deleted.")
        else:
            raise AssertionError("Can't delete project folder (reason: does not exist)")

    def __str__(self):
        return str(self.root)

    def __repr__(self):
        return "<FolderStructure (root: %s)>" % self.root


class Project:
    """Project resource handling.

    Args:
        path: path to load project from
        plugin: Plugin to use. This overwrites plugin from config.
        workflow: Workflow to use with this project

    Raises:
        AssertionError: on invalid path. E.g. if not existing
    """
    formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    _active_project = None  # lock to prevent multiple interfering projects

    def __init__(self, path: str = None, plugin: Plugin = None, workflow=None):
        """Load existing project"""
        self.storage = {}  # project related items
        self.paths = FolderStructure(path)
        try:
            self.name = list(
                filter(Path.is_file, self.paths.ifc.glob('**/*')))[0].stem
        except:
            logger.warning(
                "Could not set correct project name, using Project!")
            self.name = "Project"

        if not self.paths.is_project_folder():
            raise AssertionError("Project path is no valid project directory. "
                                 "Use Project.create() to create a new Project")
        self._made_decisions = DecisionBunch()
        self.loaded_decisions = load(self.paths.decisions)

        # TODO: Plugins provide Tasks and Elements. there are 'builtin' Plugins
        #  which should be loaded anyway. In config additional Plugins can be specified.
        #  'external' Plugins ca specify a meaningful workflow, builtins cant. How to get a generic workflow?
        self.default_plugin = self._get_plugin(plugin)
        if not workflow:
            workflow = self.default_plugin.default_workflow()
        workflow.relevant_elements = self.default_plugin.elements
        workflow.update_from_config(self.config)
        self.playground = Playground(workflow, self.paths, self.name)

        self._log_handler = self._setup_logger()  # setup project specific handlers

    def _get_plugin(self, plugin):
        if plugin:
            return plugin
        else:
            plugin_name = self.config['Backend']['use']
            assert plugin_name, "Either an explicit passed plugin or equivalent entry in config is required."
            return load_plugin(plugin_name)

    @classmethod
    def create(cls, project_folder, ifc_path=None, plugin: Union[str, Plugin] = None,
               open_conf=False, workflow=None):
        """Create new project

        Args:
            project_folder: directory of project
            ifc_path: path to in ifc which gets copied into project folder
            plugin: Plugin to use with this project.
                If passed as string, make sure it is importable (see plugins.load_plugin)
            open_conf: open config file in default editor to manually edit it
            workflow: Workflow to use with this project
        """
        # create folder first
        if isinstance(plugin, str):
            FolderStructure.create(project_folder, ifc_path, plugin, open_conf)
            project = cls(project_folder, workflow=workflow)
        else:
            # an explicit plugin can't be recreated from config. Thou we don't save it
            FolderStructure.create(project_folder, ifc_path, open_conf=open_conf)
            project = cls(project_folder, plugin=plugin, workflow=workflow)

        return project

    @staticmethod
    def is_project_folder(path: str) -> bool:
        return FolderStructure(path).is_project_folder()

    @classmethod
    def _release(cls, project):
        if cls._active_project is project:
            cls._active_project = None
        elif cls._active_project is None:
            raise AssertionError("Cant release Project. No active project.")
        else:
            raise AssertionError("Cant release from other project.")

    def is_active(self) -> bool:
        """Return True if current project is active, False otherwise."""
        return Project._active_project is self

    def _setup_logger(self):
        file_handler = logging.FileHandler(os.path.join(self.paths.log, "bim2sim.log"))
        file_handler.setFormatter(self.formatter)
        logger.addHandler(file_handler)
        return file_handler

    def _teardown_logger(self):
        logger.removeHandler(self._log_handler)
        self._log_handler.close()

    @property
    def config(self):
        """returns configparser instance. Basic config is done if file is not present"""
        config = configparser.ConfigParser(allow_no_value=True)
        if not config.read(self.paths.config):
            self.config_base_setup(self.paths.root)
            config.read(self.paths.config)
        return config

    def run(self, interactive=False, cleanup=True):
        """Run project.

        Args:
            interactive: if True the Task execution order is determined by Decisions else its derived by plugin
            cleanup: execute cleanup logic. Not doing this is only relevant for debugging

        Raises:
            AssertionError: if project setup is broken or on invalid Decisions
        """
        if not self.paths.is_project_folder():
            raise AssertionError("Project ist not set correctly!")

        success = False
        if interactive:
            run = self._run_interactive
        else:
            run = self._run_default
        try:
            for decision_bunch in run():
                yield decision_bunch
                if not decision_bunch.valid():
                    raise AssertionError("Cant continue with invalid decisions")
                for decision in decision_bunch:
                    decision.freeze()
                self._made_decisions.extend(decision_bunch)
                self._made_decisions.validate_global_keys()
            success = True
        except Exception as ex:
            logger.exception("Something went wrong!")
        finally:
            if cleanup:
                self.finalize(success=success)
        return 0 if success else -1

    def _run_default(self, plugin=None):
        """Execution of plugins default run"""
        # run plugin default
        plugin_cls = plugin or self.default_plugin
        _plugin = plugin_cls()
        for task_cls in _plugin.default_tasks:
            yield from self.playground.run_task(task_cls())

    def _run_interactive(self):
        """Interactive execution of available ITasks"""
        while True:
            tasks_classes = {task.__name__: task for task in self.playground.available_tasks()}
            choices = [(name, task.__doc__) for name, task in tasks_classes.items()]
            task_decision = ListDecision("What shall we do?", choices=choices)
            yield DecisionBunch([task_decision])
            task_name = task_decision.value
            task_class = tasks_classes[task_name]
            yield from self.playground.run_task(task_class())
            if task_class.final:
                break

    def finalize(self, success=False):
        """cleanup method"""

        if self.is_active():
            # clean up run relics
            #  backup decisions
            if not success:
                pth = self.paths.root / 'decisions_backup.json'
                save(self._made_decisions, pth)
                logger.warning("Decisions are saved in '%s'. Rename file to 'decisions.json' to reuse them.", pth)
            else:
                save(self._made_decisions, self.paths.decisions)

        # clean up init relics
        #  clean logger
        logger.info('finished')
        self._teardown_logger()

    def delete(self):
        """Delete the project."""
        self.finalize(True)  # success True to prevent unnecessary decision saving
        self.paths.delete(False)
        logger.info("Project deleted")

    def __repr__(self):
        return "<Project(%s)>" % self.paths.root
