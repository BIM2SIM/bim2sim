@echo on
python -m pip install --no-deps --ignore-installed .
python -m pip install deep_translator
python -m pip install string_grouper==0.6.1
python -m pip install -r dependency_requirements.txt
IF %ERRORLEVEL% NEQ 0 exit 1