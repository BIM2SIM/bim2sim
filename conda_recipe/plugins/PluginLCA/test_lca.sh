pip install coverage
pip install coverage-badge
apt-get update -y
apt-get upgrade -y
apt-get install unzip wget -y
wget --quiet -O test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/SAUQQgvwqeS96ix/download
unzip test/TestModels/download.zip -d test/TestModels/
coverage run -m unittest discover bim2sim/plugins/PluginLCA/test/integration_test
coverage report -i
mkdir -p $CI_COMMIT_REF_NAME/coverage
coverage html -i
cp htmlcov/* $CI_COMMIT_REF_NAME/coverage/