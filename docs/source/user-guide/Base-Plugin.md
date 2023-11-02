# Base(-Plugin)

In this chapter it will explained howto install the Base of the `bim2sim`
framework and first steps of the usage.

`bim2sim` is divided into a base library and plugins.
For further information of the specific plugins:

* [TEASER](user-guide/PluginTEASER)
* [EnergyPlus](user-guide/PluginEnergyPlus)
* [AixLib](user-guide/PluginAixLib)
* [HKESIM](user-guide/PluginHKESIM)
* [LCA](user-guide/PluginLCA)
* [CFD](user-guide/PluginCFD)

The base installation of the `bim2sim` framework includes a generic Base-Plugin.
The Base-Plugin is a plugin, which includes generic features and structure. This
plugin is used as general starting point without any third party dependencies.
So it is a good starting point for development of own plugins or as test
environment for debugging.

## How to install?

### Step by step
We will first guide you through the process how
to install `bim2sim` base library and afterwards how to install the plugins.
As some requirements for core functionality of `bim2sim` are not available via
PyPi but only via Anaconda an installation only via PyPi is sadly not possible
for now.
For now the easiest way to install `bim2sim` is the by

1. creating an anaconda environment
2. clone `bim2sim` GitHub repository
3. install pip requirements
4. install conda requirements
5. add base libraray and plugins to `PYTHONPATH`

We will guide you through the process now.
```shell
# create fresh python environment with conda 
conda create -n bim2sim python=3.9

# activate your environment
conda activate bim2sim

# clone bim2sim repository (you can also use SSH if you prefer)
git clone https://github.com/BIM2SIM/bim2sim.git
# change into bim2sim folder
cd bim2sim
# use of development branch is recommended, as main branch is currently not updated regulary
git checkout development


# install pip requirements
pip install -r requirements.txt

# install conda packages (OCC not available via pip)
conda install -c conda-forge pythonocc-core=7.7.0
```
After this we need to add bim2sim to the `PYTHONPATH` variable. For Windows, we 
recommend to use the graphical user interface, but you can also use the shell.
#### <span style="color:red">Important for Linux.</span>
Keep in mind that this change will only persist for the current session.
If you want to make it permanent, you can add the above line to your shell's 
configuration file (e.g., .bashrc or .bash_profile for Bash) so that it's 
executed every time you start a new shell session.
For Windows when you want to add multiple directorys to `PYTHONPATH` you need to
do it all in one command.

```shell
# Linux
export PYTHONPATH=$PYTHONPATH:<your_git_bim2sim_repo_path>
# Windows
setx PYTHONPATH %PYTHONPATH%;<your_git_bim2sim_repo_path>
```

### Test install
If all worked well you should be able to start using bim2sim. Try

`python bim2sim -h` and try out the [First Steps](First_steps).   

We will improve this process by our own anaconda image soon.

### Docker
We already create docker images for each the base `bim2sim` tool as for every
Plugin, but currently these are only available through our own registry. You can
still build the images yourself based on the existing Dockerfiles. As our
current structure is a bit complicated, please have a look at the explanation of
the [Docker Structure](docker_structure).

We will release the images on DockerHub soon to make them accessible for
everyone (see [issuue 452](https://github.com/BIM2SIM/bim2sim/issues/452)). 



## How to create a project?
You can either use bim2sim directly from console or include it in your scripts.

### Console

Start your favorite console and type

```
$ python bim2sim -h
```

to see all available commands.

Now it's time to create your first project with bim2sim.

```
$ python bim2sim project create path/to/project -s teaser
```

will create a new project folder at `path/to/project` and set it up for a
simulation with [TEASER](teaser) (see [](plugins) for more options).
Now open the newly created project folder and put the *.ifc file you wish to
process into the subfolder `ifc`. Alternatively you could add the
option `-i path/to/ifc` to the command above, which would copy the ifc for you.

If all is set up correctly, run

```
$ python bim2sim load path/to/project
```

to load and run an existing project. Then follow the instructions from your
console. When you are done, you can inspect the results from the `/results` folder of
your project.

### Script

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

## Examples

Please have also a look at `bim2sim/examples` which provide you some runnable
examples for PluginTEASER, PluginEnergyPlus and PluginLCA.


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
