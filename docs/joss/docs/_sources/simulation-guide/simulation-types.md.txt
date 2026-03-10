# Simulation Types
## Building Performance Simulation (BPS)
BPS dynamically computes a building's heating and cooling loads for a chosen
period. The simulation results are a base for the design of heating and cooling
systems. Even advanced renewable energy systems that require demand management
can be sized efficiently.
A building's internal and external thermal loads vary throughout the day. The
internal temperature changes are caused by the heat exchange with the
surroundings and the building's thermal mass.

To set up a BPS, one must balance the results' robustness and the workload. The
selected level of detail of the simulation must fit the problem.

### Reasons to perform a BPS

It is the current state of the art that a high manual modeling effort is
required to create a dynamic simulation model of a building. Therefore, thermal
simulation is often performed, if at all, only for a specific time in a later
planning phase, when only a few changes to the cubature are expected.
Alternatively, static calculation methods are used, which cannot represent the
dynamic loads in the building in detail.

The `bim2sim` tool aims to automate the IFC-based creation of thermal simulation
models to make BPS accessible for all IFC-based design processes, as the
designers can significantly influence the building's geometry in the early
design phases.
By linking the building simulation to the IFC model, cubature variants can be
simulated and evaluated without modeling effort.
The IFC-based setup of the building geometry lowers the barrier for the detailed
dynamic thermal analysis.
The considerable CO2 savings potential is to be expected through optimal
building orientation and optimization of thermal loads in an early planning
phase.

### Requirements for BPS in bim2sim
The BPS part in `bim2sim` requires a sufficient representation of the building.
This includes a description of:
* building geometry
* materials (the building's thermal mass)
* HVAC systems (only covered with ideal loads for now. Coupled simulations are in scope of future releases)
* internal loads (occupancy, equipment, lighting, schedules)
* external loads (weather)
* building's location and surroundings (shadings)

This information is extracted from the IFC file. Missing data can be added 
by using e.g. a template-based enrichment. 

(eplus_ifc_requ)=
### IFC Requirements
The BPS Plugins ([PluginEnergyPlus](PluginEnergyPlus) and 
[PluginTEASER](PluginTEASER)) should only be applied, 
if minimum IFC requirements are fulfilled:
* IFC-Version: IFC4
* Validity: The IFC file must be valid (fulfill all rules of its schema)
* Space Boundaries: IfcRelSpaceBoundary elements should be included of type 
  2ndLevel (either IfcRelSpaceBoundary2ndLevel (optimum) or 
  IfcRelSpaceBoundary with Description 2ndLevel)
* Quality of Space Boundaries: The provided space boundary data must be 
  valid in terms of syntax, geometry and consistency (cf. Richter et al.: 
  'Validation of IFC-based Geometric Input for Building Energy Performance 
  Simulation', 2022 Building Performance Analysis Conference and SimBuild 
  co-organized by ASHRAE and IBPSA-USA, https://doi.org/10.26868/25746308.2022.C033)
  
Other IFC requirements (optional, improve model accuracy):
* Material definitions
* Shading Space Boundaries (only applicable for [PluginEnergyPlus](PluginEnergyPlus))


## Heating Ventilation and Air Conditioning (HVAC) Simulation
HVAC simulations are used to simulate the behaviour of different system 
components in the energy system. For now `bim2sim` focuses on the heating and 
cooling generation, while ventilation and air conditioning is planned for the 
future (see issue 245 # TODO github deploy). 

The corresponding simulation models for heating and cooling analysis typically 
include:
* hydraulic network including pipes, valves and pumps
* generation devices for heating and cooling
* consumers
* control logic 

### Hydraulic Network 
(hydraulic_network)=
Since it is not convenient to model every pipe, pipe fitting and all components 
of the hydraulic network, one part of the creation of simulation models for 
heating and cooling analysis is the abstraction of the hydraulic network.
The abstraction can be quite time-consuming and error-prone, so one of the 
strengths of `bim2sim` is offering automated tasks for analysis and aggregation 
of the network. To do so we convert the imported meta structure 
[elements](elements_structure) and their connections into a [HvacGraph](HvacGraph) using 
[networkx](https://networkx.org/) python package.  
The possible aggregations start with quite simply aggregations like 
[PipeStrand](PipeStrand) to aggregate multiple straight connected pipes, but
also include more complex aggregations like [Underfloorheating](Underfloorheating)
which tries to identify underfloor-heating or concrete core activation as there is
no possibility in IFC to represent these directly. You can find an overview to
all aggregations in it the [corresponding documentation](concepts/aggregations.md). 
Generation devices and consumers are also simplified in aggregations which
brings us to the next group.


### Generation Devices & Consumers
Generation devices are e.g. boilers or chillers and consumers might be radiators 
or the already mentioned underfloor-heating. 




### Control Logic
Even if IFC offers the possibility to include controls, it is not very practical
and rarely used. But for a running simulation the control logic is 
indispensable. So we came up with a mix of two solutions:

1. For elements where common standard control logics exist we include these 
logics as default into the mapped Modelica models.  
We try to gather the relevant parameters for the control from the IFC via the [attribute](concepts/attribute.md) 
system. One example would be the flow set temperature of a boiler. If there is
no information in IFC we can either request them during export or mark them as
non-existing in the exported model, so the user can input them in Modelica.
2. For custom controls and complex controls which highly depend on the system
and the usage we offer the possibility to deactivate the internal controls inside
the modelica models and allow the user to model their own controls.

(simtype_cfd)=
## Computational Fluid Dynamics (CFD) Simulations

CFD simulations are used to analyze fluid flow, heat transfer, and indoor air 
distribution in buildings. Building Performance Simulation (BPS) focuses 
on overall energy balance and system sizing on a zonal scale for the whole 
building with a single node per zone and per surface. CFD on the other hand 
has provides much more detailed insights through a high-resolution spatial 
grid. This allows for an evaluation of local comfort parameters, such as air 
velocity, temperature stratification, and contaminant dispersion for a 
smaller subset of the building (e.g., a zone or room). With its help, 
designers can assess the indoor environmental quality (IEQ) beyond energy 
efficiency.

Typical applications of CFD in building design include:
* Evaluation of thermal comfort in different room setups
* Optimization of air diffusers
* Smoke and contaminant dispersion studies

### Reasons to Perform a CFD Simulation
CFD simulations require more computational resources than BPS but provide highly 
detailed results that cannot be captured with zonal or network-based airflow models. 
They are particularly useful for closer investigations of local thermal 
comfort, air flows and air quality.  

By linking CFD setup to IFC-based design workflows, bim2sim aims to reduce the
manual modeling effort. Automating the extraction of geometry and boundary 
conditions from the IFC model enables CFD simulations to be performed earlier 
in the design process and provides deeper insights.

### Requirements for CFD in bim2sim
CFD simulation, especially when set up with OpenFOAM, require a 
sufficiently detailed computational grid and extensive boundary conditions. 
These boundary conditions can be generated by the IFC-based workflows in 
bim2sim. Hence, to perform a CFD simulation within bim2sim, first a full 
EnergyPlus Simulation has to be performed. For a single airtight room, 
the required boundary conditions can then be extracted from the EnergyPlus 
results.

### IFC Requirements
Since the CFD simulations using OpenFOAM are heavily based on the 
EnergyPlus simulations, the IFC requirements are the same as the ones 
described [here](eplus_ifc_requ).

These requirements ensure that the geometry and boundary conditions extracted 
from IFC are consistent and suitable for meshing and CFD preprocessing.

### Literature Recommendations
CFD and especially OpenFOAM as a compute kernel are very complex topics 
which can not be explained in detail in this documentation. It is therefore 
recommended to take a closer look at some of the following further literature:
* **Basics of CFD**: Computational Methods for Fluid Dynamics, J. H. 
  Ferziger and M. Perić, 2002, doi: 10.1007/978-3-642-56026-2. 
* **OpenFOAM User Guides and Documentation**: https://www.openfoam.com/documentation/overview 
* **Background of the PluginOpenFOAM**: IFC-based analysis of present and 
  future thermal comfort using building energy performance simulation and 
  computational fluid dynamics, V. E. Richter, RWTH Aachen University 2025, 
  doi: [10.18154/RWTH-2025-05670](https://doi.org/10.18154/RWTH-2025-05670)