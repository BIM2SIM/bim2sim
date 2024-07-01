#!/bin/zsh

# build fresh envifonment (delete the old one)

micromamba deactivate
rm -r ~/micromamba/envs/b2s_pptoml
micromamba create -n b2s_pptoml python=3.10 -c conda-forge
micromamba activate b2s_pptoml


# instsll general dependencies
pip install -e '.'
python -m bim2sim -h
