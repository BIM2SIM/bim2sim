pip install -r requirements.txt
pip install -r dependency_requirements.txt
pip install -r bim2sim/plugins/PluginAixLib/requirements.txt
pip install -r bim2sim/plugins/PluginAixLib/dependency_requirements.txt
coverage run -m unittest discover bim2sim/plugins/PluginAixLib/test/integration_test ||
coverage report -i ||
coverage html -i
