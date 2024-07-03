
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:development

# install EnergyPlus specific requirements
COPY ./bim2sim/plugins/PluginEnergyPlus/requirements.txt ./requirements_ep.txt

RUN pip install -r ./requirements_ep.txt

## EnergyPlus part

# This is not ideal. The tarballs are not named nicely and EnergyPlus versioning is strange
#ARG ENERGYPLUS_VERSION
#ARG ENERGYPLUS_TAG
#ARG ENERGYPLUS_SHA
#ARG ENERGYPLUS_INSTALL_VERSION
ENV ENERGYPLUS_VERSION=9.4.0
ENV ENERGYPLUS_TAG=v9.4.0
ENV ENERGYPLUS_SHA=998c4b761e

# This should be x.y.z, but EnergyPlus convention is x-y-z
ENV ENERGYPLUS_INSTALL_VERSION=9-4-0

# Downloading from Github
# e.g. https://github.com/NREL/EnergyPlus/releases/download/v8.3.0/EnergyPlus-8.3.0-6d97d074ea-Linux-x86_64.sh
ENV ENERGYPLUS_DOWNLOAD_BASE_URL https://github.com/NREL/EnergyPlus/releases/download/$ENERGYPLUS_TAG
ENV ENERGYPLUS_DOWNLOAD_FILENAME EnergyPlus-$ENERGYPLUS_VERSION-$ENERGYPLUS_SHA-Linux-Ubuntu18.04-x86_64.sh
ENV ENERGYPLUS_DOWNLOAD_URL $ENERGYPLUS_DOWNLOAD_BASE_URL/$ENERGYPLUS_DOWNLOAD_FILENAME
#ENV ENERGYPLUS_DOWNLOAD_URL https://github.com/NREL/EnergyPlus/releases/download/v9.4.0/EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64.sh

# Collapse the update of packages, download and installation into one command
# to make the container smaller & remove a bunch of the auxiliary apps/files
# that are not needed in the container
RUN apt-get --allow-releaseinfo-change update && apt-get install -y ca-certificates curl libx11-6 libexpat1\
    && rm -rf /var/lib/apt/lists/* \
    && curl -SLO $ENERGYPLUS_DOWNLOAD_URL \
    && chmod +x $ENERGYPLUS_DOWNLOAD_FILENAME \
    && echo "y\r" | ./$ENERGYPLUS_DOWNLOAD_FILENAME \
    && rm $ENERGYPLUS_DOWNLOAD_FILENAME \
    && cd /usr/local/EnergyPlus-$ENERGYPLUS_INSTALL_VERSION \
    && rm -rf DataSets Documentation ExampleFiles WeatherData MacroDataSets PostProcess/convertESOMTRpgm \
    PostProcess/EP-Compare PreProcess/FMUParser PreProcess/ParametricPreProcessor PreProcess/IDFVersionUpdater

# Remove the broken symlinks
RUN cd /usr/local/bin \
    && find -L . -type l -delete

VOLUME /var/simdata/energyplus
WORKDIR /var/simdata/energyplus

#CMD [ "/bin/bash" ]
