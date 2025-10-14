# Image with Dymola required to test TEASER plugin

ARG PYTHON_VERSION=3.11
ARG FROM_BUILD_TAG=Dymola_2022
# bring in the micromamba image so we can copy files from it
FROM mambaorg/micromamba:2.0.2 as micromamba

# This is the image we are going add micromaba to:
FROM registry.git.rwth-aachen.de/ebc/ebc_intern/dymola-docker:${FROM_BUILD_TAG}

# Redeclare the ARG after FROM
ARG PYTHON_VERSION

USER root

# Install CA certificates
RUN apt-get update && apt-get install -y ca-certificates && update-ca-certificates

# if your image defaults to a non-root user, then you may want to make the
# next 3 ARG commands match the values in your image. You can get the values
# by running: docker run --rm -it my/image id -a
ARG MAMBA_USER=mambauser
ARG MAMBA_USER_ID=57439
ARG MAMBA_USER_GID=57439
ENV MAMBA_USER=$MAMBA_USER
ENV MAMBA_ROOT_PREFIX="/opt/conda"
ENV MAMBA_EXE="/bin/micromamba"

# Add the DYMOLA_RUNTIME_LICENSE environment variable
ENV DYMOLA_RUNTIME_LICENSE="ANY 50064@license2.rz.rwth-aachen.de"

COPY --from=micromamba "$MAMBA_EXE" "$MAMBA_EXE"
COPY --from=micromamba /usr/local/bin/_activate_current_env.sh /usr/local/bin/_activate_current_env.sh
COPY --from=micromamba /usr/local/bin/_dockerfile_shell.sh /usr/local/bin/_dockerfile_shell.sh
COPY --from=micromamba /usr/local/bin/_entrypoint.sh /usr/local/bin/_entrypoint.sh
COPY --from=micromamba /usr/local/bin/_dockerfile_initialize_user_accounts.sh /usr/local/bin/_dockerfile_initialize_user_accounts.sh
COPY --from=micromamba /usr/local/bin/_dockerfile_setup_root_prefix.sh /usr/local/bin/_dockerfile_setup_root_prefix.sh

RUN /usr/local/bin/_dockerfile_initialize_user_accounts.sh && \
    /usr/local/bin/_dockerfile_setup_root_prefix.sh

USER $MAMBA_USER

SHELL ["/usr/local/bin/_dockerfile_shell.sh"]

ENTRYPOINT ["/usr/local/bin/_entrypoint.sh"]
# Optional: if you want to customize the ENTRYPOINT and have a conda
# environment activated, then do this:
# ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "my_entrypoint_program"]

# You can modify the CMD statement as needed....
CMD ["/bin/bash"]

# Set the Python version as an environment variable
ENV PYTHON_VERSION=${PYTHON_VERSION}

# Install specific python version and python occ to save time
RUN micromamba install -y -n base -c conda-forge python=${PYTHON_VERSION} pythonocc-core=7.7.0 pip gcc git --retry-clean-cache && \
    micromamba clean --all --yes

USER $MAMBA_USER
WORKDIR /home/$MAMBA_USER

SHELL ["/usr/local/bin/_dockerfile_shell.sh"]

ENTRYPOINT ["/usr/local/bin/_entrypoint.sh"]

CMD ["/bin/bash"]

ENV PIP_DEFAULT_TIMEOUT=500

# Add .local/bin to PATH
ENV PATH=/home/$MAMBA_USER/.local/bin:$PATH