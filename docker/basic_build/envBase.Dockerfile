########################################################
FROM ubuntu:20.04
ARG BIM2SIM_NAME=bim2sim
ARG BIM2SIM_VERSION
ARG BIM2SIM_FLAG
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PATH /opt/conda/bin:$PATH

RUN apt-get update --fix-missing && \
    apt-get install -y wget bzip2 ca-certificates curl git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-4.5.11-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh && \
    /opt/conda/bin/conda clean -tipsy && \
    ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate base" >> ~/.bashrc

ENV TINI_VERSION v0.16.1
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /usr/bin/tini
RUN chmod +x /usr/bin/tini

ENTRYPOINT [ "/usr/bin/tini", "--" ]
CMD [ "/bin/bash" ]
########################################################


########################################################
WORKDIR /bim2sim-coding

RUN apt-get --allow-releaseinfo-change update
RUN apt-get -y install unzip
RUN apt-get -y install libgl-dev


RUN 	conda create -n env python=3.9
RUN		conda update -n base -c defaults conda
RUN 	echo "source activate env" > ~/.bashrc
ENV 	PATH /opt/conda/envs/env/bin:$PATH
SHELL 	["conda", "run", "-n", "env", "/bin/bash", "-c"]

RUN  conda config --add channels bim2sim
RUN  conda config --add channels conda-forge

RUN /opt/conda/bin/conda install --yes --freeze-installed \
	    -c bim2sim ${BIM2SIM_NAME}==${BIM2SIM_VERSION}${BIM2SIM_FLAG} \
	&& /opt/conda/bin/conda clean -afy \
	&& find /opt/conda/ -follow -type f -name '*.a' -delete \
	&& find /opt/conda/ -follow -type f -name '*.pyc' -delete \
	&& find /opt/conda/ -follow -type f -name '*.js.map' -delete