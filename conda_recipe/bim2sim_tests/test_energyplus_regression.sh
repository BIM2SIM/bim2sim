pip install coverage
pip install coverage-badge

cat /bim2sim-coding/bim2sim/plugins/PluginEnergyPlus/data/Minimal.idf
wget --quiet -O /bim2sim-coding/test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/SAUQQgvwqeS96ix/download
unzip /bim2sim-coding/test/TestModels/download.zip -d /bim2sim-coding/test/TestModels/
wget --quiet -O /bim2sim-coding/bim2sim/assets/download.zip https://rwth-aachen.sciebo.de/s/5EQqe5g8x0x4lae/download
unzip /bim2sim-coding/bim2sim/assets/download.zip -d /bim2sim-coding/bim2sim/assets/
coverage run -m unittest discover /bim2sim-coding/bim2sim/plugins/PluginEnergyPlus/test/regression_test
coverage report -i
mkdir -p $CI_COMMIT_REF_NAME/coverage
coverage html -i
cp htmlcov/* $CI_COMMIT_REF_NAME/coverage/