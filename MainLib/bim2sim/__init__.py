"""BIM2SIM library"""

import os
import sys
import importlib
import pkgutil
import logging
from pathlib import Path
import site

import pkg_resources

from bim2sim.kernel import ifc2python
from bim2sim.manage import BIM2SIMManager
from bim2sim.project import PROJECT, get_config
from bim2sim.workflow import PlantSimulation
from bim2sim.decision import Decision

VERSION = '0.1-dev'

# TODO: setup: copy backends to bim2sim/backends


def get_default_backends():
    path = Path(__file__).parent / 'backends'
    backends = []
    for pkg in [item for item in path.glob('**/*') if item.is_dir()]:
        if pkg.name.startswith('bim2sim_'):
            backends.append(pkg)
    return backends


def get_dev_backends():
    path = Path(__file__).parent.parent.parent
    backends = []
    for plugin in [item for item in path.glob('**/*') if item.is_dir()]:
        if plugin.name.startswith('Plugin'):
            for pkg in [item for item in plugin.glob('**/*') if item.is_dir()]:
                if pkg.name.startswith('bim2sim_'):
                    backends.append(pkg)
    return backends


def get_backends(by_entrypoint=False):
    """load all possible plugins"""
    logger = logging.getLogger(__name__)

    default = get_default_backends()
    dev = get_dev_backends()

    # add all plugins to PATH
    sys.path.extend([str(path.parent) for path in default + dev])

    if by_entrypoint:
        sim = {}
        for entry_point in pkg_resources.iter_entry_points('bim2sim'):
            sim[entry_point.name] = entry_point.load()
    else:
        sim = {}
        for finder, name, ispkg in pkgutil.iter_modules():
            if name.startswith('bim2sim_'):
                module = importlib.import_module(name)
                contend = getattr(module, 'CONTEND', None)
                if not contend:
                    logger.warning("Found potential plugin '%s', but CONTEND is missing", name)
                    continue

                for key, getter in contend.items():
                    sim[key] = getter
                    logger.debug("Found plugin '%s'", name)

    return sim


def finish():
    """cleanup method"""
    logger = logging.getLogger(__name__)
    logger.info('finished')


def logging_setup():
    """Setup for logging module"""

    formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    root_logger = logging.getLogger()

    # Stream
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
    # File
    file_handler = logging.FileHandler(os.path.join(PROJECT.log, "bim2sim.log"))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    root_logger.setLevel(logging.DEBUG)

    # silence matplotlib
    matlog = logging.getLogger('matplotlib')
    matlog.level = logging.INFO

    logging.debug("Logging setup done.")


def main(rootpath=None):
    """Main entry point"""

    _rootpath = rootpath or os.getcwd()
    PROJECT.root = _rootpath
    assert PROJECT.is_project_folder(), \
        "'%s' does not look like a project folder. Create a project folder first."%(_rootpath)

    logging_setup()
    logger = logging.getLogger(__name__)

    plugins = get_backends()

    conf = get_config()
    backend = conf["Backend"].get("use")
    assert backend, "No backend set. Check config.ini"

    logger.info("Loading backend '%s' ...", backend)
    manager_cls = plugins.get(backend.lower())()

    if manager_cls is None:
        msg = "Simulation '%s' not found in plugins. Available plugins:\n - "%(backend)
        msg += '\n - '.join(list(plugins.keys()) or ['None'])
        raise AttributeError(msg)

    if not BIM2SIMManager in manager_cls.__bases__:
        raise AttributeError("Got invalid manager from %s"%(backend))

    from bim2sim.decision.console import ConsoleFrontEnd as Frontend
    # from bim2sim.decision.external import ExternalFrontEnd as Frontend
    Decision.set_frontend(Frontend())

    workflow = PlantSimulation() #TODO

    # prepare simulation
    manager = manager_cls(workflow)

    # run Manager
    manager.run()
    #manager.run_interactive()

    finish()


def _debug_run_hvac():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))
    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))
    path_example = r"C:\temp\bim2sim\testproject"

    if not PROJECT.is_project_folder(path_example):
        PROJECT.create(path_example, path_ifc, 'hkesim',)

    main(path_example)


def _debug_run_bps():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))

    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Architektur' \
                      '.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))
    path_example = r"C:\temp\bim2sim\testproject_bps"

    if not PROJECT.is_project_folder(path_example):
        PROJECT.create(path_example, path_ifc, 'TEASER')

    main(path_example)

if __name__ == '__main__':
    _debug_run_hvac()
    # _debug_run_bps()
