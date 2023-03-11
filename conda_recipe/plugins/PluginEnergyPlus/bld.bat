@echo on
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginEnergyPlus
pip install https://github.com/NREL/EnergyPlusRegressionTool/archive/refs/tags/v1.9.6.zip
IF %ERRORLEVEL% NEQ 0 exit 1