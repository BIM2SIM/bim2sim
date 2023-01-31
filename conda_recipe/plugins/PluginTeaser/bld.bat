@echo on
pip install git+https://github.com/RWTH-EBC/TEASER@development
pip install git+https://github.com/DaJansenGit/BuildingsPy.git
IF %ERRORLEVEL% NEQ 0 exit 1