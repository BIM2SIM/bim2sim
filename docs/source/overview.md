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
* A [workflow](workflow) holds the relevant settings for each type of 
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
user. This feedback is given through [Decisions](decisions).

You find detailed information about each of the concepts in the corresponding 
documentation.

## Building Performance Simulation (BPS)
...

## Heating Ventilation and Air Conditioning (HVAC) Simulation
HVAC simulations are used to simulate the behaviour of different system 
components in the energy system. For now `bim2sim` focuses on the heating and 
cooling generation, while ventilation and air conditioning is planned for the 
future. 

The corresponding simulation models for heating and cooling analysis typically 
include:
* hydraulic network including pipes, valves and pumps
* generation devices for heating and cooling
* consumers
* control logic 

### Hydraulic Network 
Since it is not expedient to model every pipe, pipe fitting and all components 
of the hydraulic network, one part of the creation of simulation models for 
heating and cooling analysis is the abstraction of the hydraulic network.

The abstraction can be quite time-consuming and error-prone, so one of the 
strengths of `bim2sim` is offering automated tasks for aggregation. This starts
with quite simply aggregations like [PipeStrand](PipeStrand) to aggregate 
multiple straight connected pipes, but also includes more complex aggregations 
like [Underfloorheating](Underfloorheating) which tries to identify 
underfloor-heating or concrete core activation as there is no possibility in IFC
to represent these directly. You can find an overview to all aggregations in it
the [corresponding documentation](aggregations). Generation devices and 
consumers are also simplified in aggregations which brings us to the next group.


### Generation Devices & Consumers
Generation devices are e.g. boilers or chillers and consumers might be radiators 
or the already mentioned underfloor-heating. 




### Control Logic
