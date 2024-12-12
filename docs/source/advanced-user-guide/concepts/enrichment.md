# Enrichment

bim2sim uses the extensive statistic data in TEASER to enrich the often unknown
but required information for construction elements materials, their layered
structure and profiles to estimate internal loads in a building based on the
usage type of its zones. This enrichment was brought into bim2sim to make it not
only available to [PluginTEASER](PluginTEASER.md) but also to [PluginEnergyPlus](EnergyPlus.md)

## Use Conditions
We enrich Use Condition data based on DIN V EN 18599-10 (2018-09) and SIA 2024 (2015-10). 
The data in UseConditions.json is a mixture of these two standards as some values are only in one of them and some values seem more reliable in one of them.
The data is copied from [TEASER](https://github.com/RWTH-EBC/TEASER/tree/main/teaser/data/input/inputdata) and adjusted in some points 
(e.g. `typical_length`and `typical_width` are currently not required for bim2sim). 

You can also use your own UseConditions data, by using the `sim_settings` `prj_use_conditions` and `prj_custom_usages`. For more information we refer to the description of these `sim_settings`.

## Material and layer enrichment
As layerset and material data is nearly always missing, we offer the task `EnrichMaterial` to enrich layer and material data by templates based on Tabula and IWU data and data we re-engineered using [Ubakus](https://www.ubakus.de/u-wert-rechner/) based on requirements from EnEV, KFW and other building requirement standards. 
The used templates and data is copied from [TEASER](https://github.com/RWTH-EBC/TEASER/tree/main/teaser/data/input/inputdata). You can currently deactivate the enrichment by not using the `EnrichMaterial` task.

