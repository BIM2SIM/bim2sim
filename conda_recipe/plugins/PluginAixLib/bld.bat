@echo on
python -m pip install --no-deps --ignore-installed bim2sim/plugins/PluginAixLib
pip install -r bim2sim/plugins/PluginAixLib/requirements.txt
pip install -r bim2sim/plugins/PluginAixLib/dependency_requirements.txt
IF %ERRORLEVEL% NEQ 0 exit 1