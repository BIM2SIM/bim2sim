@echo on
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginHKESim
pip install -r bim2sim/plugins/PluginHKESim/requirements.txt
pip install -r bim2sim/plugins/PluginHKESim/dependency_requirements.txt
IF %ERRORLEVEL% NEQ 0 exit 1