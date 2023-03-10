FROM registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/environment:cfd

WORKDIR /bim2sim-coding

# Copy files
COPY . .

#WORKDIR /bim2sim/PluginCFD/bim2sim_cfd/assets/
#RUN git clone -b master https://github.com/bimworld/bim.git ifc2sb
#WORKDIR /bim2sim/PluginCFD/bim2sim_cfd/assets/ifc2sb
#RUN chmod +x IFC2SB
#RUN ./IFC2SB -h
#RUN pwd
