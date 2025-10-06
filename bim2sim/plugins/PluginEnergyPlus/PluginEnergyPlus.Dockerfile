ARG PYTHON_VERSION=3.9
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/bim2sim:energyplus${PYTHON_VERSION}

# Install the package
ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN pip install --no-cache-dir '.[PluginEnergyPlus]' -i https://pypi.tuna.tsinghua.edu.cn/simple
