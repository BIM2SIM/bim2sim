# PluginTEASER
The [TEASER Plugin](PluginTEASER) is one the two currently implemented
[Plugins](Plugin) for building performance simulation (BPS). It uses the open
source tool [TEASER](https://github.com/RWTH-EBC/TEASER) as backend to export
Modelica simulation models based on the input IFC data. For a detailed insight
how TEASER works please have a look at the [documentation](http://rwth-ebc.github.io/TEASER/)
of TEASER. The exported simulation models can be simulated using the open source
library [AixLib](https://github.com/RWTH-EBC/AixLib). Following you will find 
some information how TEASER addresses the challenges of automated building 
simulation.

## How to install?

### Step by step
If you want to install the plugins as well, you need to install each Plugin requirements and 
add each folder of the Plugins to `PYTHONPATH`variable as well.
Example for `PluginTEASER`: you need to the following
```shell
# change directory to PluginTEASER folder
cd <your_git_bim2sim_repo_path>/plugins/PluginTEASER

# install requirements for TEASER
pip install -r requirements.txt

# add to `PYTHONPATH` environment variable (see above information)
export PYTHONPATH=$PYTHONPATH:<your_git_bim2sim_repo_path>\bim2sim\plugins\PluginTEASER
# Windows (when using the same shell as above, you need to add bim2sim main folder
# again, as `PYTHONPATH` variable is not updated during the session.
setx PYTHONPATH "%PYTHONPATH%;<your_git_bim2sim_repo_path>;<your_git_bim2sim_repo_path>\bim2sim\plugins\PluginTEASER"
```


### Test install

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




@TODO Move the following where it belongs
## Enrichment

bim2sim uses the extensive statistic data in TEASER to enrich the often unknown
but required information for construction elements materials, their layered
structure and profiles to estimate internal loads in a building based on the
usage type of its zones. This enrichment was made also available for the export
to the [EnergyPlus Plugin](EnergyPlus.md)

## Space Boundary Usage

Currently, TEASER prefers the semantic input from IFC data to get important data
like the area of walls. But as these information often are not correct or not
existing TEASER uses also the information provided by space boundaries. The
space boundaries are also mandatory for Zoning, see below. With growing quality
of IFC exports in authoring tools we might see complete IFCs with all semantic
information needed to parametrize a BPS. At this point TEASEr will allow
the creation of a single zone simulation model without the need of Space
Boundaries, as the space boundaries are only needed for zoning in this case.

## Zoning

As TEASERs simulation core offers multizone simulation models, but each zone is
adiabatic and interacts only with the environment but the zones don't interact
with each other. Even if just putting every room into one thermalzone might be
easy but not sensible as shown
in [this paper](https://doi.org/10.3384/ecp21181665).

As the zoning of simulation models is a time-consuming task we decided to
automate it with the task (BindThermalZones)[BindThermalZones].
We do this by giving the user multiple criteria to select from:

* External/Internal
* Orientation
* Usage
* Window to wall ratio

To create those zones we first need to [disaggregate](Disaggregations) the
elements
of each room based on 2nd level space boundaries and put them together again
afterwards.

### External/Internal

By selecting this criteria all zones with contact to the environment will
be in one group and all rooms without contact in the other.

### Orientation

This groups the zones into two groups, south-west orientated and
north-east orientated zones. This is useful as the south-west group is
exposed to solar radiation at a high level, while the north-east group will have
only negligible solar radiation input. Mixing both groups together can lead to
misleading results regarding peak loads as loads are smoothed out.

### Usage

This groups the zones based on the usage type of each room. bim2sim tries to
estimate the usage of each room based on the name of the room and multiple IFC
properties which might be set by the authoring tool. If the usage can't be found
a [Decision](Decisions) will be triggered to get the correct usage.

### Window to wall ratio

With this criteria the zones are grouped into 4 groups based on their window to
wall ratio or glass percentage:

* 0 - 30 %
* 30 - 50 %
* 50 - 70 %
* 70 - 100 %
This is useful as rooms with high glass percentage will have less thermal mass
and inertia and higher solar radiation input which makes their dynamic
different from the ones with low glass percentage.