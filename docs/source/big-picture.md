# Big Picture

```{eval-rst}
.. toctree::
   :maxdepth: 2

```

## How does bim2sim work?
...


## Short description of the main concepts Workflow, Plugin and Project
To prevent confusion from the beginning:
* A [workflow](workflow_main) holds the relevant settings for each type of 
simulation.
* A [Plugin](plugin_main) is for a specific simulation environment/tool. 
E.g. [TEASER](TEASERManager) plugin and [EnergyPlus](EnergyPlus) plugin use the 
same workflow [BuildingSimulation](BuildingSimulation). It defines the default
tasks that will be executed during the project run.
* A project is the main object in `bim2sim` and brings workflow and plugin 
 together and allows to run the process of simulation model creation.

You find detailed information about each of the concepts in the corresponding 
documentation.