"""Managing related"""
import logging
from abc import ABCMeta

logger = logging.getLogger(__name__)


class Plugin:
    """Base class of overall bim2sim managing instance"""
    __metaclass__ = ABCMeta

    available_plugins = {}

    name: str = None
    default_workflow = None
    tasks: set = None
    elements: set = None

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
    def get_plugin(cls, name: str):
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
