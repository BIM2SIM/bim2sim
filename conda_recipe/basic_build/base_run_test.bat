@echo on
pip install -r requirements.txt
pip install -r dependency_requirements.txt
pip install coverage && pip install coverage-badge  && wget --quiet  -O test/TestModels/download.zip https://rwth-aachen.sciebo.de/s/R6K1H5Z9fiB3EoB/download
coverage run -m unittest discover test
coverage report -i && coverage html -i
