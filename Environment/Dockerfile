FROM continuumio/miniconda3

#WORKDIR /app

# Make RUN commands use `bash --login`:
SHELL ["/bin/bash", "--login", "-c"]

RUN conda update -y conda
# Create the environment:
COPY environment.yml .
RUN conda env create -f environment.yml

