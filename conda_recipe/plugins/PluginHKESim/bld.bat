@echo on
pip install https://github.com/NREL/EnergyPlusRegressionTool/archive/refs/tags/v1.9.6.zip
IF %ERRORLEVEL% NEQ 0 exit 1