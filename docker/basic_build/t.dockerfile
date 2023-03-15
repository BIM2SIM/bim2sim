# The build-stage image:
FROM continuumio/miniconda3 AS build
ARG BIM2SIM_NAME
ARG BIM2SIM_VERSION
ARG BIM2SIM_FLAG
# Install the package as normal:
#COPY docker/basic_build/environment.yml .
RUN conda config --add channels bim2sim
RUN conda config --add channels conda-forge
RUN conda install conda=23.1.0
RUN conda create -n bim2sim3.9 ${BIM2SIM_NAME}==${BIM2SIM_VERSION}${BIM2SIM_FLAG}
# Install conda-pack:
