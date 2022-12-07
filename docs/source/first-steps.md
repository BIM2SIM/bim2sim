(First_steps)=
# First steps

You can either use bim2sim directly from console or include it in your scripts.

## Console
Start your favorite console and type
```
$ python bim2sim -h
```
to see all available commands.

Now it's time to create your first project with bim2sim.
```
$ python bim2sim project create path/to/project -s teaser
```
will create a new project folder at `path/to/project` and set it up for a simulation with [TEASER](teaser) (see [](plugins) for more options). 
Now open the newly created project folder and put the *.ifc file you wish to process into the subfolder `ifc`. Alternatively you could add the option `-i path/to/ifc` to the command above, which would copy the ifc for you.

If all is set up correctly, run
```
$ python bim2sim load path/to/project
```
to load and run an existing project. Then follow the instructions from your console.
When you are done, you can inspect the results from the `/results` folder of your project.


## Script

To include bim2sim in your scripts start with something like this:
```python
from bim2sim import Project
from bim2sim.log import default_logging_setup

default_logging_setup()  # call this first or do a custom logging setup

project_path = 'path/to/project'
ifc_path = 'path/to/ifc'

if Project.is_project_folder(project_path):
    # load project if existing
    project = Project(project_path)
else:
    # else create a new one
    project = Project.create(project_path, ifc_path, 'teaser')
```
now you have multiple options to run the project and handle it's decisions:
```python
# Option 1: handle decisions manually
for bunch in project.run():
    for decision in bunch:
        print(decision.question)
        decision.value = 42  # your logic goes here

# Option 2: handle decisions via console input
from bim2sim import run_project, ConsoleDecisionHandler
run_project(project, ConsoleDecisionHandler())

# Option 3: write your own DecisionHandler and use it as in Option 2
```
Details about [DecisionHandlers](DecisionHandler). 