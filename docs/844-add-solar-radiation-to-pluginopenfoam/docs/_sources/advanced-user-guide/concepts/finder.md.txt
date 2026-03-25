# Finder
## What does the finder?
The abstract `finder` class has currently only one implementation, the 
[TemplateFinder](TemplateFinder). The TemplateFinder is used to find attributes
in the IFC which are not placed in an IFC schema specified way, but in a known 
way (Custom `IfcPropertySets`). E.g. it is known that ArchiCAD creates an
`IfcPropertySet` named `BaseQuantites`, with additional information. 
To get these information, we use templates in form of .json files, which store
potential data storage points in the IFC for widly used tools.
Currently we support templates for:
* Revit (BPS)
* ArchiCAD (BPS)
* CarF from LuArtX IT (HVAC)
* TRICAD MS (HVAC)

## I have my own tool, or I'm aware of more typical storage points, what to do?
Please feel free to enrich the existing templates. They are stored under 
`bim2sim/assets/finder`. Please take the following guidelines into account:
* every .json file needs to be named with "template_<name of tool>"
* every .json file should be structured the following way:

```json
{
  "Identification": {
    "tool_names": [<list of possible names>],
    "languages": [<list of languages>]
    
  },
  "<name of bim2sim instance>": {
	"default_ps": {
      "<name bim2sim attribute> 1" : ["<tool Pset name>", "<tool attribute name>"],
      "<name bim2sim attribute> 2" : ["<tool Pset name>", "<tool attribute name>"]
    }
  }
}

```
Explanation of the example:
* `list of possible names`: Here you should add the possible names that can 
will be stored in `IfcApplication: FullName` by the corresponding tool. You can 
also use %v and %lang for version and language if your tool changes the export 
name depending on version and language. The version must then be stored in
`IfcApplication: Version` to identify. See Revit template for an example.
* `languages`: possible languages like "DEU", "ENG" etc.
* `name of bim2sim instance`: have a look at the [elements](elements). We 
defined own names for our bim2sim elements as we have many-to-one as well as 
one-to-many mappings between IFC and simulation.
* `name bim2sim attribute`: you can find these in  [elements](elements) as well.
They are added as [attributes](attribute).
* `tool Pset name`: Name of the custom `IfcPropertySet` that the tool uses.
* `tool attribute name`: Name of the attribute of the custom `IfcPropertySet`


All templates will be validated against the correct json format on startup, so 
please stick to the .json guidelines. You can use a JSOn validator like [this one](https://jsonformatter.curiousconcept.com/).