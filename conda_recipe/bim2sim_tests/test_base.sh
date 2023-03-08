pip install coverage
pip install coverage-badge

mv ./* /bim2sim-coding/
cd /bim2sim-coding
wget --quiet -O /bim2sim-coding/test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/R6K1H5Z9fiB3EoB/download
unzip /bim2sim-coding/test/TestModels/download.zip -d /bim2sim-coding/test/TestModels/
coverage run -m unittest discover /bim2sim-coding/test
coverage report -i
mkdir -p $CI_COMMIT_REF_NAME/coverage
coverage html -i
cp htmlcov/* $CI_COMMIT_REF_NAME/coverage/