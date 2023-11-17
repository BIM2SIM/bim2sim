# Project

## Functionality

The project class and its instance are the main starting point of every bim2sim
usage. The project is responsible for the following tasks and information:

* Create the local [FolderStructure](FolderStructure) if not existing
* Write the local config file if not existing
* Maintain (load and save) made decisions
* Run and finalize the project

In general there are two ways to basic ways to create a project.

1. Let `bim2sim` create your FolderStructure and base config, that you might
   overwrite later.
2. Create a [FolderStructure](FolderStructure) yourself including the IFC file,
   config file etc. and start the project based on this folder.

The first way would be the best as a starting point. If you want to change the
settings that the base config is created with you can do this by either
overwriting the settings (see [workflow](workflow_concept)) or using

```python
project.run(interactive=True)
```

This will open the config file after creation and allow you to make manual
changes. You can save it and close it afterwards and the process will continue. 
This is currently only working under Windows.

For further information please have a look at the code documentation of 
[project](project).
