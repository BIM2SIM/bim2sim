"""bim2sim main module.

This tool can be used to create simulation models based on IFC4 files.

Usage:
    bim2sim project create <project_path> [-i <source>] [-s <target>] [-o]
    bim2sim project load [<project_path>]
    bim2sim --help
    bim2sim --version

Options:
    load                Load project from current working directory or given path
    create              Create project folder on given relative or absolute path
    -h --help           Show this screen.
    -v --version        Show version.
    -s <target> --sim <target>  Simulation to convert to.
    -i <source> --ifc <source>  Path to ifc file
    -o --open           Open config file
"""
from importlib.metadata import version

import docopt

from bim2sim import run_project
from bim2sim.project import Project, FolderStructure
from bim2sim.kernel.decision.console import ConsoleDecisionHandler


def get_version():
    """Get package version"""
    try:
        return version("bim2sim")
    except Exception:
        return "unknown"


def commandline_interface():
    """user interface"""

    args = docopt.docopt(__doc__, version=get_version())

    # arguments
    project = args.get('project')
    load = args.get('load')
    create = args.get('create')

    path = args.get('<project_path>')
    target = args.get('--sim')
    source = args.get('--ifc')
    open_conf = args.get('--open')

    if project:
        if create:
            FolderStructure.create(path, source, target, open_conf)
            exit(0)
            # pro = Project.create(path, source, target, open_conf)
        elif load:
            pro = Project(path)
            handler = ConsoleDecisionHandler()
            run_project(pro, handler)
            handler.shutdown(True)
    else:
        print("Invalid arguments")
        exit()


commandline_interface()
