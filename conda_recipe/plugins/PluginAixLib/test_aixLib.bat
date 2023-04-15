pip install deep_translator
pip install string_grouper
coverage run -m unittest discover bim2sim/plugins/PluginAixLib/test/integration_test ||
coverage report -i ||
coverage html -i
