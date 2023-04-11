#!/bin/bash
python -m pip install --no-deps --ignore-installed .
pip install -r requirements.txt
pip install -r dependency_requirements.txt
