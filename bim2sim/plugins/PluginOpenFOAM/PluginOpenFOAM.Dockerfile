ARG PYTHON_VERSION=energyplus-py3.10
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/bim2sim:${PYTHON_VERSION}

RUN echo $(pwd)

# Install the package
ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN pip install --no-cache-dir '.[PluginOpenFOAM]' -i https://pypi.tuna.tsinghua.edu.cn/simple
