@echo on
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginAixLib
IF %ERRORLEVEL% NEQ 0 exit 1