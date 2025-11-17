# Run Sphinx local

In the bim2sim project [Sphinx](https://www.sphinx-doc.org) is used to generate
the documentation. The documentation is generate via the CI.
But to extend or adapt the documentation it is very useful to run the documentation generation locally. Following it is shown how to do that.

First install the following python packages based on the pyproject.toml.
Therefore you need to switch into the root directory of the bim2sim repo, which includes the project.toml file. 
```shell
  cd [bim2sim-Root]/bim2sim/
  pip install -e '.[docu]'
```

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

### Warning: import failures - No module named XXXX
Please install the dependencies for all plugins. (see
[TEASER](HowtoInstallTeaser), [EnergyPlus](HowtoInstallEP), [LCA](HowtoInstallLCA),
[AixLib](HowtoInstallAixLib) and [HKESim](HowtoInstallHKESim))

### Problems with code documentation
If there are problems regarding the generated code documentation. Please delete the folder ../source/code (in docs folder) and regenerate the code documentation (see above).
```shell
rm -r source/code
```
