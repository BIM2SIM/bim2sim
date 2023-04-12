#!/bin/bash
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginEnergyPlus
pip install -r bim2sim/plugins/PluginEnergyPlus/requirements.txt
pip install -r bim2sim/plugins/PluginEnergyPlus/dependency_requirements.txt
