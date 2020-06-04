FROM registry.git.rwth-aachen.de/bim2sim/bim2sim-coding/environment:latest

WORKDIR /bim2sim

# Make RUN commands use `bash --login`:
SHELL ["/bin/bash", "--login", "-c"]


# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "bim2sim_coding", "/bin/bash", "-c"]

# Copy files
COPY . .

# Set Pythonpath
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim/MainLib"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim/PluginEnergyPlus"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim/PluginCFD"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim/PluginAixLib"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim/PluginHKESIM"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim/PluginTEASER"

# The code to run when container is started:
ENTRYPOINT ["conda", "run", "-n", "bim2sim_coding", "python", "MainLib/bim2sim/__init__.py"]