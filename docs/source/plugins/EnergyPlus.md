(EnergyPlus)=
# PluginEnergyPlus

The Plugin EnergyPlus exports the preprocessed IFC data to en EnergyPlus 
Input file (idf). This Plugin contains EnergyPlus specific modifications of 
the geometry and further enrichment for the export. General simulation 
control settings are set here as well as the output variables.

## IFC Requirements
The PluginEnergyPlus should only be applied, if minimum IFC requirements are 
fulfilled:
* IFC-Version: IFC4
* Validity: The IFC file must be valid (fulfill all rules of its schema)
* Space Boundaries: IfcRelSpaceBoundary Instances should be included of type 
  2ndLevel (either IfcRelSpaceBoundary2ndLevel (optimum) or 
  IfcRelSpaceBoundary with Description 2ndLevel)
* Quality of Space Boundaries: The provided space boundary data must be 
  valid in terms of syntax, geometry and consistency (cf. Richter et al.: 
  'Validation of IFC-based Geometric Input for Building Energy Performance 
  Simulation', 2022 Building Performance Analysis Conference and SimBuild 
  co-organized by ASHRAE and IBPSA-USA, https://doi.org/10.26868/25746308.2022.C033)

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
  * [IfcValidation](ep_ifc_validation)
  * [EPGeomPreprocessing](ep_geom_preprocessing)
  * [AddSpaceBoundaries2B](AddSpaceBoundaries2B)
  * [WeatherEnergyPlus](WeatherEnergyPlus)
  * [CreateIdf](CreateIdf)
  * [IdfPostprocessing](IdfPostprocessing)
  * [ExportIdfForCfd](ExportIdfForCfd)
  * [RunEnergyPlusSimulation](RunEnergyPlusSimulation)


## EnergyPlus specific tasks

### Validation of the IFC file 
(ep_ifc_validation)=
[Go to IfcValidation](IfcValidation)

The EnergyPlus specific tasks start with an EnergyPlus specific validation 
of the space boundaries provided by the IFC file. This validation algorihtm 
is included in the default workflow to give an insight in the quality of the 
provided IFC.

### Geometric Preprocessing for EnergyPlus Export
(ep_geom_preprocessing)=
[Go to EPGeomPreprocessing](EPGeomPreprocessing)

The preprocessed geometry and material needs an additional preprocessing to 
cover all requirements for the EnergyPlus export. This is done in the 
[EPGeomPreprocessing](EPGeomPreprocessing). The space boundaries which are 
further used to model the building geometry are [added](add_bounds_to_instances) 
to the instances. Minor geometric displacements are fixed by 
[moving children to their parents](move_children_to_parents). This covers all 
cases, where opening space boundaries are displaced by the thickness of the wall.
The surface orientation is [fixed](fix_surface_orientation) if needed 
(all surface normals are supposed to point outwards the relating space). To
improve shading calculations and remove inner loops from surfaces, 
[non-convex space boundaries can be split up](split_non_convex_bounds). Similarly,
[shadings can be added and split if needed](add_and_split_bounds_for_shadings). 

Use the [settings](settings) to decide if boundaries should be split up and
if shadings should be added.


