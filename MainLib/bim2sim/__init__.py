"""BIM2SIM library"""

import os
import sys
import importlib
import pkgutil
import logging

import pkg_resources

from bim2sim.ifc2python import ifc2python
from bim2sim.simulationbase import SimulationBase

VERSION = '0.1-dev'

def get_simulations(by_entrypoint=False):
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

                for key, cls in contend.items():
                    if not isinstance(key, str):
                        logger.warning("invalid key '%s' in package '%s'", key, name)
                    elif not hasattr(cls, '__bases__'):
                        logger.warning("bad class value for key '%s' in package '%s'", key, name)
                    elif not SimulationBase in cls.__bases__:
                        logger.warning(
                            "Found potential simulation '%s' in package '%s', \
                            but class '%s' does not inherit from %s", 
                            key, name, cls.__name__, SimulationBase.__name__)
                    else:
                        sim[key] = cls
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


def main(ifc_path, backend=None, run=False):
    """Main entry point"""

    assert ifc_path, "No ifc_path passed"
    assert backend, "No backend passed"

    plugins = get_simulations()
    sim_cls = plugins.get(backend)
    if sim_cls is None:
        msg = "Simulation '%s' not found in plugins. Available plugins:\n - "%(backend)
        msg += '\n - '.join(list(plugins.keys()) or ['None'])
        raise AttributeError(msg)

    print('test')
    # read ifc
    data = ifc2python.load_ifc(ifc_path)

    # prepare simulation
    sim = sim_cls()
    sim.prepare(data)

    # run simulation
    if run:
        sim.run()

    finish()


def _debug_run():
    logging_setup()
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))
    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_Spaceheaters.ifc'
    path_ifc = os.path.normcase(os.path.join(path_base, rel_example))

    main(path_ifc, "aixlib")

if __name__ == '__main__':
    _debug_run()
