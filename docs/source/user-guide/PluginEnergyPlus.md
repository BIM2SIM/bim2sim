# PluginEnergyPlus
## How to install?

### Step by step

### Trouble Shooting
For python > 3.9: make sure that the correct geomeppy is installed (using requirements.txt in the plugin): in this fork of geomeppy, we fixed the imports working from python >= 3.10: https://github.com/BIM2SIM/geomeppy/tree/fix_dependencies

### Test install

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


#TODO
Copy to correct positions:

[Go to EnergyPlus specific tasks](EnergyPlus_specific_tasks)
[Go to EnergyPlusSimSettings](EnergyPlus_sim_settings)

The Plugin EnergyPlus exports the preprocessed IFC data to en EnergyPlus 
Input file (idf). This Plugin contains EnergyPlus specific modifications of 
the geometry and further enrichment for the export. General simulation 
control settings are set here as well as the output variables.


Other IFC requirements (optional, improve model accuracy):
* Material definitions
* Shading Space Boundaries

The Plugin consists of multiple individual tasks that are executed 
consecutively. The default tasks are defined in the PluginEnergyPlus class. 
These tasks can be split in two main blocks: general preparation tasks that 
are used for both BPS workflows (TEASER and EnergyPlus) and EnergyPlus 
specific tasks.

* general tasks (common and BPS-specific):
  * [LoadIFC](LoadIFC)
  * [CreateElements](CreateElements)
  * [CreateSpaceBoundaries](CreateSpaceBoundaries)
  * [Prepare](Prepare)
  * [BindStoreys](BindStoreys)
  * [EnrichUseConditions](EnrichUseConditions)
  * [Verification](Verification)
  * [EnrichMaterial](EnrichMaterial)
  * [DisaggregationCreation](DisaggregationCreation)
  * [BindThermalZones](BindThermalZones)
* EnergyPlus specific tasks:
  * [IfcValidation](ep_ifc_valid)
  * [EPGeomPreprocessing](ep_geom_preproc)
  * [AddSpaceBoundaries2B](ep_add_2b_sbs)
  * [WeatherEnergyPlus](ep_set_weather)
  * [CreateIdf](ep_create_idf_for_export)
  * [IdfPostprocessing](ep_postprocess)
  * [ExportIdfForCfd](ep_cfd_export)
  * [RunEnergyPlusSimulation](ep_run_sim)

(EnergyPlus_specific_tasks)=
## EnergyPlus specific tasks

### Validation of the IFC file 
(ep_ifc_valid)=
[Go to IfcValidation](IfcValidation)

The EnergyPlus specific tasks start with an EnergyPlus specific validation 
of the space boundaries provided by the IFC file. This validation algorihtm 
is included in the default workflow to give an insight in the quality of the 
provided IFC.

### Geometric Preprocessing for EnergyPlus Export
(ep_geom_preproc)=
[Go to EPGeomPreprocessing](EPGeomPreprocessing)

The preprocessed geometry and material needs an additional preprocessing to 
cover all requirements for the EnergyPlus export. This is done in the 
[EPGeomPreprocessing](EPGeomPreprocessing). The space boundaries which are 
further used to model the building geometry are [added](add_bounds_to_elements) 
to the elements. Minor geometric displacements are fixed by 
[moving children to their parents](move_children_to_parents). This covers all 
cases, where opening space boundaries are displaced by the thickness of the wall.
The surface orientation is [fixed](fix_surface_orientation) if needed 
(all surface normals are supposed to point outwards the relating space). To
improve shading calculations and remove inner loops from surfaces, 
[non-convex space boundaries can be split up](split_non_convex_bounds). Similarly,
[shadings can be added and split if needed](add_and_split_bounds_for_shadings). 

Use the [settings](settings) to decide if boundaries should be split up and
if shadings should be added.

### Add 2b Space Boundaries
(ep_add_2b_sbs)=
[Go to AddSpaceBoundaries2B](AddSpaceBoundaries2B)

Space Boundaries of type 2b can be added here if gaps are located in the 
provided set of space boundaries. The resulting set of space boundaries
then forms a watertight model that can be further used for other simulation
purposes such as [CFD export](ExportIdfForCfd).

### Set the Weather File
(ep_set_weather)=
[Go to WeatherEnergyPlus](WeatherEnergyPlus)

Set the Weather File for the EnergyPlus Simulation. 

### Initialize and Export the EnergyPlus IDF File 
(ep_create_idf_for_export)=
[Go to CreateIdf](CreateIdf)

Write all preprocessed geometric data, materials, and boundary conditions
to an EnergyPlus input file (IDF). 

### IDF Postprocessing
(ep_postprocess)=
[Go to IdfPostprocessing](IdfPostprocessing)

Export data to csv. Some modifications may be required to meet your 
individual postprocessing needs here. 

### Export IDF Geometry for CFD Processing
(ep_cfd_export)=
[Go to ExportIdfForCfd](ExportIdfForCfd)

Use the [settings](settings) to specify, if the IDF geometry should be
converted to .stl for further use in CFD applications. 

### Run EnergyPlus Simulation
(ep_run_sim)=
[Go to RunEnergyPlusSimulation](RunEnergyPlusSimulation)

Run the EnergyPlus simulation. Use the [settings](settings) for further
runtime specifications. 


## EnergyPlusSimSettings

EnergyPlus has its own set of EnergyPlus specific 
[Simulation Settings](simulation_setting) that can be found here:

[Go to EnergyPlusSimSettings](EnergyPlus_sim_settings)