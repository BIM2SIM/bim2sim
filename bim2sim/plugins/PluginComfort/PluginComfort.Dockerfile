ARG PYTHON_VERSION=3.9
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/bim2sim:dev-energyplus-py${PYTHON_VERSION}

ARG MAMBA_DOCKERFILE_ACTIVATE=1

ENV PIP_DEFAULT_TIMEOUT=500

# Install the package
RUN pip install --no-cache-dir '.[PluginComfort]' -i https://pypi.tuna.tsinghua.edu.cn/simple