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
```{mermaid}
flowchart LR
  subgraph Project
  direction LR
    subgraph Inputs
    direction LR
    IFC
    Workflow
    Plugin
    end
    subgraph Playground
    direction TB
        task1[Task 1] --> Task2[Task 2] --> Taskn[Task n]
        
        
    end
    Results
  end
User

  User --> Inputs
  Playground <--> |decisions| User
  Results --> User
  Playground --> Results
  Inputs --> Playground
  
```
Let's define what each of these elements is and how they work together.

**Project:**
A project is the main object in `bim2sim` and brings workflow and plugin 
together and allows to run the process of simulation model creation.

**Inputs:**
* A [workflow](concepts/workflow.md) holds the relevant settings for each type of 
simulation.
* A [Plugin](plugins) is for a specific simulation environment/tool.
* IFC is the IFC file that you want to use as a source.
E.g. [TEASER](TEASERManager) plugin and [EnergyPlus](EnergyPlus) plugin use the 
same base workflow [BuildingSimulation](BuildingSimulation). It defines the 
default tasks that will be executed during the project run.
 
**Playground:**
* The [Playground](Playground) itself deals as a manager which coordinates the 
different tasks.
* A [Task](Tasks) is used to fulfill one specific part of the whole process. One
task is for example the loading process of the IFC into the tool.

**User:**
To overcome the already mentioned challenges regarding the mixed quality of 
IFC-files the process might need feedback and additional information from the 
user. This feedback is given through [Decisions](concepts/decisions.md).

You find detailed information about each of the concepts in the corresponding 
documentation.

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
* HVAC systems
* internal loads (occupancy, equipment, lighting, schedules)
* external loads (weather)
* building's location and surroundings (shadings)

This information is extracted from the IFC file. Missing data can be added 
by using a set of templates. 

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
all aggregations in it the [corresponding documentation](concepts/aggregations.md). 
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
We try to gather the relevant parameters for the control from the IFC via the [attribute](concepts/attribute.md) 
system. One example would be the flow set temperature of a boiler. If there is
no information in IFC we can either request them during export or mark them as
non-existing in the exported model, so the user can input them in Modelica.
2. For custom controls and complex controls which highly depend on the system
and the usage we offer the possibility to deactivate the internal controls inside
the modelica models and allow the user to model their own controls.
