@echo on
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginCFD
pip install -r bim2sim/plugins/PluginCFD/requirements.txt
pip install -r bim2sim/plugins/PluginCFD/dependency_requirements.txt
IF %ERRORLEVEL% NEQ 0 exit 1