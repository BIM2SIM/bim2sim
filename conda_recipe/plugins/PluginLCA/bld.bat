@echo on
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginLCA
IF %ERRORLEVEL% NEQ 0 exit 1