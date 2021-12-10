FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:cfd

WORKDIR /bim2sim

# Copy files
COPY . .


#WORKDIR /bim2sim/PluginCFD/bim2sim_cfd/assets/
#RUN git clone -b master https://github.com/bimworld/bim.git ifc2sb
#WORKDIR /bim2sim/PluginCFD/bim2sim_cfd/assets/ifc2sb
#RUN chmod +x IFC2SB
#RUN ./IFC2SB -h
#RUN pwd
