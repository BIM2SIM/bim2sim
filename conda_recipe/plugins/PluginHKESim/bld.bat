@echo on
conda install conda-bld/linux-64/bim2sim-* -y
pip install https://github.com/NREL/EnergyPlusRegressionTool/archive/refs/tags/v1.9.6.zip -y
IF %ERRORLEVEL% NEQ 0 exit 1