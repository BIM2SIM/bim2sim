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


def run_example_simple_hvac_aixlib():
    """Run an HVAC simulation with the AixLib backend.

    This example runs an HVAC with the aixlib backend. Specifies project
    directory and location of the HVAC IFC file. Then, it creates a bim2sim
    project with the aixlib backend. Simulation settings are specified (here,
    the aggregations are specified), before the project is executed with the
    previously specified settings."""

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(
            prefix='bim2sim_example_simple_aixlib').name)


    # Set path of ifc for hydraulic domain with the fresh downloaded test models
    ifc_paths = {
        IFCDomain.hydraulic:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/hydraulic/ifc/'
            'hvac_heating.ifc'
    }


    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)

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

    project = Project.create(project_path, ifc_paths, 'aixlib')

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    # specify simulation settings
    project.sim_settings.aggregations = [
        'UnderfloorHeating',
        'Consumer',
        'PipeStrand',
        'ParallelPump',
        'ConsumerHeatingDistributorModule',
        'GeneratorOneFluid'
    ]
    project.sim_settings.group_unidentified = 'name_and_description'

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
    handler.handle(project.run(interactive=False))

    # Cleanup connection
    try:
        tcp_client.send_message(json.dumps({"command": "finish"}))
        print("Projekt abgeschlossen, Verbindung wird beendet.")
    except:
        pass
    tcp_client.stop()

# IfcBuildingElementProxy: skip
# Rücklaufverschraubung: 'HVAC-PipeFitting',
# Apparate (M_606) 'HVAC-Distributor',
# 3-Wege-Regelventil PN16: 'HVAC-ThreeWayValve',
# True * 6
# efficiency: 0.95
# flow_temperature: 70
# nominal_power_consumption: 200
# return_temperature: 50
# heat_capacity: 10 * 7


if __name__ == '__main__':
    run_example_simple_hvac_aixlib()
