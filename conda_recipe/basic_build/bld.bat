@echo on
python -m pip install --no-deps --ignore-installed .
IF %ERRORLEVEL% NEQ 0 exit 1