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

import logging
import os
import sys

import docopt

from bim2sim.__init__ import main, VERSION, logging_setup

def commandline_interface():
    'user interface'
    logger = logging.getLogger(__name__)
    args = docopt.docopt(__doc__, version=VERSION)

    # Path
    path = args.get('PATH')

    # Simulation
    sim_type = args.get('--sim', 'error')
    if sim_type == 'error':
        logger.error("'--sim' not in args")
        exit()
    elif sim_type is None:
        logger.info('General file checking. No conversion to simulation.')

    # Run flag
    run = args.get('-r')

    return path, sim_type, run


def debug_params():
    logger = logging.getLogger(__name__)
    logger.warning("No parameters passed. Using debug parameters.")
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))
    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_Spaceheaters.ifc'
    path_ifc = os.path.normcase(os.path.join(path_base, rel_example))
        
    sys.argv.append(path_ifc)
    sys.argv.append('-s')
    sys.argv.append('aixlib')
    sys.argv.append('-r')
    logger.info("Debug parameters:\n%s", "\n".join(sys.argv[1:]))

logging_setup()

if len(sys.argv) <= 1:
    debug_params()

main(*commandline_interface())
