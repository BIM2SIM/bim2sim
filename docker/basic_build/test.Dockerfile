# The build-stage image:
FROM continuumio/miniconda3 AS build
ARG BIM2SIM_NAME
ARG BIM2SIM_VERSION
ARG BIM2SIM_FLAG
# Install the package as normal:
#COPY docker/basic_build/venvironment.yml .
COPY docker/basic_build/environment.yml .
RUN conda env create -f environment.yml
RUN conda install -c conda-forge conda-pack
RUN conda-pack -n bim2sim_env -o /tmp/venv.tar && \
  mkdir /venv && cd /venv && tar xf /tmp/venv.tar && \
  rm /tmp/venv.tar
# We've put vvenv in same path it'll be in final image,
# so now fix up paths:
RUN /venv/bin/conda-unpack



#RUN conda clean --all
# The runtime-stage image; we can use Debian as the
# base image since the Conda venv also includes Python
# for us.
FROM debian:buster AS runtime
WORKDIR /bim2sim-coding
# Copy /vvenv from the previous stage:
COPY --from=build /venv /venv
RUN ln -s /venv/bin/python /usr/bin/python && \
     ln -s /venv/bin/python3.9 /usr/bin/python3.9 && \
    ln -s /venv/bin/bim2sim /usr/bin/bim2sim
    #ln -s /venv/bin/pip /usr/bin/pip

RUN apt-get update --fix-missing && \
    apt-get install -y wget unzip bzip2 ca-certificates curl git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV PATH /venv/bin:$PATH
