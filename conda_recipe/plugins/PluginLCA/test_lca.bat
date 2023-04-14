@echo on
coverage run -m unittest discover bim2sim/plugins/PluginLCA/test/integration_test
coverage report -i
coverage html -i