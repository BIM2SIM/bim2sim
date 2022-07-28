########################################################
# OS
FROM ubuntu:20.04

#  $ docker build . -t continuumio/miniconda3:latest -t continuumio/miniconda3:4.5.11
#  $ docker run --rm -it continuumio/miniconda3:latest /bin/bash
#  $ docker push continuumio/miniconda3:latest
#  $ docker push continuumio/miniconda3:4.5.11

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

# Copy files
COPY ./requirements.txt .

RUN 	conda create -n env python=3.7
RUN		conda update -n base -c defaults conda
RUN 	echo "source activate env" > ~/.bashrc
ENV 	PATH /opt/conda/envs/env/bin:$PATH
SHELL 	["conda", "run", "-n", "env", "/bin/bash", "-c"]

# install needed packages

RUN pip install -r ./requirements.txt

# install needed packages

## install pythonocc via conda
RUN /opt/conda/bin/conda install --yes --freeze-installed \
	    -c dlr-sc pythonocc-core=7.4.1 \
	    nomkl \
	&& /opt/conda/bin/conda clean -afy \
	&& find /opt/conda/ -follow -type f -name '*.a' -delete \
	&& find /opt/conda/ -follow -type f -name '*.pyc' -delete \
	&& find /opt/conda/ -follow -type f -name '*.js.map' -delete

## install ifcopenshell via existing file
RUN wget -O /tmp/ifcopenshell.zip https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-`python3 -c 'import sys;print("".join(map(str, sys.version_info[0:2])) \
&& unzip '/tmp/ifcopenshell.zip' -d /opt/conda/envs/env/lib/python3.7/site-packages/ && rm /tmp/ifcopenshell.zip || true ;


## install occ utils via existing file 
RUN wget -O /tmp/occ-utils.zip https://github.com/tpaviot/pythonocc-utils/archive/refs/heads/master.zip \
&& unzip '/tmp/occ-utils.zip' -d /tmp/occ-utils || true \
&& mv /tmp/occ-utils/pythonocc-utils-master/OCCUtils /opt/conda/envs/env/lib/python3.7/site-packages/ ;


# Set Pythonpath
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginEnergyPlus"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginCFD"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginAixLib"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginHKESim"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginTEASER"

########################################################
