"""BIM2SIM Plugins"""
import importlib
import logging
import sys
from abc import ABCMeta
from inspect import isclass
from pathlib import Path
from typing import Set, Type, List

from task.base import ITask


logger = logging.getLogger(__name__)


def add_plugins_to_path(root: Path):
    """Add all directories under root to path."""
    for folder in root.glob('*/'):
        if folder.is_dir():
            sys.path.append(folder)
            logger.info("Added %s to path", folder)


add_plugins_to_path(Path(__file__).parent)


class Plugin:
    """Base class of overall bim2sim managing instance"""
    __metaclass__ = ABCMeta

    available_plugins = {}

    name: str = None
    default_workflow = None
    tasks: Set[Type[ITask]] = set()
    default_tasks: List[Type[ITask]] = []
    elements: set = set()

    @classmethod
    def __init_subclass__(cls, **kwargs):
        if not cls.name:
            raise NameError(str(cls))
        if cls.name in cls.available_plugins:
            logger.warning("Plugin with name '%s' already registered. Skipping.", cls.name)
        else:
            cls.available_plugins[str(cls.name).lower()] = cls
            logger.info("Plugin '%s' registered", cls.name)

    @classmethod
    def get_plugin(cls, name: str) -> Type['Plugin']:
        """Get plugin by name
        :rtype: Plugin
        :raise: NameError if name is not available or invalid
        """
        if not name:
            raise NameError(f"Invalid plugin name: {name}")
        plugin = cls.available_plugins.get(name.lower())
        if not plugin:
            msg = f"No Plugin found with name '{name}'. Available plugins:\n - "
            msg += '\n - '.join(cls.available_plugins.keys() or ['None'])
            raise NameError(msg)
        return plugin

    def __repr__(self):
        return "<%s>" % self.__class__.__name__

    def run(self, playground):
        raise NotImplementedError(f"No default run for {self.name} implemented.")


def load_plugin(name: str) -> Plugin:
    """Load Plugin from module.

    Args:
        name: name of plugin module. Prefix 'bim2sim_' may be omitted.
    """
    if not name.startswith('bim2sim_'):
        name = 'bim2sim_' + name
    try:
        # module names are usually lower case
        module = importlib.import_module(name.lower())
    except ImportError:
        if name.lower() != name:
            module = importlib.import_module(name)
        else:
            raise
    plugin = get_plugin(module)
    logger.info("Loaded Plugin %s", plugin.name)
    return plugin


def get_plugin(module) -> Plugin:
    """Get Plugin class from module."""
    for name, value in module.__dict__.items():
        if isclass(value) and issubclass(value, Plugin) and value is not Plugin:
            return value
    raise KeyError(f"Found no Plugin in {module.__file__}")


if __name__ == '__main__':
    plugin = load_plugin('teaser')
    print(plugin.name)
