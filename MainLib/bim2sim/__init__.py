"""BIM2SIM main module.

Usage:
    bim2sim PATH [-s <target> | --sim=<target>] [-r]
    bim2sim (-h | --help)
    bim2sim --version
    
Options:
    -h --help  Show this screen.
    --version  Show version.
    -s <target> --sim=<target>  Simulation to convert to.
    -r  Run simulatioin
"""

import sys
import importlib
import pkgutil
import logging

import pkg_resources
import docopt

from bim2sim.ifc2python import ifc2python
from bim2sim.simulationbase import SimulationBase

logging.basicConfig(level=logging.DEBUG)
VERSION = '0.1-dev'

def get_simulations(by_entrypoint=False):
    'load all possible plugins'
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
                contend = getattr(module, 'contend', None)
                if not contend:
                    logger.warning("Found potential plugin '%s', but contend is missing", name)
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

    return sim

def ui():
    'user interface'
    logger = logging.getLogger(__name__)
    args = docopt.docopt(__doc__, version=VERSION)

    # Path
    path = args.get('PATH')

    # Simulation
    cls = None
    sim_type = args.get('--sim', 'error')
    if sim_type == 'error':
        logger.error("'--sim' not in args")
        exit()
    elif sim_type is None:
        logger.info('General file checking. No conversion to simulation.')
    else:
        plugins = get_simulations()
        p = plugins.get(sim_type)
        if p is None:
            logger.warning("Simulation '%s' not found in plugins:", sim_type)
            lst = ['Available plugins:'] + (list(plugins.keys()) or ['None'])
            logger.info('\n - '.join(lst))
            exit()
        else:
            cls = p

    # Run flag
    run = args.get('-r')

    return path, cls, run

def finish():
    """cleanup method"""
    logger = logging.getLogger(__name__)
    logger.info('finished')

def main():
    # get input
    ifc_path, sim_cls, run = ui()
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
    return


if __name__ == '__main__':
    if len(sys.argv) <= 1:
        sys.argv.append('D:\\')
        sys.argv.append('-s')
        sys.argv.append('energyPlus')
        sys.argv.append('-r')

    main()
