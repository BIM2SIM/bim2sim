@echo on
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginEnergyPlus
pip install https://files.pythonhosted.org/packages/07/ec/908ba180d78c2a0ba170879188877b7f5df75cae0fd2c0f090d7cd2b894c/geomeppy-0.11.8.tar.gz
pip install https://github.com/NREL/EnergyPlusRegressionTool/archive/refs/tags/v1.9.6.zip
IF %ERRORLEVEL% NEQ 0 exit 1