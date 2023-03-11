#!/bin/bash
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginTEASER
pip install  git+https://github.com/RWTH-EBC/TEASER@development
pip install git+https://github.com/DaJansenGit/BuildingsPy.git
