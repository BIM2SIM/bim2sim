# SimSettings to Markdown tables

In order to create proper documentation for a module containing a class of 
SimSettings, a script for automatically converting such a class to Markdown 
tables is provided in `bim2sim/utilities/settings_to_md.`.

To run the script, one can either provide the module name or the path to 
the file as well as the class name. After setting a path for the outputs, 
the Markdown tables are written to seperate files so that they can be 
copied to their respective location in the documentation (e.g. 
`bim2sim/docs/source/advanced-user-guide/concepts/sim_settings.md`).

Currently, it will generate files for the following settings:
* BaseSimSettings
* BuildingSimSettings
* EnergyPlusSimSettings
* PluginComfortSimSettings

Nevertheless, this script can be used for any other SimSetting class as well.