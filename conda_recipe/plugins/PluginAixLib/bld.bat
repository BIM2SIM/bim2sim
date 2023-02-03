@echo on
conda install conda-bld/linux-64/bim2sim-*
IF %ERRORLEVEL% NEQ 0 exit 1