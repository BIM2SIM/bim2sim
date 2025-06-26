# General hints and howtos
Here you find some hints or howtos for using components of the 'bim2sim' framework, like
running examples.
(jupyter-notebook)=
## Hints Jupyter Notebook
For a more interactive experience, you can run the Jupyter Notebook. To do this, you need to configure a kernel based on our bim2sim Python environment. Run the following commands:
```shell
  pip install notebook
  pip install ipykernel
  python3 -m ipykernel install --user --name=bim2sim-kernel
  cd [path of the notebook]
  jupyter notebook
```
Now you can run Jupyter Notebook and switch to the configured kernel, which can be selected from the top-right corner.
More information about Jupyter notebook you can find here: [jupyter](https://jupyter.org/).
