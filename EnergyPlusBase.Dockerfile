# Base image with energy plus and micromamba installed to be used as a build-layer to avoid repeated downloads from github

FROM mambaorg/micromamba:2.0.2

ARG ENERGYPLUS_VERSION=9.4.0
ARG ENERGYPLUS_TAG=v9.4.0
ARG ENERGYPLUS_SHA=998c4b761e
ARG ENERGYPLUS_INSTALL_VERSION=9-4-0

ENV ENERGYPLUS_VERSION=$ENERGYPLUS_VERSION
ENV ENERGYPLUS_TAG=$ENERGYPLUS_TAG
ENV ENERGYPLUS_SHA=$ENERGYPLUS_SHA
ENV ENERGYPLUS_INSTALL_VERSION=$ENERGYPLUS_INSTALL_VERSION
ENV ENERGYPLUS_DOWNLOAD_BASE_URL=https://github.com/NREL/EnergyPlus/releases/download/$ENERGYPLUS_TAG
ENV ENERGYPLUS_DOWNLOAD_FILENAME=EnergyPlus-$ENERGYPLUS_VERSION-$ENERGYPLUS_SHA-Linux-Ubuntu18.04-x86_64.sh
ENV ENERGYPLUS_DOWNLOAD_URL=$ENERGYPLUS_DOWNLOAD_BASE_URL/$ENERGYPLUS_DOWNLOAD_FILENAME

USER root

# Install necessary packages and EnergyPlus
RUN apt-get update && apt-get install -y ca-certificates curl libx11-6 libexpat1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -SLOC --retry 5 --retry-delay 15 --retry-max-time 900 --connect-timeout 60 --max-time 3600 $ENERGYPLUS_DOWNLOAD_URL || \
    (sleep 30 && curl -SLOC --retry 5 --retry-delay 15 --retry-max-time 900 --connect-timeout 60 --max-time 3600 $ENERGYPLUS_DOWNLOAD_URL)

RUN chmod +x $ENERGYPLUS_DOWNLOAD_FILENAME

RUN echo "y\r" | ./$ENERGYPLUS_DOWNLOAD_FILENAME

RUN rm $ENERGYPLUS_DOWNLOAD_FILENAME

RUN cd /usr/local/EnergyPlus-$ENERGYPLUS_INSTALL_VERSION \
    && rm -rf DataSets Documentation ExampleFiles WeatherData MacroDataSets PostProcess/convertESOMTRpgm \
       PostProcess/EP-Compare PreProcess/FMUParser PreProcess/ParametricPreProcessor PreProcess/IDFVersionUpdater

# Remove broken symlinks
RUN cd /usr/local/bin && find -L . -type l -delete

USER mambauser