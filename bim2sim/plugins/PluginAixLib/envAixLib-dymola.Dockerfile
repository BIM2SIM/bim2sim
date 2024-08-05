FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:dymola

COPY ./bim2sim/plugins/PluginAixLib/requirements.txt ./requirements_aixlib.txt

RUN pip install --default-timeout=1000 --user --upgrade pip
RUN pip install --default-timeout=1000 -r ./requirements_aixlib.txt
