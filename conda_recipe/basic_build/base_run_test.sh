set -x &&
apt-get update -y &&
apt-get upgrade -y &&
apt-get install unzip wget -y &&
pip install coverage &&
pip install coverage-badge &&
wget --quiet  -O test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/R6K1H5Z9fiB3EoB/download &&
unzip test/TestModels/download.zip -d test/TestModels/ &&
coverage run -m unittest discover test ||
coverage report -i  ||
coverage html -i
