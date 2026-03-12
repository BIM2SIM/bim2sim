# Writing your own bim2sim Plugin

A `bim2sim` [Plugin](Plugin) extends the base functionality of the library to solve specific problems.

## Basics
A Plugin is little more than a collection of `Task`s. Let's have a look:

```python
from bim2sim.plugins import Plugin
from bim2sim.task.base import ITask
from bim2sim.task.common import LoadIFC

class DoGreatThings(ITask):
    reads = ('ifc', )
    
    def run(self, workflow, ifc):
        # do really great things here
        pass

    
class MySamplePlugin(Plugin):
    name = "My sample Plugin"
    default_workflow = some_workflow
    tasks = {DoGreatThings}
    default_tasks = [LoadIFC, DoGreatThings]
```

What happens here? First we create a custom Task `DoGreatThings`. It is just a
dummy here. See [here](tasks) for details on [Tasks](ITask)
It is not even required for a Plugin to have custom `Task`s, but it's what you
usually want to do.
Next we have the class `MySamplePlugin` with a `name` for nicer reading and
a `default_workflow`, which probably gets obsolete soon.
Next we have `tasks` and `default_tasks`. `tasks` will be used for
interactive `project` runs and just provides all `Tasks` made available by this
Plugin.
`default_tasks` is used for static `Project` runs, which is the default by now.
It is a static list of all `Task`s which should be executed to fulfill
the `Plugin`s purpose.

In this example the purpose of the plugin is to load an ifc file and then "do
great things" to it.


## Use a custom Plugin

Now that we have a `Plugin`, how can we actually use it?

### Let `bim2sim` find your Plugin

The preferred way is to set up your plugin in way it can be auto-detected
by `bim2sim`.

1. Create a package (or module) named `bim2sim_<plugin_name>`. (
   Replace `<plugin_name>` with an actual name like `mysampleplugin`)
1. Make your `Plugin` available at top level of your package. Class definition
   or import are both fine.
   > NOTE:
   > If you have more than one `Plugin` on top level only the first one is
   detected.
1. Put your package somewhere Python can find it. This can e.g. be done by
   adding it to `PYTHONPATH` or installing your package.

Now you can run `bim2sim` as usual und use your `<plugin_name>` as any other
Plugin.

### Use in script

Alternatively you can use your `Plugin` directly from within your script.

```python
from bim2sim import Project, run_project, ConsoleDecisionHandler

project = Project.create(plugin=MySamplePlugin)
run_project(project, ConsoleDecisionHandler())
```
## Start with PluginTemplate

A good starting point is the PluginTemplate, which is included in the bim2sim
repo. Following the general steps creating a new plugin are described:

1. generate a new project including your new plugin / task
   1. start from the PluginTemplate
      1. copy the folder PluginTemplate (rename it) (../bim2sim/bim2sim/plugins/)
      2. copy example project e1_template_plugin.py (../bim2sim/bim2sim/examples/)
      3. adapt relevant links, imports and so on
         1. also rename the plugin folders, otherwise it is not callable in
           Project.create()
   2. always run the example to check our adaptions
2. write tests also/especially for development
   1. there is a testTask
      1. maybe needed to have access to specific variables
      2. bim2sim/test/unit/tasks/\_\_init\_\_.py > class TestTask
