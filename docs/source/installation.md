# Installation

## Base Library
`bim2sim` is divided into a base library  and plugins. For Further information 
we refer to [plugins](plugins). We will first guide you through the process how
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

## Plugins
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


[//]: # (### Outdated )

[//]: # (```)

[//]: # (# create fresh python environment with conda )

[//]: # (conda create -n bim2sim python=3.9)

[//]: # ()
[//]: # (# activate your environment)

[//]: # (conda activate bim2sim)

[//]: # ()
[//]: # (# clone bim2sim repository &#40;you can also use SSH if you prefer&#41;)

[//]: # (git clone https://github.com/BIM2SIM/bim2sim.git)

[//]: # (cd bim2sim)

[//]: # ()
[//]: # (# go into main directory of the repo where setup.py is stored and run)

[//]: # (python setup.py install)

[//]: # ()
[//]: # (# afterwards install the packages which are installable via pip)

[//]: # (conda install -c conda-forge pythonocc-core=7.6.2 -y)

[//]: # (conda install -c conda-forge ifcopenshell -y)

[//]: # (```)

If all worked well you should be able to start using bim2sim. Try

`python bim2sim -h` and try out the [First Steps](First_steps).   

We will improve this process by our own anaconda image soon.

## Docker

We already create docker images for each the base `bim2sim` tool as for every
Plugin, but currently these are only available through our own registry. You can
still build the images yourself based on the existing Dockerfiles. As our
current structure is a bit complicated, please have a look at the explanation of
the [Docker Structure](docker_structure).

We will release the images on DockerHub soon to make them accessible for
everyone (see [issuue 452](https://github.com/BIM2SIM/bim2sim/issues/452)). 
