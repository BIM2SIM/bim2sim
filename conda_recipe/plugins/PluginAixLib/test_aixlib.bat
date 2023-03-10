pip install coverage
pip install coverage-badge

wget --quiet -O /bim2sim-coding/test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/R6K1H5Z9fiB3EoB/download
unzip /bim2sim-coding/test/TestModels/download.zip -d /bim2sim-coding/test/TestModels/
coverage run -m unittest discover /bim2sim-coding/bim2sim/plugins/PluginAixLib/test/integration_test
coverage report -i
coverage html -i
