# PluginHKESim
## How to install?

### Step by step

### Test install

## Structure of the plugin

The following figure shows the structure of the HKESim plugin. Here you see which tasks are used and how they are combined.
<!--- 
the following code is pasted from the a file from /bim2sim/docs/source/img/dynamic/plugindiagram
this figure is generated by the function generate_plugin_structure_fig in file template_mermaid.py
-->

```{mermaid}
---
title: plugin HKESim
---
flowchart TB
    
subgraph taskLoadIFC["task LoadIFC"]
 subgraph "" 

  tLoadIFC["bim2sim > tasks > common >  
 LoadIFC"]
  extLoadIFC(" Load all IFC files from PROJECT. " )
 end

stateLoadIFC[("state
 (reads/touches)")]
    
tLoadIFC -- ifc_files --> stateLoadIFC

end
    
subgraph taskCheckIfc["task CheckIfc"]
 subgraph "" 

  tCheckIfc["bim2sim > tasks > common >  
 CheckIfc"]
  extCheckIfc("  Check an IFC file, for a number of conditions
(missing information, incorrect information, etc)
that could lead on future tasks to fatal errors. " )
 end

stateCheckIfc[("state
 (reads/touches)")]
    
stateCheckIfc -- ifc_files --> tCheckIfc
direction RL
end
    
subgraph taskCreateElements["task CreateElements"]
 subgraph "" 

  tCreateElements["bim2sim > tasks > common >  
 CreateElements"]
  extCreateElements(" Create bim2sim elements based on information in
IFC. " )
 end

stateCreateElements[("state
 (reads/touches)")]
    
stateCreateElements -- ifc_files --> tCreateElements

tCreateElements -- elements, ifc_files --> stateCreateElements

end
    
subgraph taskConnectElements["task ConnectElements"]
 subgraph "" 

  tConnectElements["bim2sim > tasks > hvac >  
 ConnectElements"]
  extConnectElements(" Analyses IFC, creates element elements and
connects them. " )
 end

stateConnectElements[("state
 (reads/touches)")]
    
stateConnectElements -- elements --> tConnectElements

tConnectElements -- elements --> stateConnectElements

end
    
subgraph taskMakeGraph["task MakeGraph"]
 subgraph "" 

  tMakeGraph["bim2sim > tasks > hvac >  
 MakeGraph"]
  extMakeGraph(" Instantiate HVACGraph. " )
 end

stateMakeGraph[("state
 (reads/touches)")]
    
stateMakeGraph -- elements --> tMakeGraph

tMakeGraph -- graph --> stateMakeGraph

end
    
subgraph taskExpansionTanks["task ExpansionTanks"]
 subgraph "" 

  tExpansionTanks["bim2sim > tasks > hvac >  
 ExpansionTanks"]
  extExpansionTanks(" Analyses graph network for expansion tanks and
removes them. " )
 end

stateExpansionTanks[("state
 (reads/touches)")]
    
stateExpansionTanks -- graph --> tExpansionTanks

tExpansionTanks -- graph --> stateExpansionTanks

end
    
subgraph taskReduce["task Reduce"]
 subgraph "" 

  tReduce["bim2sim > tasks > hvac >  
 Reduce"]
  extReduce(" Reduce number of elements by aggregation. " )
 end

stateReduce[("state
 (reads/touches)")]
    
stateReduce -- graph --> tReduce

tReduce -- graph --> stateReduce

end
    
subgraph taskDeadEnds["task DeadEnds"]
 subgraph "" 

  tDeadEnds["bim2sim > tasks > hvac >  
 DeadEnds"]
  extDeadEnds(" Analyses graph network for dead ends and removes
ports due to dead ends. " )
 end

stateDeadEnds[("state
 (reads/touches)")]
    
stateDeadEnds -- graph --> tDeadEnds

tDeadEnds -- graph --> stateDeadEnds

end
    
subgraph taskLoadLibrariesHKESim["task LoadLibrariesHKESim"]
 subgraph "" 

  tLoadLibrariesHKESim[" 
 LoadLibrariesHKESim"]
  extLoadLibrariesHKESim(" Load HKESim library for export. " )
 end

stateLoadLibrariesHKESim[("state
 (reads/touches)")]
    
tLoadLibrariesHKESim -- libraries --> stateLoadLibrariesHKESim

end
    
subgraph taskExport["task Export"]
 subgraph "" 

  tExport["bim2sim > tasks > hvac >  
 Export"]
  extExport(" Export to Dymola/Modelica. " )
 end

stateExport[("state
 (reads/touches)")]
    
stateExport -- libraries, graph --> tExport
direction RL
end
    taskLoadIFC --> taskCheckIfc 
taskCheckIfc --> taskCreateElements 
taskCreateElements --> taskConnectElements 
taskConnectElements --> taskMakeGraph 
taskMakeGraph --> taskExpansionTanks 
taskExpansionTanks --> taskReduce 
taskReduce --> taskDeadEnds 
taskDeadEnds --> taskLoadLibrariesHKESim 
taskLoadLibrariesHKESim --> taskExport 
```

This figure is generated by the function TODO XXX (insert the link to generate_plugin_structure_fig in file template_mermaid.py)

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