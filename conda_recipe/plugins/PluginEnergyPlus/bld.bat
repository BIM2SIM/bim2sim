@echo on
python -m  pip install --upgrade pip
pip install https://github.com/NREL/EnergyPlusRegressionTool/archive/refs/tags/v1.9.6.zip
pip install geomeppy==0.11.8
IF %ERRORLEVEL% NEQ 0 exit 1