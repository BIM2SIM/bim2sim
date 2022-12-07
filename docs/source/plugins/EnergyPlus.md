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
  * common.LoadIFC
  * common.CreateElements
  * bps.CreateSpaceBoundaries
  * bps.Prepare
  * common.BindStoreys
  * bps.EnrichUseConditions
  * bps.Verification
  * bps.EnrichMaterial
  * bps.DisaggregationCreation
  * bps.BindThermalZones
* EnergyPlus specific tasks:
  * IfcValidation
  * EPGeomPreprocessing
  * AddSpaceBoundaries2B
  * WeatherEnergyPlus
  * CreateIdf
  * IdfPostprocessing
  * ExportIdfForCfd
  * RunEnergyPlusSimulation


## EnergyPlus specific tasks

The EnergyPlus specific tasks start with an EnergyPlus specific validation 
of the space boundaries provided by the IFC file. 