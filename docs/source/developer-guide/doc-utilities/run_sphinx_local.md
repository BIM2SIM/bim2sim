# Run Sphinx local

In the bim2sim project [Sphinx](https://www.sphinx-doc.org) is used to generate
the documentation. The documentation is generate via the CI.
But to extend or adapt the documentation it is very useful to run the documentation generation locally. Following it is shown how to do that.

First install the following python packages.
```shell
 pip install sphinx==6.2.1 anybadge m2r2 sphinx-material autodoc_pydantic sphinx-rtd-theme
 pip install myst_parser
 pip install sphinx_autodoc_typehints
 pip install sphinxcontrib.mermaid
```

#TODO: add these dependencies to the pyproject.toml (in docu) and adapt this guide here.

After that, switch in to the docs folder of the bim2sim repo.
```shell
cd bim2sim-Root/bim2sim/docs
```

Next, regenerate the description of the python code (classes/functions) 
For bim2sim itself:
```shell
sphinx-apidoc -M -o source/code ../bim2sim
```

And for documentation utilizes:
```shell
sphinx-apidoc -M -o source/code utilities
```

Next, delete the existing html-files (needed to prevent strange behaviour)

```shell
make clean
```

Next, generate fresh html-files

```shell
make html 
```

Now, the html based documentation is available. Switch into the folder and open the file index.html.
```shell
cd build/html
```
Don't run the command "sphinx-quickstart", because this command overwrites the configuration of the bim2sim documentation.

## Troubleshooting
If there are problems regarding the generated code documentation. Please delete the folder ../source/code (in docs folder) and regenerate the code documentation (see above).
```shell
rm -r source/code
```
