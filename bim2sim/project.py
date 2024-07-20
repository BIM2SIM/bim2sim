"""Project handling"""
import logging
import os
import sys
import subprocess
import shutil
import threading
from distutils.dir_util import copy_tree
from enum import Enum
from pathlib import Path
from typing import Dict, List, Type, Union

import configparser

from bim2sim.kernel.decision import ListDecision, DecisionBunch, save, load
from bim2sim.kernel import log
from bim2sim.tasks.base import Playground
from bim2sim.plugins import Plugin, load_plugin
from bim2sim.utilities.common_functions import all_subclasses
from bim2sim.sim_settings import BaseSimSettings
from bim2sim.utilities.types import LOD

logger = logging.getLogger(__name__)
user_logger = log.get_user_logger(__name__)


def open_config(path):
    """Open config for user and wait for closing before continue."""
    if sys.platform.startswith('darwin'):  # For MAC OS X
        open_file = subprocess.Popen(['open', path])
    elif os.name == 'nt':  # For Windows
        open_file = subprocess.Popen(["notepad.exe", path])
        # os.system("start " + conf_path)
    # todo for any reason wait() seems not to work on linux
    # elif os.name == 'posix':  # For Linux, Mac, etc.
    # open_file = subprocess.Popen(['xdg-open', path])
    else:
        raise NotImplementedError('Only mac os and windows are '
                                  'supported currently.')
    open_file.wait()


def add_config_section(
        config: configparser.ConfigParser,
        sim_settings: BaseSimSettings,
        name: str) -> configparser.ConfigParser:
    """Add a section to config with all attributes and default values."""
    if name not in config._sections:
        config.add_section(name)
    attributes = [attr for attr in list(sim_settings.__dict__.keys())
                  if not callable(getattr(sim_settings, attr)) and not
                  attr.startswith('__')]
    for attr in attributes:
        default_value = getattr(sim_settings, attr).default
        if isinstance(default_value, Enum):
            default_value = str(default_value)
        if not attr in config[name]:
            config[name][attr] = str(default_value)
    return config


def config_base_setup(path, backend=None):
    """Initial setup for config file"""
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(path)

    if not config.sections():
        # add all default attributes from base workflow
        config = add_config_section(config, BaseSimSettings, "Generic Simulation "
                                                     "Settings")
        # add all default attributes from sub workflows
        all_settings = all_subclasses(BaseSimSettings)
        for flow in all_settings:
            config = add_config_section(config, flow, flow.__name__)

        # add general settings
        config.add_section("Backend")
        config["Backend"]["use"] = backend
        config.add_section("Frontend")
        config["Frontend"]["use"] = 'ConsoleFrontEnd'
        config.add_section("Modelica")
        config["Modelica"]["Version"] = "4.0"

    with open(path, "w") as file:
        config.write(file)


class FolderStructure:
    """Project related file and folder handling."""

    CONFIG = "config.toml"
    DECISIONS = "decisions.json"
    FINDER = "finder"
    IFC_BASE = "ifc"
    LOG = "log"
    EXPORT = "export"

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
        """absolute path to finder"""
        return self._root_path / self.FINDER

    @property
    def log(self):
        """absolute path to log folder"""
        return self._root_path / self.LOG

    @property
    def ifc_base(self):
        """absolute path to ifc folder"""
        return self._root_path / self.IFC_BASE

    @property
    def export(self):
        """absolute path to export folder"""
        return self._root_path / self.EXPORT

    @property
    def b2sroot(self):
        """absolute path of bim2sim root folder"""
        return self._src_path.parent

    @property
    def sub_dirs(self):
        """list of paths to sub folders"""
        return [self.log, self.ifc_base, self.export, self.finder]

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
    def create(cls, rootpath: str, ifc_paths: Dict = None,
               target: str = None, open_conf: bool = False):
        """Create ProjectFolder and set it up.

        Create instance, set source path, create project folder
        copy ifc, base config setup and open config if needed.

        Args:
            rootpath: path of root folder
            ifc_paths: dict with key: bim2sim domain and value: path
                to corresponding ifc which gets copied into project folder
            target: the target simulation tool
            open_conf: flag to open the config file in default application
        """

        # set rootpath
        self = cls(rootpath)

        if self.is_project_folder():
            logger.info(
                "Given path is already a project folder ('%s')" % self.root)
        else:
            self.create_project_folder()
            config_base_setup(self.config, target)

        if ifc_paths:
            if not isinstance(ifc_paths, Dict):
                raise ValueError(
                    "Please provide a Dictionary with key: Domain, value: Path "
                    "to IFC ")
            # copy all ifc files to domain specific project folders
            for domain, file_path in ifc_paths.items():
                if not file_path.exists():
                    if "test" in file_path.parts \
                            and "resources" in file_path.parts:
                        raise ValueError(
                            f"Provided path to ifc is: {file_path}, but this "
                            f"file does not exist. You are trying to run a test on your local machine,"
                            f" but it seems like you have not downloaded the"
                            f" needed test resources. Run dl_test_resources.py "
                            f"in test folder first."
                        )
                    else:
                        raise ValueError(
                            f"Provided path to ifc is: {file_path}, but this file "
                            f"does not exist.")
                Path.mkdir(self.ifc_base / domain.name, exist_ok=True)
                shutil.copy2(
                    file_path, self.ifc_base / domain.name / file_path.name)

        if open_conf:
            # open config for user interaction
            open_config(self.config)
        logger.info("Project folder created.")
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
            raise AssertionError(
                "Can't delete project folder (reason: does not exist)")

    def __str__(self):
        return str(self.root)

    def __repr__(self):
        return "<FolderStructure (root: %s)>" % self.root


class Project:
    """Project resource handling.

    Args:
        path: path to load project from
        plugin: Plugin to use. This overwrites plugin from config.

    Raises:
        AssertionError: on invalid path. E.g. if not existing
    """
    formatter = log.CustomFormatter('[%(levelname)s] %(name)s: %(message)s')
    _active_project = None  # lock to prevent multiple interfering projects

    def __init__(
            self,
            path: str = None,
            plugin: Type[Plugin] = None,
    ):
        """Load existing project"""
        self.paths = FolderStructure(path)
        # try to get name of project from ifc name
        try:
            self.name = list(
                filter(Path.is_file, self.paths.ifc_base.glob('**/*')))[0].stem
        except:
            logger.warning(
                'Could not set correct project name, using "Project"!')
            self.name = "Project"

        if not self.paths.is_project_folder():
            raise AssertionError("Project path is no valid project directory. "
                                 "Use Project.create() to create a new Project")
        self._made_decisions = DecisionBunch()
        self.loaded_decisions = load(self.paths.decisions)

        self.plugin_cls = self._get_plugin(plugin)
        self.playground = Playground(self)
        # link sim_settings to project to make set of settings easier
        self.sim_settings = self.playground.sim_settings

        self._user_logger_set = False
        self._log_thread_filters: List[log.ThreadLogFilter] = []
        self._log_handlers = {}
        self._setup_logger()  # setup project specific handlers

    def _get_plugin(self, plugin):
        if plugin:
            return plugin
        else:
            plugin_name = self.config['Backend']['use']
            assert plugin_name, "Either an explicit passed plugin or" \
                                " equivalent entry in config is required."
            return load_plugin(plugin_name)

    @classmethod
    def create(cls, project_folder, ifc_paths: Dict = None, plugin: Union[
        str, Type[Plugin]] = None, open_conf: bool = False):
        """Create new project

        Args:
            project_folder: directory of project
            ifc_paths: dict with key: IFCDomain and value: path
                to corresponding ifc which gets copied into project folder
            plugin: Plugin to use with this project. If passed as string,
             make sure it is importable (see plugins.load_plugin)
            open_conf: flag to open the config file in default application
            updated from config
        """
        # create folder first
        if isinstance(plugin, str):
            FolderStructure.create(project_folder, ifc_paths, plugin, open_conf)
            project = cls(project_folder)
        else:
            # an explicit plugin can't be recreated from config.
            # Thou we don't save it
            FolderStructure.create(
                project_folder, ifc_paths, open_conf=open_conf)
            project = cls(project_folder, plugin=plugin)

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
        # we assume only one project per thread and time is active.
        # Thou we can use the thread name to filter project specific log
        # messages.
        # BUT! this assumption is not enforced and multiple active projects
        # per thread will result in a mess of log messages.

        # tear down existing handlers (just in case)
        self._teardown_logger()

        thread_name = threading.current_thread().name

        # quality logger
        quality_logger = logging.getLogger('bim2sim.QualityReport')
        quality_handler = logging.FileHandler(
            os.path.join(self.paths.log, "IFCQualityReport.log"))
        quality_handler.addFilter(log.ThreadLogFilter(thread_name))
        quality_handler.setFormatter(log.quality_formatter)
        quality_logger.addHandler(quality_handler)

        general_logger = logging.getLogger('bim2sim')

        # dev logger
        dev_handler = logging.StreamHandler()
        dev_thread_filter = log.ThreadLogFilter(thread_name)
        dev_handler.addFilter(dev_thread_filter)
        dev_handler.addFilter(log.AudienceFilter(None))
        dev_handler.setFormatter(log.dev_formatter)
        general_logger.addHandler(dev_handler)

        self._log_handlers['bim2sim.QualityReport'] = [quality_handler]
        self._log_handlers['bim2sim'] = [dev_handler]
        self._log_thread_filters.append(dev_thread_filter)

    def _update_logging_thread_filters(self):
        """Update thread filters to current thread."""
        thread_name = threading.current_thread().name
        for thread_filter in self._log_thread_filters:
            thread_filter.thread_name = thread_name

    def set_user_logging_handler(self, user_handler: logging.Handler,
                                 set_formatter=True):
        """Set a project specific logging Handler for user loggers.

        Args:
            user_handler: the handler instance to use for this project
            set_formatter: if True, the user_handlers formatter is set
        """
        general_logger = logging.getLogger('bim2sim')
        thread_name = threading.current_thread().name

        if self._user_logger_set:
            self._setup_logger()
        user_thread_filter = log.ThreadLogFilter(thread_name)
        user_handler.addFilter(user_thread_filter)
        user_handler.addFilter(log.AudienceFilter(log.USER))
        if set_formatter:
            user_handler.setFormatter(log.user_formatter)
        general_logger.addHandler(user_handler)

        self._user_logger_set = True

        self._log_handlers.setdefault('bim2sim', []).append(user_handler)
        self._log_thread_filters.append(user_thread_filter)

    def _teardown_logger(self):
        for name, handlers in self._log_handlers.items():
            _logger = logging.getLogger(name)
            for handler in handlers:
                _logger.removeHandler(handler)
                handler.close()
        self._log_thread_filters.clear()

    @property
    def config(self):
        """returns configparser instance. Basic config is done if file is not
        present"""
        config = configparser.ConfigParser(allow_no_value=True)
        if not config.read(self.paths.config):
            config_base_setup(self.paths.root)
            config.read(self.paths.config)
        return config

    def rewrite_config(self):
        # TODO this might need changes due to handling of enums
        config = self.config
        settings_manager = self.sim_settings.manager
        for setting in settings_manager:
            s = settings_manager.get(setting)
            if isinstance(s.value, LOD):
                val = s.value.value
            else:
                val = s.value
            config[type(self.sim_settings).__name__][s.name] = str(val)

        with open(self.paths.config, "w") as file:
            config.write(file)

    def run(self, interactive=False, cleanup=True):
        """Run project.

        Args:
            interactive: if True the Task execution order is determined by
                Decisions else its derived by plugin
            cleanup: execute cleanup logic. Not doing this is only relevant for
                debugging

        Raises:
            AssertionError: if project setup is broken or on invalid Decisions
        """
        if not self.paths.is_project_folder():
            raise AssertionError("Project ist not set correctly!")

        if not self._user_logger_set:
            logger.info("Set user logger to default Stream. "
                        "Call project.set_user_logging_handler(your_handler) "
                        "with your own handler prior to "
                        "project.run() to change this.")
            self.set_user_logging_handler(logging.StreamHandler())
        self.sim_settings.check_mandatory()
        success = False
        if interactive:
            run = self._run_interactive
        else:
            run = self._run_default
        try:
            # First update log filters in case Project was created from
            # different tread.
            # Then update log filters for each iteration, which might get called
            # by a different thread.
            # Deeper down multithreading is currently not supported for logging
            # and will result in a mess of log messages.
            self._update_logging_thread_filters()
            for decision_bunch in run():
                yield decision_bunch
                self._update_logging_thread_filters()
                if not decision_bunch.valid():
                    raise AssertionError("Cant continue with invalid decisions")
                for decision in decision_bunch:
                    decision.freeze()
                self._made_decisions.extend(decision_bunch)
                self._made_decisions.validate_global_keys()
            success = True
        except Exception as ex:
            logger.exception(f"Something went wrong!: {ex}")
        finally:
            if cleanup:
                self.finalize(success=success)
        return 0 if success else -1

    def _run_default(self, plugin=None):
        """Execution of plugins default tasks"""
        # run plugin default
        plugin_cls = plugin or self.plugin_cls
        _plugin = plugin_cls()
        for task_cls in _plugin.default_tasks:
            yield from self.playground.run_task(task_cls(self.playground))

    def _run_interactive(self):
        """Interactive execution of available ITasks"""
        while True:
            tasks_classes = {task.__name__: task for task in
                             self.playground.available_tasks()}
            choices = [(name, task.__doc__) for name, task in
                       tasks_classes.items()]
            task_decision = ListDecision("What shall we do?", choices=choices)
            yield DecisionBunch([task_decision])
            task_name = task_decision.value
            task_class = tasks_classes[task_name]
            yield from self.playground.run_task(task_class(self.playground))
            if task_class.final:
                break

    def finalize(self, success=False):
        """cleanup method"""

        # clean up run relics
        #  backup decisions
        if not success:
            pth = self.paths.root / 'decisions_backup.json'
            save(self._made_decisions, pth)
            user_logger.warning("Decisions are saved in '%s'. Rename file to "
                                "'decisions.json' to reuse them.", pth)
            user_logger.error(f'Project "{self.name}" '
                                f'finished, but not successful')

        else:
            save(self._made_decisions, self.paths.decisions)
            user_logger.info(f'Project Exports can be found under '
                             f'{self.paths.export}')
            user_logger.info(f'Project "{self.name}" finished successful')

        # clean up init relics
        #  clean logger
        self._teardown_logger()

    def delete(self):
        """Delete the project."""
        self.finalize(True)
        self.paths.delete(False)
        user_logger.info("Project deleted")

    def reset(self):
        """Reset the current project."""
        user_logger.info("Project reset")
        self.playground.state.clear()
        self.playground.history.clear()
        self._made_decisions.clear()

    def __repr__(self):
        return "<Project(%s)>" % self.paths.root
