# Base image which install python with micromamba and pythonocc to speed up CI

ARG PYTHON_VERSION=3.9
FROM mambaorg/micromamba:2.0.2

# Redeclare the ARG after FROM, but don't set a default value
ARG PYTHON_VERSION

# Set the Python version as an environment variable
ENV PYTHON_VERSION=${PYTHON_VERSION}

# Copy the environment file
COPY --chown=$MAMBA_USER:$MAMBA_USER env.yaml /tmp/env.yaml

RUN echo "Python version argument: ${PYTHON_VERSION}"

# Modify the env.yaml file to include the specified Python version
RUN micromamba install -y -n base -c conda-forge python=${PYTHON_VERSION} pythonocc-core=7.7.0 pip gcc git --retry-clean-cache && \
    micromamba clean --all --yes

# Copy files
COPY --chown=$MAMBA_USER:$MAMBA_USER . .

ENV PIP_DEFAULT_TIMEOUT=500
