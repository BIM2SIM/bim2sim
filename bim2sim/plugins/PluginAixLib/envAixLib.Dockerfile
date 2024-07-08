FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:development

COPY ./bim2sim/plugins/PluginAixLib/requirements.txt ./requirements_aixlib.txt

RUN pip install -r ./requirements_aixlib.txt
