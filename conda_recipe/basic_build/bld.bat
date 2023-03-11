@echo on
python -m pip install --no-deps --ignore-installed .
pip install deep-translator
pip install decision
IF %ERRORLEVEL% NEQ 0 exit 1