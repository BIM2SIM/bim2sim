FROM registry.git.rwth-aachen.de/ebc/ebc_intern/dymola-docker:Dymola_2022

ARG BIM2SIM_NAME=bim2sim
ARG BIM2SIM_VERSION
ARG BIM2SIM_FLAG
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PATH /opt/conda/bin:$PATH

RUN apt-get update --fix-missing && \
    apt-get install -y wget bzip2 ca-certificates curl git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

SHELL [ "/bin/bash", "--login", "-c" ]

RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-4.5.11-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh && \
    /opt/conda/bin/conda clean -tipsy && \
    ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate base" >> ~/.bashrc


WORKDIR /bim2sim-coding

RUN conda config --add channels bim2sim
RUN conda config --add channels conda-forge
RUN conda create -n bim2sim3.9 -c conda-forge python=3.9
RUN	conda update -n base -c defaults conda

RUN conda activate bim2sim3.9 \
    && conda install -y --freeze-installed \
    -c bim2sim ${BIM2SIM_NAME}==${BIM2SIM_VERSION}${BIM2SIM_FLAG}  \
    && /opt/conda/bin/conda clean -afy \
	&& find /opt/conda/ -follow -type f -name '*.a' -delete \
	&& find /opt/conda/ -follow -type f -name '*.pyc' -delete \
	&& find /opt/conda/ -follow -type f -name '*.js.map' -delete \
