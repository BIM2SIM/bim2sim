# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
from sphinx.ext import autodoc
import os
import sys
sys.path.insert(0, os.path.abspath('../../'))


project = 'bim2sim'
copyright = '2022, RWTH Aachen University, EBC & E3D; ROM Technik GmbH'
author = 'David Jansen'
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
# 'sphinx.ext.autodoc', 'sphinx_autodoc_sort' 'autoapi.extension',
#extensions = ['sphinx.ext.autodoc', 'sphinx_rtd_theme'  ]
extensions = [
    'myst_parser',
    'sphinx.ext.autodoc',
    # 'sphinx.ext.autosummary',
    'sphinx.ext.napoleon',
    'sphinx.ext.mathjax',
    'sphinx.ext.doctest',
    # 'sphinx.ext.coverage',
    'sphinx_autodoc_typehints',
    'sphinxcontrib.mermaid'
]


# autosummary_generate = True
doctest_path = [os.path.abspath('../../bim2sim/')]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match_graph files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []
#automodapi_exclude_modules = ['bim2sim.submodules']

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
html_logo = "img/static/b2s_logo.png"
html_theme_options = {
    'logo_only': True,
    'display_version': False,
}


