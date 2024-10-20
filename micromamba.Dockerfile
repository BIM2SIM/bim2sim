ARG PYTHON_VERSION=3.9
FROM mambaorg/micromamba:2.0.2

# Set the Python version as an environment variable
ENV PYTHON_VERSION=${PYTHON_VERSION}

# Copy the environment file
COPY --chown=$MAMBA_USER:$MAMBA_USER env.yaml /tmp/env.yaml

# Modify the env.yaml file to include the specified Python version
RUN micromamba install -y -n base -f /tmp/env.yaml python=${PYTHON_VERSION} && \
    micromamba clean --all --yes

# Copy files
COPY --chown=$MAMBA_USER:$MAMBA_USER . .

ARG MAMBA_DOCKERFILE_ACTIVATE=1

ENV PIP_DEFAULT_TIMEOUT=500

# Install the package
RUN pip install --no-cache-dir '.' -i https://pypi.tuna.tsinghua.edu.cn/simple