FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:development

COPY ./bim2sim/plugins/PluginAixLib/requirements.txt ./requirements_aixlib.txt

RUN pip install -r ./requirements_aixlib.txt
