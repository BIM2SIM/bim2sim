#!/bin/bash
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginTEASER  &&
pip install -r bim2sim/plugins/PluginTEASER/dependency_requirements.txt