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
RUN conda install -c conda-forge conda-pack

# Use conda-pack to create a standalone enviornment
# in /venv:
RUN conda-pack -n bim2sim3.9 -o /tmp/env.tar && \
  mkdir /venv && cd /venv && tar xf /tmp/env.tar && \
  rm /tmp/env.tar

# We've put venv in same path it'll be in final image,
# so now fix up paths:
RUN /venv/bin/conda-unpack

RUN find -name '*.a' -delete   && \
  find -name '*.pyc' -delete && \
  find -name '*.js.map' -delete && \
  rm -rf /venv/conda-meta && \
  rm -rf /venv/include && \
# rm /env/lib/libpython3.9.so.1.0  && \
  find -name '__pycache__' -type d -exec rm -rf '{}' '+' && \
#  rm -rf /env/lib/python3.9/site-packages/pip /env/lib/python3.9/idlelib /env/lib/python3.9/ensurepip \
  rm -rf  /env/lib/python3.9/idlelib /env/lib/python3.9/ensurepip \
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
WORKDIR /bim2sim-coding
COPY --from=build /venv /venv
RUN ln -s /venv/bin/python /usr/bin/python && \
     ln -s /venv/bin/python3.9 /usr/bin/python3.9 && \
    ln -s /venv/bin/bim2sim /usr/bin/bim2sim  && \
    ln -s /venv/bin/pip /usr/bin/pip

RUN apt-get update
RUN apt-get install wget unzip -y
ENV PATH /venv/bin:$PATH
