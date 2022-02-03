FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:ubuntu_base

ENV PYTHONPATH "${PYTHONPATH}:/bim2sim/PluginTEASER/bim2sim_teaser/TEASER/"
