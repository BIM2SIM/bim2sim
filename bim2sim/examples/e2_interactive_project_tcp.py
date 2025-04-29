import tempfile
from pathlib import Path
import json
import time
import sys

import bim2sim
from bim2sim import Project
from bim2sim.elements import bps_elements
from bim2sim.utilities.types import IFCDomain
from bim2sim.elements.base_elements import Material
from bim2sim.tcp_connection import TCPClient
from bim2sim.kernel.decision.tcp_decisionhandler import TCPDecisionHandler


def run_interactive_example():
    """Run the building simulation with teaser as backend in interactive mode with TCP connections to Blender."""
    # Create a temp directory for the project
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example_tcp').name)

    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }

    # Ensure IFC paths exist
    for domain, path in ifc_paths.items():
        if not path.exists():
            print(f"FEHLER: IFC-Datei existiert nicht: {path}")
            print(f"Bitte prüfen Sie den Pfad: {path.parent}")
            sys.exit(1)

    # Create TCP client for communication with Blender
    tcp_client = TCPClient(host="localhost", port=65432)

    # Verbindung wiederholt versuchen, bis sie erfolgreich ist
    max_attempts = 30  # 30 Versuche
    attempt = 0

    print("Versuche, eine Verbindung zum Blender-Server herzustellen...")
    while attempt < max_attempts:
        attempt += 1
        tcp_client.start()

        if tcp_client.running:
            print(f"Verbindung zum Blender-Server hergestellt (Versuch {attempt})")
            break

        print(f"Verbindungsversuch {attempt}/{max_attempts} fehlgeschlagen. Warte 2 Sekunden...")
        time.sleep(2)

    if not tcp_client.running:
        print("Konnte keine Verbindung zum Blender-Server herstellen. Bitte starten Sie zuerst den Server in Blender.")
        sys.exit(1)

    # Kurze Pause für die Verbindungsherstellung
    time.sleep(1)

    # Send IFC information to Blender upon connection
    try:
        # Convert all paths to strings and create a message with project info
        ifc_info = {
            "command": "load_ifc",
            "project_path": str(project_path),
            "ifc_files": {str(domain): str(path) for domain, path in ifc_paths.items()}
        }

        # Send the IFC info message
        print(f"Sende IFC-Infos an Blender: {ifc_info}")
        tcp_client.send_message(json.dumps(ifc_info))

        # Wait for confirmation with long timeout
        print("Warte auf Bestätigung vom Blender-Server...")
        response = tcp_client.receive_message(timeout=60.0)  # Gib dem Server 60 Sekunden Zeit zum Antworten
        if response:
            print(f"Blender-Antwort: {response}")
        else:
            print("Keine Bestätigung vom Blender-Server erhalten. Fahre trotzdem fort...")
    except Exception as e:
        print(f"Fehler beim Senden der IFC-Infos an Blender: {e}")

    # Create project with all the settings
    project = Project.create(
        project_path, ifc_paths, 'template', open_conf=True)

    # Set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    # Set relevant elements
    project.sim_settings.relevant_elements = {*bps_elements.items, Material}

    # Ändern der TCPClient-Klasse, um unbegrenzten Timeout zu ermöglichen
    original_receive_message = tcp_client.receive_message

    def receive_message_no_timeout(*args, **kwargs):
        # Immer ohne Timeout aufrufen
        kwargs['timeout'] = None
        return original_receive_message(*args, **kwargs)

    tcp_client.receive_message = receive_message_no_timeout

    # Create TCP decision handler
    handler = TCPDecisionHandler(tcp_client)

    # Handle the project execution using the TCP handler
    print("Starte interaktive Ausführung mit Blender-Verbindung...")
    handler.handle(project.run(interactive=True))

    # Cleanup connection
    try:
        tcp_client.send_message(json.dumps({"command": "finish"}))
        print("Projekt abgeschlossen, Verbindung wird beendet.")
    except:
        pass
    tcp_client.stop()


if __name__ == '__main__':
    run_interactive_example()