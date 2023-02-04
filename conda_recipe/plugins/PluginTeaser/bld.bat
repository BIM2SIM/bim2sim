@echo on
conda install conda-bld/bim2sim/linux-64/bim2sim-*
pip install pyqt5==5.12.2
pip install git+https://github.com/RWTH-EBC/TEASER@development
pip install git+https://github.com/DaJansenGit/BuildingsPy.git
IF %ERRORLEVEL% NEQ 0 exit 1