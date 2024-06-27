# PluginComfort
The PluginComfort builds upon the [PluginEnergyPlus](PluginEnergyPlus) and 
adds data sets for clothing and activity degrees, as well as the implementation 
of ISO 7730 / Fanger, EN 15251 (outdated), EN 16798-1, and ASHRAE 55 
evaluation. 

The implementation of the plugin was also presented in [Richter et al. (2023)
](https://www.mdpi.com/2076-3417/13/22/12478).

## How to install?
Please follow the installation instructions of the [PluginEnergyPlus
](PluginEnergyPlus). 

### Step by step

### Trouble Shooting
For python > 3.9: make sure that the correct geomeppy is installed (using requirements.txt in the plugin): in this fork of geomeppy, we fixed the imports working from python >= 3.10: https://github.com/BIM2SIM/geomeppy/tree/fix_dependencies

### Test install


## Structure of the plugin

The structure of the plugin extends the structure of the [PluginEnergyPlus
](PluginEnergyPlus). After the general bim2sim BPS preprocessing, the 
general EnergyPlus setup (IDF setup) is followed by the [ComfortSettings
](comf_comfort_settings) and the IDF is updated. Once the EnergyPlus 
simulation is executed, the setup of the dataframe for result evaluation ([CreateResultDF](comf_result_df))
follows, as well of the plotting of the results ([PlotComfortResults]
(comf_plot_results)).

PluginComfort specific tasks:
  * [ComfortSettings](comf_comfort_settings)
  * [CreateResultDF](comf_result_df)
  * [PlotComfortResults](comf_plot_results)

(comfort_specific_tasks)=
## Comfort specific tasks

### Add Comfort Settings
(comf_comfort_settings)=
[Go to ComfortSettings](ComfortSettings)

As this plugin for thermal comfort application bases on the [PluginEnergyPlus
](PluginEnergyPlus), the comfort settings extend and update the already 
available settings of the PluginEnergyPlus. The extensions and updates 
mostly focus on the personal data of occupants, such as clothing and 
activity degrees. This task starts with the definition of schedules for 
clothing, air velocities and work efficiency. It further assigns clothing 
parameters which have been imported from comfort-extended templates based on 
the TEASER use conditions. This task also sets the evaluation algorithms for 
thermal comfort evaluation, which are by default ISO 7730 / Fanger, EN 15251 
(outdated), and ASHRAE 55. As EN 15251 is outdated but EnergyPlus does not 
yet provide comfort analysis according to the EN 16798-1, the results of the 
EN 16798-1 are calculated in the postprocessing of the plugin.

After setting up the comfort parameters for the occupants, the output 
variables for comfort analysis are set. In a last step, the resulting 
EnergyPlus input file (IDF) is cleaned from possible duplicate names and zone 
references, which increases the robustness of the EnergyPlus simulation. 

### Create result dataframe for comfort analysis
(comf_result_df)=
[Go to CreateResultDF](CreateResultDF)
This task creates a result dataframe in the same structure as the other 
plugins. 


### Plot comfort results
(comf_plot_results)=
[Go to PlotComfortResults](PlotComfortResults)
This task provides methods to visualize the thermal comfort results. The 
following plots are available:

  * Calendar Plot for daily PMV results per zone
  * EN 16798-1 scatter plots
  * combined table and bar plots for EN 16798-1 evaluation

More plots are to be added to the plugin. However, all plots can also be 
generated from the EnergyPlus output csv file, using the tool of your choice 
(Python/matplotlib, MS Excel, ...).


## How to create a project?

## How to load an IFC file?

## How to configure my project?

### Simulation settings

### Configuration file

### Default tasks

### Additional templates

## How to run the project?

## How to run the simulation?

## How to analyze the project?

### What kind of results exist?

### What programs/tools to use for further analysis?
