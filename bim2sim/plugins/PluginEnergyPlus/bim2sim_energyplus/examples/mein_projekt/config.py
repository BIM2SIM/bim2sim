"""
Konfiguration fuer den IDF Generator.
======================================

Hier alle Einstellungen anpassen. Relative Pfade beziehen sich
auf den Ordner in dem dieses Skript liegt.
"""

CONFIG = {

    # === Pflicht-Angaben ===

    # IFC-Datei (relativ oder absolut)
    # Wenn leer, wird automatisch nach *.ifc im Ordner gesucht.
    'ifc_path': '',

    # Wetterdatei im EPW-Format (relativ oder absolut)
    # Wenn leer, wird automatisch nach *.epw im Ordner gesucht.
    'weather_file': '',


    # === Wandaufbauten und Materialien ===

    # Konstruktionsklasse fuer Waende
    # Optionen z.B.: 'iwu_heavy', 'iwu_light', 'tabula_de_standard', ...
    'construction_class_walls': 'iwu_heavy',

    # Konstruktionsklasse fuer Fenster
    'construction_class_windows':
        'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach',


    # === Eigene JSON-Dateien (optional) ===

    # Eigene Nutzungsprofile (UseConditions)
    # Leer lassen fuer Standard-Templates aus bim2sim.
    # Format: siehe UseConditions.json im bim2sim-Paket
    'use_conditions': '',

    # Eigenes Mapping von IFC-Nutzungen auf Profilnamen
    # Leer lassen fuer Standard-Mapping.
    'custom_usages': '',


    # === Heizung / Kuehlung ===

    'cooling': True,
    'setpoints_from_template': True,


    # === EnergyPlus Version ===

    # Version der EnergyPlus-Installation
    # Optionen: '9-2-0', '9-4-0', '22-2-0'
    # Hinweis: Andere Versionen ggf. moeglich (any_string=True),
    # aber nicht offiziell getestet.
    'ep_version': '9-4-0',

    # Installationspfad von EnergyPlus (leer = Standard)
    # Beispiele:
    #   Windows: 'C:/EnergyPlusV9-4-0/'
    #   Linux:   '/usr/local/EnergyPlus-9-4-0/'
    'ep_install_path': 'D:/Software/EnergyPlusV9-4-0',


    # === Baujahr und Decisions ===

    # Space Boundary Generator: 'Other' oder 'IFC'
    'space_boundary_generator': 'Other',

    # Umgang mit unbekannten IFC-Elementen (Proxies)
    # Liste von None-Werten, Laenge abhaengig von der IFC-Datei.
    # Bei 12 unbekannten Elementen: [None] * 12
    'handle_proxies': [None] * 12,

    # Baujahr des Gebaeudes (fuer Konstruktions-Templates)
    'construction_year': 2015,


    # === Ergebnisvariablen ===
    # (relevant wenn die IDF spaeter simuliert wird)

    'sim_results': [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out",
        "internal_gains_machines_rooms", "internal_gains_persons_rooms",
        "internal_gains_lights_rooms",
        "heat_set_rooms", "cool_set_rooms"
    ],
}