FROM condaforge/mambaforge:4.9.2-5 as conda
COPY docker/basic_build/conda-linux-64.lock .
RUN --mount=type=cache,target=/opt/conda/pkgs mamba create --copy -p /env --file conda-linux-64.lock && echo 4

RUN find -name '*.a' -delete   && \
  find -name '*.pyc' -delete && \
  find -name '*.js.map' -delete && \
  rm -rf /env/conda-meta && \
  rm -rf /env/include && \
# rm /env/lib/libpython3.9.so.1.0  && \
  find -name '__pycache__' -type d -exec rm -rf '{}' '+' && \
#  rm -rf /env/lib/python3.9/site-packages/pip /env/lib/python3.9/idlelib /env/lib/python3.9/ensurepip \
  rm -rf  /env/lib/python3.9/idlelib /env/lib/python3.9/ensurepip \
    /env/lib/libasan.so.5.0.0 \
    /env/lib/libtsan.so.0.0.0 \
    /env/lib/liblsan.so.0.0.0 \
    /env/lib/libubsan.so.1.0.0 \
    /env/bin/x86_64-conda-linux-gnu-ld \
    /env/bin/sqlite3 \
    /env/bin/openssl \
    /env/share/terminfo \
  rm -rf /env/lib/python3.9/site-packages/uvloop/loop.c \
  conda-linux-64.lock
#Distroless for execution

FROM debian:buster AS runtime
COPY --from=conda  /env /env
RUN ln -s /env/bin/python /usr/bin/python && \
    ln -s /env/bin/bim2sim /usr/bin/bim2sim  && \
    ln -s /env/bin/pip /usr/bin/pip

#ENTRYPOINT [ "bim2sim" ,"--version"]
