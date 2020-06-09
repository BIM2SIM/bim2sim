FROM registry.git.rwth-aachen.de/bim2sim/bim2sim-coding/environment:latest

WORKDIR /bim2sim

# Make RUN commands use `bash --login`:
SHELL ["/bin/sh", "--login", "-c"]

# Copy files
COPY . .

# The code to run when container is started:
RUN /bin/sh -c "source activate base"
CMD ["/bin/sh"]
