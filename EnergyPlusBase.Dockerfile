# Base image with energy plus and micromamba installed to be used as a build-layer to avoid repeated downloads from github

FROM mambaorg/micromamba:2.0.2

ARG ENERGYPLUS_VERSION=9.4.0
ARG ENERGYPLUS_SHA=998c4b761e

ENV ENERGYPLUS_VERSION=$ENERGYPLUS_VERSION
ENV ENERGYPLUS_TAG="v${ENERGYPLUS_VERSION}"
ENV ENERGYPLUS_SHA=$ENERGYPLUS_SHA
ENV ENERGYPLUS_INSTALL_VERSION=${ENERGYPLUS_INSTALL_VERSION}

ENV DOWNLOAD_URL="https://energyplus.net/assets/EnergyPlus-${ENERGYPLUS_VERSION}-${ENERGYPLUS_SHA}-Linux-Ubuntu18.04-x86_64.sh"
#ENV DOWNLOAD_URL="https://github.com/NREL/EnergyPlus/releases/download/${ENERGYPLUS_TAG}/EnergyPlus-${ENERGYPLUS_VERSION}-${ENERGYPLUS_SHA}-Linux-Ubuntu18.04-x86_64.sh"

USER root


# Download and install EnergyPlus using wget with retry options
RUN apt-get update && apt-get install -y ca-certificates wget libx11-6 libexpat1 \
    && rm -rf /var/lib/apt/lists/* \
    && wget --retry-connrefused --waitretry=30 --read-timeout=60 --timeout=60 -t 10 -O EnergyPlus-Installer.sh $DOWNLOAD_URL \
    && chmod +x EnergyPlus-Installer.sh \
    && echo "y\r" | ./EnergyPlus-Installer.sh \
    && rm EnergyPlus-Installer.sh \
    && cd /usr/local/EnergyPlus-${ENERGYPLUS_INSTALL_VERSION} \
    && rm -rf DataSets Documentation ExampleFiles WeatherData MacroDataSets PostProcess/convertESOMTRpgm \
       PostProcess/EP-Compare PreProcess/FMUParser PreProcess/ParametricPreProcessor PreProcess/IDFVersionUpdater \
    && cd /usr/local/bin && find -L . -type l -delete

USER mambauser
