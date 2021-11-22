FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:ubuntu_base

WORKDIR /bim2sim

# Make RUN commands use `bash --login`:
# SHELL ["/bin/sh", "--login", "-c"]

# Copy files
COPY . .


WORKDIR /bim2sim/PluginCFD/bim2sim_cfd/assets
RUN git clone -b master https://github.com/bimworld/bim.git ifc2sb
WORKDIR /bim2sim/PluginCFD/bim2sim_cfd/assets/ifc2sb
RUN chmod +x IFC2SB

# The code to run when container is started:
# RUN /bin/sh -c "source activate base"
# CMD ["/bin/sh"] 
