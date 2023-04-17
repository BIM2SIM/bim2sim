#!/bin/bash
set -x &&
apt-get update -y &&
apt-get upgrade -y &&
apt-get install unzip wget -y &&
pip install -r requirements.txt &&
pip install -r dependency_requirements.txt  &&
pip install -r bim2sim/plugins/PluginTeaser/requirements.txt   &&
pip install -r bim2sim/plugins/PluginTeaser/dependency_requirements.txt  &&
pip install coverage &&
pip install coverage-badge &&
wget --quiet -O test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/SAUQQgvwqeS96ix/download &&
unzip -o test/TestModels/download.zip -d test/TestModels/ &&
wget --quiet -O bim2sim/assets/download.zip https://rwth-aachen.sciebo.de/s/5EQqe5g8x0x4lae/download &&
unzip -o bim2sim/assets/download.zip -d bim2sim/assets/ &&
git clone --branch development https://github.com/RWTH-EBC/AixLib.git AixLib &&
xvfb-run -n 77 coverage run -m unittest discover bim2sim/plugins/PluginTEASER/test/regression_test &&
coverage report -i &&
coverage html -i
