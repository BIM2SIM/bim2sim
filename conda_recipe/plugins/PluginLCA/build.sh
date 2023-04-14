#!/bin/bash
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginLCA  &&
pip install -r bim2sim/plugins/PluginLCA/requirements.txt  &&
pip install -r bim2sim/plugins/PluginLCA/dependency_requirements.txt
