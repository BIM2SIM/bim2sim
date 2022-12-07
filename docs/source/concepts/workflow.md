(workflow_concept)=
# Workflow
## What is a workflow?
In `bim2sim` a workflow describes how a specific simulation should be handled. 
Next to the basic [Workflow](workflow.md) we have three workflows pre implemented:
* [BuildingSimulation](BuildingSimulation)
* [PlantSimulation](PlantSimulation)
* [CFDWorkflow](CFDWorkflow)
 
You might think now, why do we have [Plugins](Plugin) and [Workflows](workflow.md)?
A workflow is simulation type specific, while a Plugin is simulation 
environment/tool specific. See also [big-picture](big-picture).

## What are workflow settings?
(workflow_settings_concept)=
Each instance of a [Workflow](workflow.md) owns a 
[SettingsManager](SettingsManager) to manage all workflow specific 
[WorkflowSettings](WorkflowSetting). A setting can be used to concretize the way 
 how the [tasks](task) are executed. E.g. the level of detail ([LOD](LOD)) of the 
setting `layers_and_materials` with which the layers of building elements and 
their materials should be inspected can be defined either set LOD.low or 
LOD.full.  Currently, each [WorkflowSetting](WorkflowSetting) has a specified 
number of choices from which one or multiple can be chosen.

## How to set workflow settings?
There are two different ways to set a workflow setting:
* Define the settings inside the `config.toml` file that is part of every 
[FolderStructure](FolderStructure) of every [Project](project.md).
* Define the settings after the project creation by overwriting the existing ones
```python 
project = Project.create(project_path, ifc_path, 'teaser', open_conf=True)
project.workflow.layers_and_materials = LOD.low
 ```
The first way is useful if you want to work in an interactive way, the second is 
more fitting for automated tasks.

## Want to set up your own workflow?
The pre implemented workflows hold the needed settings for the simulation with 
the pre implemented Plugins. For further customization you can add your own 
Workflow (from scratch or by inheriting from the existing ones) and add your own
settings that you might miss from the existing ones.
