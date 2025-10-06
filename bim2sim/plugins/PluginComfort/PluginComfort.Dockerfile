ARG BASE_IMAGE_TAG=energyplus-py3.10
FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/bim2sim:${BASE_IMAGE_TAG}

# Install the package
ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN pip install --no-cache-dir '.[PluginComfort]' -i https://pypi.tuna.tsinghua.edu.cn/simple
