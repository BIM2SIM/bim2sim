# Installation

## Base Library

As some requirements for core functionality of `bim2sim` are not available via
PyPi but only via Anaconda an installation only via PyPi is sadly not possible
for now.
For now the easiest way to install `bim2sim` is the following:

```
# create fresh python environment with conda 
conda create -n bim2sim python=3.9

# activate your environment
conda activate bim2sim

# clone bim2sim repository (you can also use SSH if you prefer)
git clone https://github.com/BIM2SIM/bim2sim.git
cd bim2sim

# go into main directory of the repo where setup.py is stored and run
python setup.py install

# afterwards install the packages which are installable via pip
conda install -c conda-forge pythonocc-core=7.6.2 -y
conda install -c conda-forge ifcopenshell -y
```

If all worked well you should be able to start using bim2sim. Try

`python bim2sim -h`

We will improve this process by our own anaconda image soon.

## Plugins

To use the Plugins you have to install the requirements of the corresponding
plugins. Therefore just go the Plugin folder you want to use under
`bim2sim/plugins/` and run

```
pip install -r requirements.txt
```

to see all available commands. For further reading see
[First Steps](First_steps).


## Docker

We already create docker images for each the base `bim2sim` tool as for every
Plugin, but currently these are only available through our own registry. You can
still build the images yourself based on the existing Dockerfiles. As our
current structure is a bit complicated, please have a look at the explanation of
the [Docker Structure](docker_structure).

We will release the images on DockerHub soon to make them accessible for
everyone (see [issuue 452](https://github.com/BIM2SIM/bim2sim/issues/452)). 