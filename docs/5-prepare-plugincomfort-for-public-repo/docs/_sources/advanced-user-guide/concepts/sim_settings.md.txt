(simulation_setting)=
# Simulation settings
## What are simulation settings?
`bim2sim` uses prescribed settings which define how a specific simulation
should be handled. For basic setup we have a [BaseSimSettings](BaseSimSettings),
which is extended for the different simulation types (e.g.
[BuildingSimSettings](BuildingSimSettings)) and this domain simulation type 
specific settings can also be further specified for each [Plugin](Plugin)
(e.g. [TEASERSimSettings](TEASERSimSettings) or
[EnergyPlusSimSettings](EnergyPlusSimSettings)) via class inheritance.
 
Each [Plugin](Plugin) has a set of predefined settings. But the different settings can 
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
The pre-implemented workflows hold the needed settings for the simulation with 
the pre-implemented Plugins. For further customization you can add your own 
Workflow (from scratch or by inheriting from the existing ones) and add your own
settings that you might miss from the existing ones.

## List of current simulation settings:
The following tables provide an overview of simulation settings for the 
different simulation types.

### BaseSimSettings

| Setting Name             | Type         | Default       | Description                                                                                                       |
|--------------------------|--------------|---------------|-------------------------------------------------------------------------------------------------------------------|
| dymola_simulation        | Boolean      | False         | Run a Simulation with Dymola after model export?                                                                  |
| create_external_elements | Boolean      | False         | Create external elements?                                                                                         |
| max_wall_thickness       | Number       | 0.3           | Choose maximum wall thickness as a tolerance for mapping opening boundaries to their base surface (Wall).         |
| group_unidentified       | Choice       | 'fuzzy'       | To reduce the number of decisions by user to identify elements which can not be identified automatically.         |
| fuzzy_threshold          | Number       | 0.7           | If using fuzzy search in the `group_unidentified` setting, set the similarity threshold.                          |
| reset_guids              | Boolean      | False         | Reset GlobalIDs from imported IFC if duplicate GlobalIDs occur in the IFC.                                        |

### PlantSimSettings

| Setting Name    | Type    | Default | Description                                                                            |
|-----------------|---------|---------|----------------------------------------------------------------------------------------|
| aggregations    | Choice (MultipleChoice) | [list]  | Choose which aggregations should be applied on the hydraulic network.                  |

### BuildingSimSettings

| Setting Name                    | Type       | Default         | Description                                                                                  |
|---------------------------------|------------|-----------------|----------------------------------------------------------------------------------------------|
| layers_and_materials            | Choice     | LOD.low         | Select how existing Material information in IFC should be treated.                           |
| construction_class_walls        | Choice     | 'heavy'         | Select the most fitting type of construction class for the walls of the selected building.   |
| year_of_construction_overwrite  | Number     | None            | Force an overwrite of the year of construction as a base for the selected construction set.  |
| construction_class_windows      | Choice     | 'Alu- oder...'  | Select the most fitting type of construction class for the windows of the selected building. |
| heating                         | Boolean    | True            | Whether the building should be supplied with heating.                                        |
| cooling                         | Boolean    | False           | Whether the building should be supplied with cooling.                                        |
| deactivate_ahu                  | Boolean    | False           | If True, the AHU unit will be deactivated for all thermal zones.                             |
| prj_use_conditions              | Path       | None            | Path to a custom UseConditions.json for the specific project.                                |
| prj_custom_usages               | Path       | None            | Path to a custom customUsages.json for the specific project.                                 |
| setpoints_from_template         | Boolean    | False           | Use template heating and cooling profiles instead of setpoints from IFC.                     |

### TEASERSimSettings

| Setting Name    | Type    | Default | Description                                                                             |
|-----------------|---------|---------|-----------------------------------------------------------------------------------------|
| zoning_setup    | Choice  | LOD.low | Select the criteria based on which thermal zones will be aggregated.                      |
| zoning_criteria | Choice  | ZoningCriteria.usage | Choose the zoning criteria for thermal zone aggregation.                                 |

### EnergyPlusSimSettings
(EnergyPlus_sim_settings)=

| Setting Name           | Type      | Default           | Description                                                                  | Choices |
|------------------------|-----------|-------------------|-----------------------------------------------------------------------------|---------------|
| cfd_export             | Boolean   | False             | Whether to use CFD export for this simulation or not.                       |               |
| split_bounds           | Boolean   | False             | Whether to convert non-convex space boundaries or not.                      |               |
| add_shadings           | Boolean   | True              | Whether to add shading surfaces if available or not.                        |               |
| split_shadings         | Boolean   | False             | Whether to convert non-convex shading boundaries or not.                    |               |
| run_full_simulation    | Boolean   | False             | Choose simulation period.                                                   |               |
| ep_version             | Choice    | '9-4-0'           | Choose EnergyPlus Version.                                                  |'9-2-0', '9-4-0'|
| ep_install_path        | Path      | Path('/usr/local/EnergyPlus-9-4-0/')   | Choose EnergyPlus Installation Path.                   |               |
| system_sizing          | Boolean   | True              | Whether to do system sizing calculations in EnergyPlus or not.              |               |
| run_for_sizing_periods | Boolean   | False             | Whether to run the EnergyPlus simulation for sizing periods or not.         |               |
| run_for_weather_period | Boolean   | True              | Whether to run the EnergyPlus simulation for weather file period or not.    |               |
| solar_distribution     | Choice    | 'FullExterior'    | Choose solar distribution.                                                  |'FullExterior', 'FullInteriorAndExterior'|
| add_window_shading     | Choice    | None              | Choose window shading.                                                      |'Interior', 'Exterior' |
| output_format          | Choice    | 'CommaAndHTML'    | Choose output format for result files.                                      |'Comma', 'Tab', 'Fixed', 'HTML', 'XML', 'CommaAndHTML','TabAndHTML', 'XMLAndHTML', 'All' |
| unit_conversion        | Choice    | 'JtoKWH'          | Choose unit conversion for result files.                                    |'None', 'JtoKWH', JtoMJ', 'JtoGJ', 'InchPound'              |
| output_keys            | Choice (MultipleChoice)   | ['output_outdoor_conditions', 'output_zone_temperature', 'output_zone', 'output_infiltration', 'output_meters'] | Choose groups of output variables (multiple choice).                        |'output_outdoor_conditions', 'output_internal_gains', 'output_zone_temperature', 'output_zone', 'output_infiltration', 'output_meters',  'output_dxf'            |

### CFDSimSettings

No specific settings provided.

### LCAExportSettings

No specific settings provided.

### ComfortSimSettings
(ComfortSimSettings)=

| Setting Name           | Type      | Default           | Description                                                                                  |
|------------------------|-----------|-------------------|----------------------------------------------------------------------------------------------|
| prj_use_conditions     | [Path]    | UseConditionsComfort.json' in PluginComfort | Path to a custom UseConditions.json for the comfort application.   |
| use_dynamic_clothing   | Boolean   | False             |Use dynamic clothing according to ASHRAE 55 standard.                                         |
