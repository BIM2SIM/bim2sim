# Aggregations

## What are aggregations used for?

Aggregations try to reduce the number of elements that will be exported to
modelica in a way that the exported elements fit the existing modelica models.
For more information have a look at the docs for
[Hydraulic Network](hydraulic_network).

## How are they implemented?

...

### Find Matches

...

### Get Edge Ports

...

### Replace

...

### Merge graph

...

## Improvements

Currently, we follow a common guideline but the aggregations are still
very different in the way they are implemented. We want to improve this in the
feature to increase readability, modularity, maintainability and reusability.
If you want to help us, everything related is documented in issue #243. # TODO
GITHUB LINK

## What aggregations exist currently:

Currently, we implemented the following aggregations, please have a look at the
corresponding documentation for more details.

* [PipeStrand](PipeStrand)
* [AggregatedPipeFitting](AggregatedPipeFitting)
* [UnderfloorHeating](UnderfloorHeating)
* [ParallelPump](ParallelPump)
* [ParallelSpaceHeater](ParallelSpaceHeater)
* [Consumer](Consumer)
* [ConsumerHeatingDistributorModule](ConsumerHeatingDistributorModule)
* [AggregatedThermalZone](AggregatedThermalZone)
* [GeneratorOneFluid](GeneratorOneFluid)
