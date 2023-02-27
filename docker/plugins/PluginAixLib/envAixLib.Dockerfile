ARG IMAGE_VERSION=development

FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:${IMAGE_VERSION}

RUN /opt/conda/bin/conda install --yes --freeze-installed \
	    -c bim2sim ${BIM2SIM_NAME}==${BIM2SIM_VERSION}${BIM2SIM_FLAG} \
	&& /opt/conda/bin/conda clean -afy \
	&& find /opt/conda/ -follow -type f -name '*.a' -delete \
	&& find /opt/conda/ -follow -type f -name '*.pyc' -delete \
	&& find /opt/conda/ -follow -type f -name '*.js.map' -delete

