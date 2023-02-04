@echo on
conda install conda-bld/bim2sim/linux-64/bim2sim-*
pip install https://github.com/NREL/EnergyPlusRegressionTool/archive/refs/tags/v1.9.6.zip
IF %ERRORLEVEL% NEQ 0 exit 1