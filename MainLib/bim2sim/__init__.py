"""BIM2SIM library"""

import logging
import typing
import importlib
import pkgutil


from bim2sim.decision.console import ConsoleDecisionHandler
from bim2sim.decision.decisionhandler import DecisionHandler
from bim2sim.kernel import ifc2python
from bim2sim.project import Project
from bim2sim.project import FolderStructure
from bim2sim.plugin import Plugin
from bim2sim.plugins import DummyPlugin


VERSION = '0.1-dev'


def load_plugins(names: typing.Iterable[str] = None) -> typing.Dict[str, Plugin]:
    """Load bim2sim plugins filtered by names if argument names is specified"""
    # TODO: load by names
    # _names = [name for name in names if name.startswith('bim2sim_')]
    logger = logging.getLogger(__name__)
    plugins = {}
    # internal plugins
    plugins[DummyPlugin.name] = DummyPlugin

    # load all
    for finder, name, ispkg in pkgutil.iter_modules():
        if name.startswith('bim2sim_'):
            print(name)
            module = importlib.import_module(name)
            contend = getattr(module, 'CONTEND', None)
            if not contend:
                logger.warning("Found potential plugin '%s', but CONTEND is missing", name)
                continue

            for key, getter in contend.items():
                plugins[key] = getter()
                logger.debug("Found plugin '%s'", name)
    return plugins


def logging_setup():
    """Setup for logging module"""

    formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    root_logger = logging.getLogger(__name__)

    # Stream
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
    # File
    # file_handler = logging.FileHandler(os.path.join(PROJECT.log, "bim2sim.log"))
    # file_handler.setFormatter(formatter)
    # root_logger.addHandler(file_handler)

    root_logger.setLevel(logging.DEBUG)

    # silence matplotlib
    # matlog = logging.getLogger('matplotlib')
    # matlog.level = logging.INFO

    root_logger.debug("Logging setup done.")


def setup_default():
    """Main entry point"""
    logging_setup()
    logger = logging.getLogger(__name__)


def run_project(project: Project, handler: DecisionHandler):
    """Run project using decision handler."""
    return handler.handle(project.run(), project.loaded_decisions)


setup_default()
PLUGINS = load_plugins()

