#!/bin/bash
set -x &&
apt-get update -y &&
apt-get upgrade -y &&
apt-get install unzip wget -y &&
pip install coverage &&
pip install coverage-badge &&
wget --quiet -O test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/SAUQQgvwqeS96ix/download &&
unzip test/TestModels/download.zip -d test/TestModels/ &&
coverage run -m unittest discover bim2sim/plugins/PluginCFD/test/integration_test ||
coverage report -i ||
coverage html -i
