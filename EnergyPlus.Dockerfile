# Actual image to be used for testing of plugins or provision of plugins as images

ARG PYTHON_VERSION=3.9
ARG ENERGYPLUS_VERSION=9.4.0
ARG ENERGYPLUS_INSTALL_VERSION=9-4-0

# First stage - use the EnergyPlus base image
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/bim2sim:energyplus_builder as energyplus

# Second stage - build the final image
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/bim2sim:dev-py${PYTHON_VERSION}

ARG MAMBA_DOCKERFILE_ACTIVATE=1
ARG ENERGYPLUS_INSTALL_VERSION

ENV PIP_DEFAULT_TIMEOUT=500
ENV ENERGYPLUS_INSTALL_VERSION=${ENERGYPLUS_INSTALL_VERSION}

# Copy EnergyPlus from the first stage
USER root
COPY --from=energyplus /usr/local/EnergyPlus-${ENERGYPLUS_INSTALL_VERSION} /usr/local/EnergyPlus-${ENERGYPLUS_INSTALL_VERSION}
COPY --from=energyplus /usr/local/bin/energyplus /usr/local/bin/energyplus
COPY --from=energyplus /usr/local/bin/EPMacro /usr/local/bin/EPMacro
COPY --from=energyplus /usr/local/bin/ExpandObjects /usr/local/bin/ExpandObjects

USER $MAMBA_USER

VOLUME /var/simdata/energyplus
WORKDIR /var/simdata/energyplus