FROM continuumio/miniconda3



ARG BIM2SIM_NAME=bim2sim
ARG BIM2SIM_VERSION
ARG BIM2SIM_FLAG
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PATH /opt/conda/bin:$PATH

SHELL [ "/bin/bash", "--login", "-c" ]
WORKDIR /bim2sim-coding

RUN conda config --add channels bim2sim
RUN conda config --add channels conda-forge
RUN	conda update -n base -c defaults conda
RUN conda create -n bim2sim3.9 python=3.9

RUN conda activate bim2sim3.9 \
    && conda install -y  --freeze-installed\
    -c bim2sim ${BIM2SIM_NAME}==${BIM2SIM_VERSION}${BIM2SIM_FLAG}  \
    && /opt/conda/bin/conda clean -afy \
	&& find /opt/conda/ -follow -type f -name '*.a' -delete \
	&& find /opt/conda/ -follow -type f -name '*.pyc' -delete \
	&& find /opt/conda/ -follow -type f -name '*.js.map' -delete

#ENTRYPOINT [ "/bin/bash", "--login", "-c" , "conda activate env" , "bim2sim" ]
#ENTRYPOINT [ "/bin/bash", "--login", "-c" ,"conda activate env"  ]
