pip install coverage
pip install coverage-badge

wget --quiet -O /bim2sim-coding/test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/SAUQQgvwqeS96ix/download
unzip /bim2sim-coding/test/TestModels/download.zip -d /bim2sim-coding/test/TestModels/
coverage run -m unittest discover /bim2sim-coding/bim2sim/plugins/PluginCFD/test/integration_test
coverage report -i
mkdir -p $CI_COMMIT_REF_NAME/coverage
coverage html -i
cp htmlcov/* $CI_COMMIT_REF_NAME/coverage/