# Heating Ventilation and Air Conditioning (HVAC) Simulation
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

## Hydraulic Network 
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


## Generation Devices & Consumers
Generation devices are e.g. boilers or chillers and consumers might be radiators 
or the already mentioned underfloor-heating. 




## Control Logic