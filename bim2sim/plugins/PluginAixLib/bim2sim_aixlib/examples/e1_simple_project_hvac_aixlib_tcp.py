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


def run_example_with_blender_ifc():
    """
    Führt ein HVAC-Simulation mit AixLib backend aus, wobei der IFC-Pfad von Blender kommt.

    Dieser neue Workflow:
    1. Verbindet sich mit Blender
    2. Fragt den IFC-Pfad von Blender ab
    3. Verwendet diesen Pfad für das bim2sim Projekt
    """

    # Create a temp directory for the project
    project_path = Path(
        tempfile.TemporaryDirectory(
            prefix='bim2sim_blender_integration').name)

    print(f"Projekt-Verzeichnis: {project_path}")

    # Create TCP client for communication with Blender
    tcp_client = TCPClient(host="localhost", port=65432)

    # Verbindung wiederholt versuchen, bis sie erfolgreich ist
    max_attempts = 30
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
        print("Konnte keine Verbindung zum Blender-Server herstellen.")
        print("Bitte stellen Sie sicher, dass:")
        print("1. Blender läuft")
        print("2. Das bim2sim Plugin aktiviert ist")
        print("3. Der TCP-Server in Blender gestartet ist")
        sys.exit(1)

    # Kurze Pause für die Verbindungsherstellung
    time.sleep(1)

    # Create TCP decision handler
    handler = TCPDecisionHandler(tcp_client)

    # IFC-Pfad von Blender anfordern
    print("Fordere IFC-Pfad vom Blender-Server an...")
    ifc_path = handler.get_ifc_path_from_blender(timeout=30.0)

    if not ifc_path:
        print("FEHLER: Kein IFC-Pfad von Blender erhalten!")
        print("Bitte stellen Sie sicher, dass in Blender eine IFC-Datei geladen ist.")
        tcp_client.stop()
        sys.exit(1)

    # Validiere den IFC-Pfad
    if not handler.validate_ifc_path(ifc_path):
        print(f"FEHLER: IFC-Pfad ist ungültig oder Datei existiert nicht: {ifc_path}")
        tcp_client.stop()
        sys.exit(1)

    print(f"Verwende IFC-Datei von Blender: {ifc_path}")

    # IFC-Pfade für das Projekt definieren
    # Annahme: Die Datei von Blender ist für das hydraulische Domain
    ifc_paths = {
        IFCDomain.hydraulic: Path(ifc_path)
    }

    # Falls du mehrere Domains brauchst, kannst du hier weitere Pfade hinzufügen:
    # ifc_paths[IFCDomain.thermal] = Path("pfad/zu/thermal.ifc")
    # ifc_paths[IFCDomain.structural] = Path("pfad/zu/structural.ifc")

    print("Erstelle bim2sim Projekt...")
    try:
        project = Project.create(project_path, ifc_paths, 'aixlib')
    except Exception as e:
        print(f"Fehler beim Erstellen des Projekts: {e}")
        tcp_client.stop()
        sys.exit(1)

    # Weather file data setzen (optional - kann angepasst werden)
    try:
        weather_file_path = (
                Path(bim2sim.__file__).parent.parent /
                'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos'
        )

        if weather_file_path.exists():
            project.sim_settings.weather_file_path = weather_file_path
            print(f"Weather file gesetzt: {weather_file_path}")
        else:
            print("Warnung: Standard-Weather-File nicht gefunden. Projekt wird ohne Weather-File fortgesetzt.")
    except Exception as e:
        print(f"Warnung: Fehler beim Setzen des Weather-Files: {e}")

    # Simulation settings spezifizieren
    project.sim_settings.aggregations = [
        'UnderfloorHeating',
        'Consumer',
        'PipeStrand',
        'ParallelPump',
        'ConsumerHeatingDistributorModule',
        'GeneratorOneFluid'
    ]
    project.sim_settings.group_unidentified = 'name_and_description'

    print("Simulation-Settings konfiguriert")

    # Modifiziere TCPClient für unbegrenzten Timeout bei Decision-Verarbeitung
    original_receive_message = tcp_client.receive_message

    def receive_message_with_extended_timeout(*args, **kwargs):
        # Für Decision-Verarbeitung längeren Timeout verwenden
        if 'timeout' not in kwargs or kwargs['timeout'] is None:
            kwargs['timeout'] = 300.0  # 5 Minuten für komplexe Decisions
        return original_receive_message(*args, **kwargs)

    tcp_client.receive_message = receive_message_with_extended_timeout

    # Informiere Blender über den Projektstart
    try:
        project_info = {
            "command": "project_started",
            "project_path": str(project_path),
            "ifc_file": str(ifc_path),
            "backend": "aixlib",
            "message": "bim2sim Projekt gestartet mit IFC-Datei von Blender"
        }
        tcp_client.send_message(json.dumps(project_info))
        print("Projekt-Info an Blender gesendet")
    except Exception as e:
        print(f"Warnung: Konnte Projekt-Info nicht an Blender senden: {e}")

    # Handle the project execution using the TCP handler
    print("\n" + "=" * 60)
    print("STARTE INTERAKTIVE AUSFÜHRUNG MIT BLENDER-INTEGRATION")
    print("=" * 60)
    print("Alle Entscheidungen werden jetzt in Blender angezeigt.")
    print("Bitte wechseln Sie zu Blender und beantworten Sie die Fragen.")
    print("=" * 60 + "\n")

    try:
        # Projekt mit dem Handler ausführen
        result = handler.handle(project.run(interactive=False))
        print(f"\nProjekt erfolgreich abgeschlossen! Ergebnis: {result}")

    except KeyboardInterrupt:
        print("\nProjekt durch Benutzer abgebrochen")
        handler.shutdown(success=False)
        sys.exit(1)

    except Exception as e:
        print(f"\nFehler bei der Projektausführung: {e}")
        import traceback
        traceback.print_exc()
        handler.shutdown(success=False)
        sys.exit(1)

    # Projekt erfolgreich abgeschlossen
    print("\n" + "=" * 60)
    print("PROJEKT ERFOLGREICH ABGESCHLOSSEN")
    print("=" * 60)
    print(f"Projekt-Verzeichnis: {project_path}")
    print(f"IFC-Datei: {ifc_path}")
    print("Sie können die Ergebnisse im Projekt-Verzeichnis finden.")
    print("=" * 60)

    # Cleanup connection
    handler.shutdown(success=True)


def run_example_simple_hvac_aixlib():
    """
    Legacy-Funktion für Rückwärtskompatibilität.
    Leitet an die neue Blender-Integration weiter.
    """
    print("Warnung: Diese Funktion verwendet jetzt die Blender-Integration.")
    print("Der IFC-Pfad wird von Blender angefordert statt fest definiert.")
    print("")
    run_example_with_blender_ifc()


def main():
    """Hauptfunktion mit Benutzerinteraktion"""
    print("bim2sim Blender Integration")
    print("=" * 40)
    print("Dieses Skript erstellt ein bim2sim-Projekt basierend auf")
    print("einer IFC-Datei, die in Blender geladen ist.")
    print("")
    print("Voraussetzungen:")
    print("1. Blender ist geöffnet")
    print("2. bim2sim Plugin ist aktiviert")
    print("3. Eine IFC-Datei ist in Blender geladen (über Bonsai BIM)")
    print("4. Der TCP-Server ist in Blender gestartet")
    print("")

    input("Drücken Sie Enter um fortzufahren...")

    try:
        run_example_with_blender_ifc()
    except KeyboardInterrupt:
        print("\nProgramm durch Benutzer abgebrochen")
        sys.exit(0)


if __name__ == '__main__':
    main()