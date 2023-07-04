# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
from sphinx.ext import autodoc

project = 'bim2sim'
copyright = '2023, David Jansen'
author = 'David Jansen'
release = '01.01.2023'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
# 'sphinx.ext.autodoc', 'sphinx_autodoc_sort' 'autoapi.extension',
extensions = ['sphinx.ext.autodoc', 'sphinx_rtd_theme'  ]
autodoc_member_order = 'bysource'
autoapi_options = {
    'members': 'all',
   'undoc-members': False,
    'show-inheritance': True
}





#autodoc_mock_imports = ['bim2sim.filter']
templates_path = ['_templates']
exclude_patterns = []

html_theme_options = {
    #'sidebar_width': '250px',
    'navigation_depth': 2,
}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

import os
import sphinx.util


directory = 'C:/05_bim2sim-coding/bim2sim-coding/bim2sim\source'

for root, dirs, files in os.walk(directory):
    for file in files:
        if file.endswith('.rst'):
            rst_file = os.path.join(root, file)
            with open(rst_file, 'a') as f:
                f.write('\n.. meta::\n   :maxdepth: 1\n')