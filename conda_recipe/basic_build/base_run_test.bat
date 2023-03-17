@echo on
pip install coverage
pip install coverage-badge
coverage run -m unittest discover test
coverage report -i
coverage html -i
