@echo on
python -m pip install --no-deps --ignore-installed git+https://github.com/RWTH-EBC/TEASER@development
python -m pip install --no-deps --ignore-installed git+https://github.com/DaJansenGit/BuildingsPy.git
IF %ERRORLEVEL% NEQ 0 exit 1