"""bim2sim main module.

This tool can be used to create simulation models based on IFC4 files.

Usage:
    bim2sim project create <project_path> [-i <source>] [-s <target>] [-o]
    bim2sim project load [<project_path>]
    bim2sim tcp <host> <port>
    bim2sim --help
    bim2sim --version

Options:
    load                Load project from current working directory or given path
    create              Create project folder on given relative or absolute path
    tcp                 Connect to a TCP server at the given host and port.
    -h --help           Show this screen.
    -v --version        Show version.
    -s <target> --sim <target>  Simulation to convert to.
    -i <source> --ifc <source>  Path to ifc file
    -o --open           Open config file
"""
from importlib.metadata import version
import socket
import docopt
from tcp_connection import TCPClient


from bim2sim import run_project
from bim2sim.project import Project, FolderStructure
from bim2sim.kernel.decision.console import ConsoleDecisionHandler

def get_version():
    """Get package version"""
    try:
        return version("bim2sim")
    except Exception:
        return "unknown"

def start_tcp_client(host, port):
    """Start a TCP client to connect to the Blender server."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((host, int(port)))
            print(f"Connected to server at {host}:{port}")

            while True:
                message = input("Enter message to send (or 'exit' to quit): ")
                if message.lower() == 'exit':
                    print("Closing connection.")
                    break

                client_socket.sendall(message.encode())
                response = client_socket.recv(1024).decode()
                print(f"Server response: {response}")
    except ConnectionRefusedError:
        print(f"Could not connect to server at {host}:{port}. Please ensure the server is running.")
    except Exception as e:
        print(f"An error occurred: {e}")

def commandline_interface():
    """User interface"""

    args = docopt.docopt(__doc__, version=get_version())

    # arguments
    project = args.get('project')
    load = args.get('load')
    create = args.get('create')
    tcp = args.get('tcp')

    path = args.get('<project_path>')
    target = args.get('--sim')
    source = args.get('--ifc')
    open_conf = args.get('--open')
    host = args.get('<host>')
    port = args.get('<port>')

    if args.get('--tcp'):
        tcp_client = TCPClient(host='localhost', port=65432)
        tcp_client.start()
        print("TCP Client gestartet und mit dem Server verbunden.")

    if project:
        if create:
            FolderStructure.create(path, source, target, open_conf)
            exit(0)
        elif load:
            pro = Project(path)
            handler = ConsoleDecisionHandler()
            run_project(pro, handler)
            handler.shutdown(True)
    elif tcp:
        if host and port:
            tcp_client = TCPClient(host='localhost', port=65432)
            tcp_client.start()
            print("Verbunden mit dem Server.")
            tcp_client.send_message("Initiale Nachricht an den Server")
        else:
            print("Error: Host and port must be specified for TCP connection.")
    else:
        print("Invalid arguments")
        exit()

commandline_interface()
