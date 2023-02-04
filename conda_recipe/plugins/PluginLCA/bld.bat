@echo on
conda install conda-bld/bim2sim/linux-64/bim2sim-*
IF %ERRORLEVEL% NEQ 0 exit 1