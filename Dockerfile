FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:development

WORKDIR /bim2sim-coding

# Make RUN commands use `bash --login`:
# SHELL ["/bin/sh", "--login", "-c"]

# Copy files
COPY . .

# The code to run when container is started:
# RUN /bin/sh -c "source activate base"
# CMD ["/bin/sh"] 
