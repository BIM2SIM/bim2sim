FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:development

COPY ./bim2sim/plugins/PluginTEASER/requirements.txt ./requirements_teaser.txt

RUN pip install -r ./requirements_teaser.txt

#ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginTEASER/bim2sim_teaser/TEASER/"
