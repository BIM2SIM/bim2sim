# stage 0: aixlib (use aixlib as base layer because it has least dependencies)
#FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:aixlib AS aixlib

# stage 1: teaser
FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:teaser AS teaser
# copy python installs from aixlib stage

# stage 2: cfd
#FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:cfd AS cfd
# copy python installs from teaser stage

# stage 3: energyplus plugin (use ep as last image because it has most dependencies and already holds base image)
FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:energyplus AS energyplus
# copy python installs from previous stages
COPY --from=teaser /opt/conda/envs/env/lib/python3.7/site-packages/teaser/ /opt/conda/envs/env/lib/python3.7/site-packages/teaser/
# todo copy cfd installs from previous stages (clarify with eric)

# copy code to image
WORKDIR /bim2sim-coding

COPY . .






