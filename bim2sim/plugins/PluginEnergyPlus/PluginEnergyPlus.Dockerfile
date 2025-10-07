ARG PYTHON_VERSION=energyplus-py3.10
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/bim2sim:${PYTHON_VERSION}
ARG MAMBA_DOCKERFILE_ACTIVATE=1

# Copy the files to enable fresh installation in /opt/bim2sim folder
WORKDIR /opt/bim2sim
COPY --chown=$MAMBA_USER:$MAMBA_USER . .

# Install the package
RUN pip install --no-cache-dir '.[PluginEnergyPlus]' -i https://pypi.tuna.tsinghua.edu.cn/simple

# For EnergyPlus images, use the energyplus var folder
WORKDIR /var/simdata/energyplus
