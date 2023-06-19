(simulation_setting)=
# Simulation settings
## What are simulation settings?
`bim2sim` uses prescribed settings which define how a specific simulations 
should be handled. For basic setup we have a [BaseSimSettings](BaseSimSettings),
which is extended for the different simulation types (e.g.
[BuildingSimSettings](BuildingSimSettings)) and this domain simulation type 
specific settings can also be further specified for each [Plugin](Plugin)
(e.g. [TEASERSimSettings](TEASERSimSettings) or
[EnergyPlusSimSettings](EnergyPlusSimSettings)) via clas inheritance.
 
Each [Plugin](Plugin) has a setting predefined. But the different settings can 
easily be changed (see below)

## How do settings work?
(sim_settings_concept)=
Each instance of a simulation settings owns a 
[SettingsManager](SettingsManager) to manage all simulation specific 
[Settings](Setting). A setting can be used to concretize the way 
 how [tasks](task) are executed. E.g. the level of detail ([LOD](LOD)) of the 
setting `layers_and_materials` with which the layers of building elements and 
their materials should be inspected can be defined either set LOD.low or 
LOD.full. Currently, each [Setting](Setting) has a specified 
number of choices from which one or multiple can be chosen.

Additionally, to the settings itself, a simulation setting instance holds the 
`relevant_elements`. These define, which of the existing `bim2sim` 
[elements](elements) will be taken into account for the simulation model 
creation. 

## How to set simulation settings?
There are two different ways to set a workflow setting:
* Define the settings inside the `config.toml` file that is part of every 
[FolderStructure](FolderStructure) of every [Project](project.md).
* Define the settings after the project creation by overwriting the existing ones
```python 
project = Project.create(project_path, ifc_path, 'teaser', open_conf=True)
project.sim_settings.layers_and_materials = LOD.low
 ```
If you want to overwrite the specified `relevant_elements` you can 
do this in the same way
```python
project.sim_settings.relevant_elements = {<classes of elements of interest>}
```
The first way is useful if you want to work in an interactive way, the second is 
more fitting for automated tasks.

## Want to set up your own workflow?
The pre implemented workflows hold the needed settings for the simulation with 
the pre implemented Plugins. For further customization you can add your own 
Workflow (from scratch or by inheriting from the existing ones) and add your own
settings that you might miss from the existing ones.
