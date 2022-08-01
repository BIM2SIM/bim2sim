# stage 0: aixlib (use aixlib as base layer because it has least dependencies)
FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:aixlib AS aixlib

# stage 1: teaser
FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:teaser AS teaser
# copy python installs from aixlib stage

# stage 2: cfd
FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:energyplus AS energyplus

# stage 3: cfd plugin (use cfd as last image because it has most dependencies and already holds base image)
FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:cfd AS cfd
# copy and merge python installs from previous stages
COPY --from=teaser /opt/conda/envs/env/ /tmp/teaser_env
COPY --from=energyplus /opt/conda/envs/env/ /tmp/energyplus_env
COPY --from=aixlib /opt/conda/envs/env/ /tmp/aixlib_env

RUN cp -n /tmp/energyplus_env/ /opt/conda/envs/env/
RUN cp -n /tmp/teaser_env/ /opt/conda/envs/env/
RUN cp -n /tmp/aixlib_env/ /opt/conda/envs/env/

# delete temp folders
RUN rm -rf /tmp/teaser_env /tmp/energyplus_env /tmp/aixlib_env

# copy energyplus install
COPY --from=energyplus /usr/local/EnergyPlus* /usr/local/EnergyPlus
ENV PATH "${PATH}:/usr/local/EnergyPlus"

# copy code to image
WORKDIR /bim2sim-coding

COPY . .
