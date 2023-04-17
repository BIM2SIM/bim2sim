@echo on
pip install -r requirements.txt
pip install -r dependency_requirements.txt
pip install -r bim2sim/plugins/PluginLCA/requirements.txt
pip install -r bim2sim/plugins/PluginLCA/dependency_requirements.txt
coverage run -m unittest discover bim2sim/plugins/PluginLCA/test/integration_test
coverage report -i
coverage html -i