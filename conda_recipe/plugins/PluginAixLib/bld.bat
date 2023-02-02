@echo on
python -m pip install --no-deps --ignore-installed .
conda install conda-bld/linux-64/bim2sim-*
IF %ERRORLEVEL% NEQ 0 exit 1