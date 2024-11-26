ARG PYTHON_VERSION=3.9
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/bim2sim:dev-py${PYTHON_VERSION}

ARG MAMBA_DOCKERFILE_ACTIVATE=1

ENV PIP_DEFAULT_TIMEOUT=500

# Install the package
RUN pip install --no-cache-dir '.[PluginComfort]' -i https://pypi.tuna.tsinghua.edu.cn/simple

# EnergyPlus part
ENV ENERGYPLUS_VERSION=9.4.0
ENV ENERGYPLUS_TAG=v9.4.0
ENV ENERGYPLUS_SHA=998c4b761e
ENV ENERGYPLUS_INSTALL_VERSION=9-4-0

ENV ENERGYPLUS_DOWNLOAD_BASE_URL https://github.com/NREL/EnergyPlus/releases/download/$ENERGYPLUS_TAG
ENV ENERGYPLUS_DOWNLOAD_FILENAME EnergyPlus-$ENERGYPLUS_VERSION-$ENERGYPLUS_SHA-Linux-Ubuntu18.04-x86_64.sh
ENV ENERGYPLUS_DOWNLOAD_URL $ENERGYPLUS_DOWNLOAD_BASE_URL/$ENERGYPLUS_DOWNLOAD_FILENAME

USER root

# Install necessary packages and EnergyPlus
RUN apt-get update && apt-get install -y ca-certificates curl libx11-6 libexpat1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -SLO --retry 5 --retry-delay 15 --retry-max-time 900 --connect-timeout 60 --max-time 3600 $ENERGYPLUS_DOWNLOAD_URL || \
    (sleep 30 && curl -SLO --retry 5 --retry-delay 15 --retry-max-time 900 --connect-timeout 60 --max-time 3600 $ENERGYPLUS_DOWNLOAD_URL)

RUN chmod +x $ENERGYPLUS_DOWNLOAD_FILENAME

RUN echo "y\r" | ./$ENERGYPLUS_DOWNLOAD_FILENAME

RUN rm $ENERGYPLUS_DOWNLOAD_FILENAME

RUN cd /usr/local/EnergyPlus-$ENERGYPLUS_INSTALL_VERSION \
    && rm -rf DataSets Documentation ExampleFiles WeatherData MacroDataSets PostProcess/convertESOMTRpgm \
       PostProcess/EP-Compare PreProcess/FMUParser PreProcess/ParametricPreProcessor PreProcess/IDFVersionUpdater

# Remove broken symlinks
RUN cd /usr/local/bin && find -L . -type l -delete

USER $MAMBA_USER

VOLUME /var/simdata/energyplus
WORKDIR /var/simdata/energyplus