#!/bin/bash
set -x &&
apt-get update -y &&
apt-get upgrade -y &&
apt-get install unzip wget -y &&
pip install -r requirements.txt &&
pip install -r dependency_requirements.txt  &&
pip install -r bim2sim/plugins/PluginLCA/requirements.txt   &&
pip install -r bim2sim/plugins/PluginLCA/dependency_requirements.txt  &&
pip install coverage &&
pip install coverage-badge &&
wget --quiet -O test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/SAUQQgvwqeS96ix/download &&
unzip -o test/TestModels/download.zip -d test/TestModels/ &&
coverage run -m unittest discover bim2sim/plugins/PluginLCA/test/integration_test &&
coverage report -i &&
coverage html -i
