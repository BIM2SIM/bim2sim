@echo on
conda install conda-bld/linux-64/bim2sim-* -y
pip install git+https://github.com/RWTH-EBC/TEASER@development -y
pip install git+https://github.com/DaJansenGit/BuildingsPy.git -y
IF %ERRORLEVEL% NEQ 0 exit 1