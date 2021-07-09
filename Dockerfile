FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:development

WORKDIR /bim2sim

# Make RUN commands use `bash --login`:
SHELL ["/bin/sh", "--login", "-c"]

# Copy files
COPY . .

# The code to run when container is started:
RUN /bin/sh -c "source activate base"
CMD ["/bin/sh"]
