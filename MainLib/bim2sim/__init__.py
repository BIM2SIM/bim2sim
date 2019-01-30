"""BIM2SIM library"""

import os
import sys
import importlib
import pkgutil
import logging

import pkg_resources

from bim2sim.ifc2python import ifc2python
from bim2sim.manage import BIM2SIMManager
from bim2sim.tasks import PlantSimulation

VERSION = '0.1-dev'

def get_backends(by_entrypoint=False):
    """load all possible plugins"""
    logger = logging.getLogger(__name__)

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
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

    # silence matplotlib
    matlog = logging.getLogger('matplotlib')
    matlog.level = logging.INFO

    logging.debug("Logging setup done.")


def main(ifc_path, backend=None, run=False, task=None):
    """Main entry point"""

    assert ifc_path, "No ifc_path passed"
    assert backend, "No backend passed"
    logger = logging.getLogger(__name__)

    plugins = get_backends()

    logger.info("Loading backend '%s' ...", backend)
    manager_cls = plugins.get(backend)()

    if manager_cls is None:
        msg = "Simulation '%s' not found in plugins. Available plugins:\n - "%(backend)
        msg += '\n - '.join(list(plugins.keys()) or ['None'])
        raise AttributeError(msg)

    if not BIM2SIMManager in manager_cls.__bases__:
        raise AttributeError("Got invalid manager from %s"%(backend))

    if not task:
        task = PlantSimulation() #TODO

    # prepare simulation
    manager = manager_cls(task, ifc_path)

    # run Manager
    manager.run()

    finish()


def _debug_run():
    logging_setup()
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))
    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))

    main(path_ifc, "hkesim")

if __name__ == '__main__':
    _debug_run()
