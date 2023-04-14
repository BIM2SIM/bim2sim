#!/bin/bash
python -m pip install --no-deps --ignore-installed . &&
pip install https://files.pythonhosted.org/packages/e5/4f/21df008b7c3c2624f9b706f3deeab5d3f7a23d7ff364114eb693cdeaa5a5/deep-translator-1.9.2.tar.gz &&
pip install https://files.pythonhosted.org/packages/4e/40/9b56ca8d29453d0589a50b25184ca9d5c2d3de12af28e57e3efc02188a47/string_grouper-0.6.1-py3-none-any.whl &&
python -m pip install -r dependency_requirements.txt
