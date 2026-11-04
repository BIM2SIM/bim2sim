"""
bim2sim EnergyPlus IDF Generator
=================================

Einfaches Skript zur Erzeugung einer EnergyPlus IDF-Datei aus IFC-Modellen.
Basierend auf dem bim2sim PluginEnergyPlus (Example 2).

Ordnerstruktur:
    mein_projekt/
    ├── generate_idf.py          (dieses Skript)
    ├── config.py                (Konfiguration -- hier anpassen!)
    ├── model.ifc                (IFC-Datei)
    ├── weather.epw              (Wetterdatei im EPW-Format)
    ├── UseConditions.json       (optional: eigene Nutzungsprofile)
    ├── CustomUsages.json        (optional: Mapping IFC-Nutzung -> Profil)
    └── output/                  (wird erzeugt, enthaelt die IDF)

Ausfuehrung:
    python generate_idf.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

# Konfiguration laden
from config import CONFIG


def find_file(directory, extensions, description):
    """Sucht eine Datei mit gegebenen Endungen im Verzeichnis."""
    directory = Path(directory)
    for ext in extensions:
        files = list(directory.glob(f'*{ext}'))
        if files:
            if len(files) > 1:
                print(f"  Hinweis: Mehrere {description} gefunden, "
                      f"verwende: {files[0].name}")
            return files[0]
    return None


def validate_config(config, project_dir):
    """Prueft ob alle benoetigten Dateien vorhanden sind."""
    errors = []

    # IFC-Datei
    ifc_path = Path(config.get('ifc_path', ''))
    if not ifc_path.is_absolute() and str(ifc_path) != '':
        ifc_path = project_dir / ifc_path
    if not ifc_path.is_file():
        # Versuche automatisch im Ordner zu finden
        found = find_file(project_dir, ['.ifc'], 'IFC-Dateien')
        if found:
            config['ifc_path'] = str(found)
            print(f"  IFC-Datei gefunden: {found.name}")
        else:
            errors.append(f"Keine IFC-Datei gefunden in: {project_dir}")
    else:
        config['ifc_path'] = str(ifc_path)

    # Wetterdatei
    weather_path = Path(config.get('weather_file', ''))
    if not weather_path.is_absolute() and str(weather_path) != '':
        weather_path = project_dir / weather_path
    if not weather_path.is_file():
        found = find_file(project_dir, ['.epw'], 'Wetterdateien')
        if found:
            config['weather_file'] = str(found)
            print(f"  Wetterdatei gefunden: {found.name}")
        else:
            errors.append(f"Keine EPW-Wetterdatei gefunden in: {project_dir}")
    else:
        config['weather_file'] = str(weather_path)

    # Optionale Dateien
    for key, desc in [('use_conditions', 'UseConditions.json'),
                      ('custom_usages', 'CustomUsages.json')]:
        path_str = config.get(key, '')
        if path_str:
            p = Path(path_str)
            if not p.is_absolute():
                p = project_dir / p
            if p.is_file():
                config[key] = str(p)
                print(f"  {desc} gefunden: {p.name}")
            else:
                print(f"  Hinweis: {desc} nicht gefunden ({p}), "
                      f"verwende Standard-Templates")
                config[key] = None

    return errors


def run():
    """Hauptfunktion: Erzeugt eine IDF-Datei aus den Projektdateien."""

    print("=" * 60)
    print("bim2sim EnergyPlus IDF Generator")
    print("=" * 60)

    # Projektverzeichnis = Ordner in dem dieses Skript liegt
    project_dir = Path(__file__).parent
    print(f"\nProjektverzeichnis: {project_dir}")

    # Konfiguration kopieren (nicht das Original veraendern)
    config = dict(CONFIG)

    # Dateien validieren
    print("\nDateien pruefen:")
    errors = validate_config(config, project_dir)
    if errors:
        print("\nFehler:")
        for e in errors:
            print(f"  - {e}")
        print("\nBitte config.py anpassen oder Dateien bereitstellen.")
        sys.exit(1)

    # Output-Verzeichnis
    output_dir = project_dir / 'output'
    output_dir.mkdir(exist_ok=True)
    print(f"\nAusgabeverzeichnis: {output_dir}")

    # bim2sim importieren
    print("\nbim2sim wird geladen...")
    try:
        from bim2sim import Project
        from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
        from bim2sim.kernel.decision import DecisionBunch
        from bim2sim.utilities.types import IFCDomain, LOD
    except ImportError as e:
        print(f"\nFehler: bim2sim konnte nicht importiert werden: {e}")
        print("Bitte sicherstellen, dass bim2sim installiert ist.")
        sys.exit(1)

    # Projekt erstellen (in temporaerem Verzeichnis, da bim2sim dort
    # eine eigene Ordnerstruktur anlegt)
    print("Projekt wird erstellt...")
    ifc_paths = {
        IFCDomain.arch: Path(config['ifc_path'])
    }
    temp_dir = Path(tempfile.mkdtemp(prefix='bim2sim_idf_'))
    print(f"  Arbeitsverzeichnis: {temp_dir}")
    project = Project.create(temp_dir, ifc_paths, 'energyplus')

    # --- Simulation Settings konfigurieren ---

    # Wetterdatei
    project.sim_settings.weather_file_path = Path(config['weather_file'])

    # Wandaufbauten und Materialien aus Templates
    project.sim_settings.layers_and_materials = LOD.low
    project.sim_settings.construction_class_walls = config.get(
        'construction_class_walls', 'iwu_heavy')
    project.sim_settings.construction_class_windows = config.get(
        'construction_class_windows',
        'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach')

    # Heizung / Kuehlung
    project.sim_settings.cooling_tz_overwrite = config.get(
        'cooling', True)
    project.sim_settings.setpoints_from_template = config.get(
        'setpoints_from_template', True)

    # Simulation NICHT ausfuehren -- nur IDF erzeugen
    project.sim_settings.run_full_simulation = False

    # EnergyPlus Version und Installationspfad
    ep_version = config.get('ep_version', '9-4-0')
    project.sim_settings.ep_version = ep_version
    if config.get('ep_install_path'):
        project.sim_settings.ep_install_path = Path(
            config['ep_install_path'])

    # Ergebnisvariablen (fuer spaetere Simulation relevant)
    project.sim_settings.sim_results = config.get('sim_results', [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out",
        "internal_gains_machines_rooms", "internal_gains_persons_rooms",
        "internal_gains_lights_rooms",
        "heat_set_rooms", "cool_set_rooms"
    ])

    # Eigene Nutzungsprofile (optional)
    if config.get('use_conditions'):
        project.sim_settings.prj_use_conditions = Path(
            config['use_conditions'])
        print(f"  Eigene UseConditions: {config['use_conditions']}")

    if config.get('custom_usages'):
        project.sim_settings.prj_custom_usages = Path(
            config['custom_usages'])
        print(f"  Eigene CustomUsages: {config['custom_usages']}")

    # Plots nicht erzeugen (wir wollen nur die IDF)
    project.sim_settings.create_plots = False

    # --- Decisions automatisch beantworten ---
    # Diese Antworten kommen aus Example 2 und muessen ggf.
    # an die eigene IFC-Datei angepasst werden.
    space_boundary_generator = config.get(
        'space_boundary_generator', 'Other')
    handle_proxies = tuple(config.get(
        'handle_proxies', [None] * 12))
    construction_year = config.get('construction_year', 2015)

    answers = (space_boundary_generator,
               *handle_proxies,
               construction_year)

    print(f"\nAutomatische Antworten:")
    print(f"  Space Boundary Generator: {space_boundary_generator}")
    print(f"  Handle Proxies: {len(handle_proxies)}x None")
    print(f"  Baujahr: {construction_year}")

    # --- Projekt ausfuehren ---
    print("\n" + "-" * 60)
    print("Starte IDF-Erzeugung...")
    print("-" * 60 + "\n")

    # --- Fallback-Handler: beantwortet unbekannte Decisions automatisch ---
    class FallbackDecisionHandler(DebugDecisionHandler):
        """DecisionHandler der bei fehlenden Antworten Defaults nutzt."""

        def get_answers_for_bunch(self, bunch: DecisionBunch) -> list:
            answers = []
            for decision in bunch:
                # Versuche vordefinierte Antwort
                try:
                    answer = next(self.answers)
                    answers.append(answer)
                    continue
                except StopIteration:
                    pass

                # Fallback: Default oder erste Option
                if decision.default is not None:
                    print(f"  [Fallback] {decision.global_key}: "
                          f"Default = {decision.default}")
                    answers.append(decision.default)
                elif hasattr(decision, 'items') and decision.items:
                    # ListDecision: ersten Wert direkt verwenden
                    value = decision.items[0]
                    print(f"  [Fallback] {decision.global_key}: "
                          f"Erste Option = {value}")
                    answers.append(value)
                else:
                    print(f"  [Fallback] {decision.global_key}: None")
                    answers.append(None)
            return answers

    handler = FallbackDecisionHandler(answers)

    try:
        handler.handle(project.run())
    except Exception as e:
        # bim2sim meldet oft "not successful" auch wenn die IDF
        # erzeugt wurde (z.B. weil die Simulation nicht lief)
        print(f"\nHinweis: {e}")

    # IDF suchen und in Ausgabeverzeichnis kopieren
    print("\n" + "-" * 60)
    # Nur die erzeugte IDF aus dem SimResults-Ordner kopieren,
    # nicht die Zwischen-Dateien (Minimal.idf, Schedules.idf etc.)
    sim_results = temp_dir / 'export' / 'EnergyPlus' / 'SimResults'
    if sim_results.exists():
        idf_files = list(sim_results.rglob('*.idf'))
    else:
        # Fallback: alle IDFs im Temp-Verzeichnis, aber ohne bekannte
        # Zwischen-Dateien
        skip = {'Minimal.idf', 'Schedules.idf'}
        idf_files = [f for f in temp_dir.rglob('*.idf')
                     if f.name not in skip]

    if idf_files:
        print("IDF-Datei(en) erzeugt:")
        for idf in idf_files:
            dest = output_dir / idf.name
            shutil.copy2(idf, dest)
            print(f"  {dest}")
        print("\nDiese Datei(en) koennen direkt in EnergyPlus "
              "geoeffnet werden.")
    else:
        print("Keine IDF-Datei gefunden. Bitte Log-Ausgabe pruefen.")

    print("=" * 60)


if __name__ == '__main__':
    run()