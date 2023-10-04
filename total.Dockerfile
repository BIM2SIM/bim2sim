# stage 0: aixlib (use aixlib as base layer because it has least dependencies)
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:aixlib AS aixlib

# stage 1: teaser
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:teaser AS teaser
# copy python installs from aixlib stage

# stage 2: cfd
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:energyplus AS energyplus

# stage 3: cfd plugin (use cfd as last image because it has most dependencies and already holds base image)
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:cfd AS cfd

# copy and merge python installs from previous stages
COPY --from=teaser /opt/conda/envs/env/ /tmp/teaser_env
COPY --from=energyplus /opt/conda/envs/env/ /tmp/energyplus_env
COPY --from=aixlib /opt/conda/envs/env/ /tmp/aixlib_env

RUN cp -n -r /tmp/energyplus_env/* /opt/conda/envs/env/ &&\
  cp -n -r /tmp/teaser_env/* /opt/conda/envs/env/ &&\
  cp -n -r /tmp/aixlib_env/* /opt/conda/envs/env/ &&\
  rm -rf /tmp/teaser_env /tmp/energyplus_env /tmp/aixlib_env 

# copy energyplus install
COPY --from=energyplus /usr/local/EnergyPlus-9-4-0 /usr/local/EnergyPlus-9-4-0
ENV PATH "${PATH}:/usr/local/EnergyPlus-9-4-0"

# copy code to image
WORKDIR /bim2sim-coding

COPY . .
