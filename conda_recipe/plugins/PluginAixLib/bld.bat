@echo on
python -m pip install --no-deps --ignore-installed .
pip install -r   bim2sim\plugins\PluginAixLib\requirements.txt
IF %ERRORLEVEL% NEQ 0 exit 1