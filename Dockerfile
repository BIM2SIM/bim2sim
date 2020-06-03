FROM registry.git.rwth-aachen.de/bim2sim/bim2sim-coding .

#WORKDIR /app

# Make RUN commands use `bash --login`:
SHELL ["/bin/bash", "--login", "-c"]

#todo: pythonpath
# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "bim2sim_coding", "/bin/bash", "-c"]

# The code to run when container is started:
COPY . .
ENTRYPOINT ["conda", "run", "-n", "myenv", "python", "MainLib/bim2sim/__init__.py"]