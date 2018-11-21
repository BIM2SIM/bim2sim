# Bim2Sim
bim2sim ist eine Bibliothek um BIM Modelle aus dem .ifc Format für unterschiedliche Simulationstools aufzubereiten.
Die grundlegende Struktur des Projekts ist hier dargestellt:
![Toolchain](https://git.rwth-aachen.de/Bim2Sim/Bim2Sim-documentation/blob/master/01_Grafiken/Toolchain.jpg)

#### Entwicklung
Zur Entwicklung sollten die Hauptbibliothek bim2sim sowie alle Plugins über den PYTHONPATH gefunden werden können.

## MainLib
In diesem Ordner befindet sich die eigentliche bim2sim Bibliothek. Sie enthält allgemeine Methoden und Funktionen zum Einlesen, Verarbeiten und Aufbereiten von .ifc Dateien.
Für mehr Informationen:
```sh
$ python bim2sim --help
```

## Plugins
Über bim2sim Plugins lässt sich die Funktionalität der bim2sim Bibliothek auf konkrete Simulationstools spezialisieren.
Die Plugins werden vom der bim2sim Bibliothek über die Namenskonvention bim2sim_\<name\> automatisch als potenzielle Plugins erkannt. Zur Entwicklung ist es dazu erforderlich, dass die Plugins über den PYTHONPATH gefunden werden können.
