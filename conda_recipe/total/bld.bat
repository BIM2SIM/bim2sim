@echo on
conda install conda-bld/bim2sim/linux-64/bim2sim-*
conda install conda-bld/bim2sim_cfd/linux-64/bim2sim_cfd-*
conda install conda-bld/bim2sim_aixlib/linux-64/bim2sim_aixlib-*
conda install conda-bld/bim2sim_energyplus/linux-64/bim2sim_energyplus-*
conda install conda-bld/bim2sim_lca/linux-64/bim2sim_lca-*
conda install conda-bld/bim2sim_teaser/linux-64/bim2sim_teaser-*
IF %ERRORLEVEL% NEQ 0 exit 1