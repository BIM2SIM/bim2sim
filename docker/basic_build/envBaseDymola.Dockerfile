# The build-stage image:
#FROM continuumio/miniconda3 AS build
FROM registry.git.rwth-aachen.de/ebc/ebc_all/gitlab_ci/templates:continuumio_miniconda3_latest AS build
ARG ENV_FILE
ARG ENV_NAME
COPY . .

# Install the package as normal:
#COPY docker/basic_build/environment.yml .
RUN  apt update  && \
     apt upgrade -y &&\
     apt install libgl1 -y &&\
     apt install build-essential -y \
RUN mamba install git conda-verify -y

RUN conda config --set channel_priority flexible && \
    conda config --add channels inso && \
    conda config --add channels dsdale24 && \
    conda config --add channels conda-forge && \
    conda config --add channels bim2sim && \
    conda config --add channels anaconda

#RUN mamba create -n bim2sim3.9  -c bim2sim ${BIM2SIM_NAME}==${BIM2SIM_VERSION}${BIM2SIM_FLAG} -y

RUN mamba env create -f  $ENV_FILE
# Install mamba-pack:
RUN mamba install -c conda-forge conda-pack -y

# Use conda-pack to create a standalone enviornment
# in /venv:
RUN conda-pack -n $ENV_NAME -o /tmp/env.tar && \
  mkdir /venv && cd /venv && tar xf /tmp/env.tar && \
  rm /tmp/env.tar

# We've put venv in same path it'll be in final image,
# so now fix up paths:
RUN /venv/bin/conda-unpack
RUN mamba clean -afy

RUN find -name '*.a' -delete   && \
  find -name '*.pyc' -delete && \
  find -name '*.js.map' -delete && \
  rm -rf /venv/conda-meta && \
  rm -rf /venv/include && \
# rm /env/lib/libpython3.9.so.1.0  && \
  find -name '__pycache__' -type d -exec rm -rf '{}' '+' && \
  #rm -rf /venv/lib/python3.9/site-packages/pip  \
  rm -rf  /venv/lib/python3.9/idlelib /venv/lib/python3.9/ensurepip \
  rm -rf  /venv/lib/python3.9/idlelib /venv/lib/python3.9/ensurepip \
    /venv/lib/libasan.so.5.0.0 \
    /venv/lib/libtsan.so.0.0.0 \
    /venv/lib/liblsan.so.0.0.0 \
    /venv/lib/libubsan.so.1.0.0 \
    /venv/bin/x86_64-conda-linux-gnu-ld \
    /venv/bin/sqlite3 \
    /venv/bin/openssl \
    /venv/share/terminfo \
  rm -rf /venv/lib/python3.9/site-packages/uvloop/loop.c

FROM registry.git.rwth-aachen.de/ebc/ebc_intern/dymola-docker:Dymola_2022 as runtime

ARG DEBIAN_FRONTEND=noninteractive
# ENV DISPLAY=host.docker.internal:0.0
WORKDIR /bim2sim-coding
# Copy /venv from the previous stage:
COPY --from=build /venv /venv
RUN ln -s /venv/bin/python /usr/bin/python && \
     ln -s /venv/bin/python3.9 /usr/bin/python3.9 && \
    ln -s /venv/bin/bim2sim /usr/bin/bim2sim  && \
    ln -s /venv/bin/pip /usr/bin/pip
#SHELL ["/bin/bash", "-c"]
RUN apt-get update --fix-missing && \
    apt-get install -y wget unzip bzip2 ca-certificates curl git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN   apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
SHELL  ["bash", "-c", "source", "/venv/bin/activate"]
ENV PATH /venv/bin:$PATH
#ENTRYPOINT source /venv/bin/activate && \
#           bim2sim --help
           #python /venv/lib/python3.9/site-packages/bim2sim/examples/e5_export_quantities_for_lca.py
