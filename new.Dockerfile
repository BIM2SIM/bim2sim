# Use Ubuntu 20.04 as the base image
FROM mambaorg/micromamba:ubuntu20.04

# Set environment variables
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# Install necessary packages
USER root
RUN apt-get update && \
    apt-get install -y libgl1-mesa-dev gcc g++ git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
USER mambauser

# Set working directory
WORKDIR /bim2sim

# Copy code
COPY --chown=mambauser:mambauser . .

# Create environment and install dependencies
RUN micromamba create -n env python=3.11 -y && \
    micromamba install -n env -y -c conda-forge pythonocc-core=7.7.0 nomkl

# Activate the environment and install the requirements
RUN micromamba run -n env /bin/bash -c "\
    set -e && \
    echo 'Python version:' && python --version && \
    echo 'Pip version:' && pip --version && \
    echo 'Contents of current directory:' && ls -la && \
    echo 'Contents of pyproject.toml:' && cat pyproject.toml && \
    echo 'Installing package...' && \
    pip install -v . && \
    echo 'Installation completed successfully'"

# install bim2sim itself
RUN micromamba run -n env pip install --no-cache-dir -e '.'

# Clean up
RUN micromamba clean --all --yes

# Set the default command to run your application in the 'env' environment
ENTRYPOINT ["micromamba", "run", "-n", "env"]
CMD ["python", "-c", "import bim2sim; print('bim2sim version:', bim2sim.VERSION)"]