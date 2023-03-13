@echo on
apt-get update -y
apt-get upgrade -y
apt-get install unzip wget -y
pip install coverage
pip install coverage-badge
cat bim2sim/plugins/PluginEnergyPlus/data/Minimal.idf
wget --quiet -O test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/SAUQQgvwqeS96ix/download
unzip test/TestModels/download.zip -d test/TestModels/
wget --quiet -O bim2sim/assets/download.zip https://rwth-aachen.sciebo.de/s/5EQqe5g8x0x4lae/download
unzip bim2sim/assets/download.zip -d bim2sim/assets/
coverage run -m unittest discover bim2sim/plugins/PluginEnergyPlus/test/regression_test
coverage report -i
coverage html -i
