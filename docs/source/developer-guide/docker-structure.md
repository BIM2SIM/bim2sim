(docker_structure)=
# Docker image structure
We provide docker images for each python version that are based on micrmamba 
to install the required PythonOCC package which is not available through pypi.
For each python version we also provide an image with preinstalled EnergyPlus 
to run EP simulations directly. For Dymola we can't provide an image for public
because we use our own internal Dymola docker as base, but feel free to build
one on your own based on our Dockerfile.
