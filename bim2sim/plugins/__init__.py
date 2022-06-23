"""BIM2SIM Plugins"""
import importlib
import logging
import pkgutil
import sys
from abc import ABCMeta
from inspect import isclass
from pathlib import Path
from typing import Set, Type, List

from bim2sim.task.base import ITask
from bim2sim.workflow import Workflow

logger = logging.getLogger(__name__)


def add_plugins_to_path(root: Path):
    """Add all directories under root to path."""
    for folder in root.glob('*/'):
        if folder.is_dir():
            sys.path.append(str(folder))
            logger.info("Added %s to path", folder)


add_plugins_to_path(Path(__file__).parent)


class Plugin:
    """Base class for bim2sim Plugins.

    Notes:
        This class is used as a namespace. Instantiation is not necessary.

    Attributes:
        name: Name of the Plugin
        default_workflow: default workflow to use in Projects using this Plugin
        tasks: Set of tasks made available by this Plugin
        default_tasks: List of tasks, which should be executed
        elements: Additional Elements made available by this Plugin
    """
    __metaclass__ = ABCMeta

    name: str = None
    default_workflow: Type[Workflow] = None
    tasks: Set[Type[ITask]] = set()
    default_tasks: List[Type[ITask]] = []
    elements: set = set()

    def __repr__(self):
        return "<%s>" % self.__class__.__name__


def available_plugins() -> List[str]:
    """List all available plugins."""
    plugins = []
    for finder, name, is_pkg in pkgutil.iter_modules():
        if is_pkg and name.startswith('bim2sim_'):
            plugins.append(name)
    return plugins


def load_plugin(name: str) -> Type[Plugin]:
    """Load Plugin from module.

    Args:
        name: name of plugin module. Prefix 'bim2sim_' may be omitted.
    """
    if not name.startswith('bim2sim_'):
        name = 'bim2sim_' + name
    try:
        # module names are usually lower case
        module = importlib.import_module(name.lower())
    except ModuleNotFoundError:
        if name.lower() != name:
            module = importlib.import_module(name)
        else:
            raise
    plugin = get_plugin(module)
    logger.info("Loaded Plugin %s", plugin.name)
    return plugin


def get_plugin(module) -> Type[Plugin]:
    """Get Plugin class from module."""
    for name, value in module.__dict__.items():
        if isclass(value) and issubclass(value, Plugin) and value is not Plugin:
            return value
    raise KeyError(f"Found no Plugin in {module.__file__}")


if __name__ == '__main__':
    print(available_plugins())
