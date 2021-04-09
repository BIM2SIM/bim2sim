"""BIM2SIM library"""

import os
import sys

import logging
import typing
import importlib
import pkgutil

from bim2sim.kernel import ifc2python
from bim2sim.plugin import Plugin
from bim2sim.project import Project, FolderStructure
from bim2sim.workflow import PlantSimulation, BPSMultiZoneSeparated
from bim2sim.decision import Decision
from bim2sim.plugins import DummyPlugin

VERSION = '0.1-dev'

# TODO: setup: copy backends to bim2sim/backends
workflow_getter = {'aixlib': PlantSimulation,
                   'teaser': BPSMultiZoneSeparated,
                   'hkesim': PlantSimulation,
                   'energyplus': BPSMultiZoneSeparated}


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

    logging.debug("Logging setup done.")


def setup_default():
    """Main entry point"""
    logging_setup()
    logger = logging.getLogger(__name__)

    plugins = load_plugins()
    # if not plugins:
    #     raise AssertionError("No plugins found!")

    from bim2sim.decision.console import ConsoleFrontEnd
    Decision.set_frontend(ConsoleFrontEnd())


def setup(frontend_name='default'):
    if frontend_name == 'ExternalFrontEnd':
        from bim2sim.decision.external import ExternalFrontEnd as Frontend
    else:
        from bim2sim.decision.console import ConsoleFrontEnd as Frontend
    Decision.set_frontend(Frontend())


def _debug_run_hvac():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))
    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))
    path_example = r"C:\temp\bim2sim\testproject"

    setup_default()

    if Project.is_project_folder(path_example):
        project = Project(path_example)
    else:
        project = Project.create(path_example, path_ifc, 'hkesim', )

    # setup_defualt(project.config['Frontend']['use'])
    project.run()


def _debug_run_bps():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))

    rel_example = 'ExampleFiles/AC20-FZK-Haus.ifc'
    # rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Architektur_spaces.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))
    path_example = r"C:\temp\bim2sim\testproject_bps2"

    if Project.is_project_folder(path_example):
        project = Project(path_example)
    else:
        project = Project.create(path_example, path_ifc, 'teaser', )

    project.run()


def _debug_run_hvac_aixlib():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))
    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))
    path_example = r"C:\temp\bim2sim\testproject_aix"

    if Project.is_project_folder(path_example):
        project = Project(path_example)
    else:
        project = Project.create(path_example, path_ifc, 'aixlib', )

    project.run()


def _debug_run_cfd():
    """Create example project and copy ifc if necessary"""

    sys.path.append("/home/fluid/Schreibtisch/B/bim2sim-coding/PluginCFD")
    path_example = r"/home/fluid/Schreibtisch/B/temp"
    # unter ifc muss datei liegen

    if Project.is_project_folder(path_example):
        project = Project(path_example)
    else:
        project = Project.create(path_example, target='cfd', )

    project.run()


setup_default()

if __name__ == '__main__':
    # _debug_run_cfd()
    # _debug_run_bps()
    _debug_run_hvac()

