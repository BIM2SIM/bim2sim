# Aggregations

## What are aggregations used for?

Aggregations try to reduce the number of elements that will be exported to
modelica in a way that the exported elements fit the existing modelica models.
For more information have a look at the docs for
[Hydraulic Network](hydraulic_network). You can select which aggregations you
want to apply in the [workflow_settings_concept](workflow settings). The
selected aggregations are called inside the [Reduce](Reduce) task.

## How are aggregations implemented?

Aggregations are created based the [HvacGraph](HvacGraph) of the hydraulic
network. The basic concept is that we are looking for elements which fit the
corresponding aggregation [Find Matches](find_matches).

### Find Matches

(find_matches_aggr)=
The `find_matches` method is used to identify the corresponding aggregation
inside the given [HvacGraph](HvacGraph). It returns a subgraph that holds only
the elements that are part of the aggregation.

### Get Edge Ports

(get_edge_ports_aggr)=
The `get_edge_ports` method returns the "most outer ports" of the aggregation.
These are the ports that are connection the subgraph of the aggregation with the
rest of the [HvacGraph](HvacGraph).

### Replacement

(replacement_aggr)=
The `get_replacement_mapping` method creates a mapping dict that holds the
information which ports in the [HvacGraph](HvacGraph) should be deleted and
which ones should be replaced by the new ports of the aggregation.

### Merge graph

Finaly the `merge` method of the [HvacGraph](HvacGraph) is called and uses the
found matches in form of the subgraphs from `find_matches` and the mapping table
from `get_replacement_mapping` to adjust the input the aggregation into
the [HvacGraph](HvacGraph).


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
