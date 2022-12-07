@echo on
python setup.py install
IF %ERRORLEVEL% NEQ 0 exit 1
conda install -c conda-forge ifcopenshell pythonocc-core=7.6.2 -y
