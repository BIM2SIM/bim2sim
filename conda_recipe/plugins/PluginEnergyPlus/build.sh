#!/bin/bash
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginEnergyPlus  &&
pip install https://files.pythonhosted.org/packages/07/ec/908ba180d78c2a0ba170879188877b7f5df75cae0fd2c0f090d7cd2b894c/geomeppy-0.11.8.tar.gz &&
pip install https://files.pythonhosted.org/packages/db/1f/94778fa817b016da933485c35bcd401b5766f0e3703b47e225667c411146/eppy-0.5.63.tar.gz &&
pip install -r bim2sim/plugins/PluginEnergyPlus/dependency_requirements.txt
