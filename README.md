# Bim2Sim [![pylint]( https://ebc.pages.git-ce.rwth-aachen.de/projects/EBC0438_BMWi_BIM2SIM_GES/bim2sim-coding/113-add-Sphinx/pylint.svg )]( https://ebc.pages.git-ce.rwth-aachen.de/projects/EBC0438_BMWi_BIM2SIM_GES/bim2sim-coding/113-add-Sphinx/pylint.html ) [![documentation]( https://ebc.pages.git-ce.rwth-aachen.de/projects/EBC0438_BMWi_BIM2SIM_GES/bim2sim-coding/113-add-Sphinx/docs/doc.svg )]( https://ebc.pages.git-ce.rwth-aachen.de/projects/EBC0438_BMWi_BIM2SIM_GES/bim2sim-coding/113-add-Sphinx/docs/index.html )
bim2sim ist eine Bibliothek um BIM Modelle aus dem .ifc Format für unterschiedliche Simulationstools aufzubereiten.
Die grundlegende Struktur des Projekts ist hier dargestellt:
![Toolchain](https://git.rwth-aachen.de/Bim2Sim/Bim2Sim-documentation/raw/master/01_Grafiken/Toolchain.jpg)

#### Entwicklung
Zur Entwicklung sollten die Hauptbibliothek bim2sim sowie alle Plugins über den PYTHONPATH gefunden werden können.
Außerdem sollten folgende Konventionen beachtet werden:
* Als Einzug vier Leerzeichen verwenden
* Dateien als utf-8 formatieren
* vor Commit Code mit PyLint prüfen und Warnungen auf ein Minimum reduzieren.

### Struktur
Zum leichteren Einstieg in die Entwicklung hier ein kurzer Überblick über die Strukut des Projekts:
- **assets**: Additional data inputs, e.g. for enrichment 
- **export**: Export related 
- **kernel**: Logic for element detectionand description, generel ifc2python methods, aggregation ...
- **task**: Tasks are small parts of a workflow, they can be used in different workflows and different domains. Example: Detection of thermal zones
- **workflow**: Workflow builds context for Tasks and holds cross-task settings like intentional LoD. Example: Create BPS-model for modelica -> high wall LoD, low pipe LoD
- **management classes**: manages the project, is bound to a workflow

## MainLib
In diesem Ordner befindet sich die eigentliche bim2sim Bibliothek. Sie enthält allgemeine Methoden und Funktionen zum Einlesen, Verarbeiten und Aufbereiten von .ifc Dateien.
Für mehr Informationen:
```sh
$ python bim2sim --help
```

## Plugins
Über bim2sim Plugins lässt sich die Funktionalität der bim2sim Bibliothek auf konkrete Simulationstools spezialisieren.
Die Plugins werden vom der bim2sim Bibliothek über die Namenskonvention bim2sim_\<name\> automatisch als potenzielle Plugins erkannt. Zur Entwicklung ist es dazu erforderlich, dass die Plugins über den PYTHONPATH gefunden werden können.
