# Big Picture
## What is bim2sim about?
`bim2sim` is a Python tool that allows to use BIM models (in the form of 
IFC files) as source to generate simulation models in a semi-automated process.
The existing version supports the following domains, where the focus of the 
development was on the first two: 
* **Heating, Ventilation Air-conditioning (HVAC)**
* **Building Performance Simulation (BPS)**
* **Computational Fluid Dynamics (CFD)**

The biggest challenge for this process is the mixed quality of IFC files. IFC as
standard theoretically offers the options to hold most of the information needed
for a simulation model generation. Nonetheless, even most current IFC files are
lacking detailed information about e.g. wall constructions or the relevant 
characteristics of HVAC equipment. 

This makes the process of a semi-automated
generation of simulation models quite complex. With `bim2sim` we provide a tool
that offers a lot of functionalities to simplify and unify this process.


## How does bim2sim work?
The general structure of bim2sim is shown below:


(Hint: firefox has issue display mermaid figures completely, for more infos see
issue [#766](https://github.com/BIM2SIM/bim2sim/issues/766))

```{mermaid}
flowchart TB

    subgraph PL["`**Plugin**`"]
        default_tasks
        sim_settings
    end
        PL-.->|input| PJ(Project)
    subgraph IP["`**Configuration**`"]
        X[ifc_paths] 
        Y[project directory]

        style X text-align:left
    end 
    IP -.->|input| PJ
    subgraph PJ["`**Project**`"]
    rd("run_default(): \n&nbsp&nbsp for task in plugin.default_tasks:\n&nbsp&nbsp&nbsp&nbsp      playground.run_task()")
    style rd text-align:left
    end 


    subgraph PG["`**Playground**`"]
        C["run_task ()"]
        S[(state)]
    end 
        rd --> C
    C -->|run| D{{Task 1}}
    D <-.-> |data exchange| S
    C -->|run| E{{Task 2}}  
    E <-.-> |data exchange| S
    C -->|run| F{{Task n}}
    F <-.-> |data exchange| S
    D-->E-->F
    S --> |load data|R
    F --> R(Task Export)

    User <---> |decisions| rd
```
Let's define what each of these elements is and how they work together in short
wrap up. For more detailed information please have a look at the detailed 
linked documentation of the components.

**Project:**
A project is the main object in `bim2sim`. It takes the selected 
[Plugin](advanced-user-guide/concepts/plugins.md) and further configuration as
input and then performs the [tasks](advanced-user-guide/concepts/tasks.md)
configured in the Plugin through the
[Playground](advanced-user-guide/concepts/playground.md). 

**Plugin:**
[Plugin](advanced-user-guide/concepts/plugins.md) are simulation use case and
sometimes even simulation tool specific. E.g. one plugin we provide is the
`PluginTEASER` that creates simulation models for building energy performance 
simulation through the tool TEASER and the modeling language Modelica. A plugin
takes two information: the `default_tasks` which is a list that describes what 
[tasks](advanced-user-guide/concepts/tasks.md) should be performed and the
[tasks](advanced-user-guide/concepts/sim_settings.md) which allow detailed 
configuration of the model creation that have default values but can be 
defined for every project. 

**Configuration**
Next to the Plugin the Project needs the object `ifc_paths` which is a 
dictionary where the key is a
[domain](advanced-user-guide/concepts/domains.md) and the value is the path to 
the IFC file. This allows to assign multiple IFCs to a project, e.g. one for 
HVAC domain and one for architecture domain. Additionally, a project directory 
needs to assigned. This can either be an empty path where a project should be 
created or an existing project directory.
 
**Playground:**
The [Playground](advanced-user-guide/concepts/playground.md) itself deals as a manager which coordinates the 
different [tasks](advanced-user-guide/concepts/tasks.md). * A task is used to
fulfill one specific part of the whole process. One task is for example the 
loading process of the IFC into the bim2sim tool. The results of each task will
be stored in the `state` of the 
[Playground](advanced-user-guide/concepts/playground.md). Every task might have
requirements (`reads`) and outputs (`touches`). The Playground checks for every
task if the requirements are met and then performs the task. Some tasks, like 
model creation tasks might also export information in form of files. Those will
be stored in the export folder of the project directory.

**User:**
To overcome the already mentioned challenges regarding the mixed quality of 
IFC-files the process might need feedback and additional information from the 
user. This feedback is given through [Decisions](advanced-user-guide/concepts/decisions.md).

You find detailed information about each of the concepts in the corresponding 
documentation.

#TODO this is copied to advanced-user-guide/simulation-types, strip it down here
## Simulation Types
### Building Performance Simulation (BPS)
BPS dynamically computes a building's heating and cooling loads for a chosen
period. The simulation results are a base for the design of heating and cooling
systems. Even advanced renewable energy systems that require demand management
can be sized efficiently.
A building's internal and external thermal loads vary throughout the day. The
internal temperature changes are caused by the heat exchange with the
surroundings and the building's thermal mass.

To set up a BPS, one must balance the results' robustness and the workload. The
selected level of detail of the simulation must fit the problem.

#### Reasons to perform a BPS

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

#### Requirements for BPS in bim2sim
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

#### IFC Requirements
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


### Heating Ventilation and Air Conditioning (HVAC) Simulation
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

#### Hydraulic Network 
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
all aggregations in it the [corresponding documentation](advanced-user-guide/concepts/aggregations.md). 
Generation devices and consumers are also simplified in aggregations which
brings us to the next group.


#### Generation Devices & Consumers
Generation devices are e.g. boilers or chillers and consumers might be radiators 
or the already mentioned underfloor-heating. 


#### Control Logic
Even if IFC offers the possibility to include controls, it is not very practical
and rarely used. But for a running simulation the control logic is 
indispensable. So we came up with a mix of two solutions:

1. For elements where common standard control logics exist we include these 
logics as default into the mapped Modelica models.  
We try to gather the relevant parameters for the control from the IFC via the [attribute](advanced-user-guide/concepts/attribute.md) 
system. One example would be the flow set temperature of a boiler. If there is
no information in IFC we can either request them during export or mark them as
non-existing in the exported model, so the user can input them in Modelica.
2. For custom controls and complex controls which highly depend on the system
and the usage we offer the possibility to deactivate the internal controls inside
the modelica models and allow the user to model their own controls.


### Computational Fluid Dynamics (CFD) Simulations

CFD simulations are used to analyze fluid flow, heat transfer, and indoor air 
distribution in buildings. While Building Performance Simulation (BPS) focuses 
on overall energy balance and system sizing, CFD provides detailed insights 
into local comfort parameters, such as air velocity, temperature stratification, 
and contaminant dispersion. This allows designers to assess the indoor 
environmental quality (IEQ) beyond energy efficiency.

Typical applications of CFD in building design include:
* Evaluation of thermal comfort in different room setups
* Optimization of air diffusers
* Smoke and contaminant dispersion studies

For more information on CFD simulations please take a look at the 
[Simulation Types](simtype_cfd).


## What are Plugins?
(plugin_overview)=
To make `bim2sim` usable for different simulation domains and tools we use
Plugins that are built upon the functionality that `bim2sim` offers. These
plugins put together one or multiple [Tasks](tasks) and a use a
[set of simulation settings](sim_settings) to create a simulation model 
based on an IFC.
Not all plugins are at the same level of development. Following, we give an
overview about the current development process and what works and what notin the
following table.

| **Plugin** | **Domain** | **Model Generation** | **Comment**                      | **Export** | **Comment**                    | **Simulation** | **Comment**                       |
|------------|------------|----------------------|----------------------------------|------------|--------------------------------|----------------|-----------------------------------|
| AixLib     | HVAC       | Working              | improvements aggregations needed | Working    |                                | Not working    | Modelica models not published yet |
| EnergyPlus | BPS        | Working              |                                  | Working    |                                |                |                                   |
| TEASER     | BPS        | Working              |                                  | Working    |                                |                |                                   |
| LCA        | LCA        | -                    | no model                         | Working    | improvements IfcWindows needed | -              | no simulation                     |
| CFD        | CFD        | -                    | no model                         | Working    | documentation missing          | -              | no simulation                     |
| OpenFOAM   | CFD        | -                    | no model                         | Working    |                                | Working        | must be run externally            |

## Compatibility
For the Plugins that export a simulation model, following the listed compatible 
versions and branches are listed, which our Plugins are compatible with at the
moment.

| **Plugin**     | **Repository** | **version/branch** |
|----------------|----------------|--------------------|
| **TEASER**     | AixLib         | `development`      |
|                | TEASER         | `development`      |
| **EnergyPlus** | EnergyPlus     | `9.4.0`            |
| **OpenFOAM**   | OpenFOAM       | `v2206`            |m


