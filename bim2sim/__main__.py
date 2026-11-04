"""bim2sim main module.

This tool can be used to create simulation models based on IFC4 files.

Usage:
    bim2sim gui [--host <host>] [--port <port>] [--no-browser]
    bim2sim project create <project_path> [-i <source>] [-s <target>] [-o]
    bim2sim project load [<project_path>]
    bim2sim --help
    bim2sim --version

Options:
    gui                 Start GUI server for web-based project management
    --host <host>       Host to bind GUI server to [default: localhost]
    --port <port>       Port to bind GUI server to [default: 8080]
    --no-browser        Don't open browser automatically

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
import logging

from bim2sim import run_project
from bim2sim.project import Project, FolderStructure
from bim2sim.kernel.decision.console import ConsoleDecisionHandler


def get_version():
    """Get package version"""
    try:
        return version("bim2sim")
    except Exception:
        return "unknown"


def start_gui(host='localhost', port=8080, open_browser=True):
    """Start GUI server."""
    try:
        from bim2sim.gui.server import run_gui_server

        print(f"Starting bim2sim GUI server...")
        print(f"GUI will be available at: http://{host}:{port}")
        print(f"Press CTRL+C to stop")
        print()

        run_gui_server(host=host, port=int(port), open_browser=open_browser)

    except ImportError as e:
        print(f"Error: Could not import GUI module: {e}")
        print("Please install required dependencies:")
        print("  pip install flask flask-socketio flask-cors")
        return 1
    except Exception as e:
        print(f"Error starting GUI: {e}")
        return 1

    return 0


def commandline_interface():
    """User interface"""

    args = docopt.docopt(__doc__, version=get_version())

    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # GUI mode
    if args.get('gui'):
        host = args.get('--host') or 'localhost'
        port = args.get('--port') or '8080'
        open_browser = not args.get('--no-browser')

        exit_code = start_gui(host=host, port=port, open_browser=open_browser)
        exit(exit_code)

    # Project management
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
        elif load:
            pro = Project(path)
            handler = ConsoleDecisionHandler()
            run_project(pro, handler)
            handler.shutdown(True)
    else:
        print("Invalid arguments. Use --help for usage information.")
        exit(1)


if __name__ == '__main__':
    commandline_interface()