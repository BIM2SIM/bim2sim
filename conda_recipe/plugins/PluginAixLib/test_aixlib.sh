pip install coverage
pip install coverage-badge
wget --quiet -O test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/R6K1H5Z9fiB3EoB/download
unzip test/TestModels/download.zip -d test/TestModels/
coverage run -m unittest discover bim2sim/plugins/PluginAixLib/test/integration_test
coverage report -i
mkdir -p $CI_COMMIT_REF_NAME/coverage
coverage html -i
cp htmlcov/* $CI_COMMIT_REF_NAME/coverage/