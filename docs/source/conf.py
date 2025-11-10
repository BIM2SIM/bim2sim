# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import logging

# Configure logging to suppress verbose MyST messages
def setup(app):
    # Suppress all loggers that start with "myst_parser"
    for logger_name in list(logging.root.manager.loggerDict.keys()):
        if logger_name.startswith('myst_parser'):
            logging.getLogger(logger_name).setLevel(logging.ERROR)

        # Also suppress markdown_it which is used by myst_parser
        if logger_name.startswith('markdown_it'):
            logging.getLogger(logger_name).setLevel(logging.ERROR)

# -- Project information -----------------------------------------------------

project = 'bim2sim '
copyright = '2022, RWTH Aachen University, EBC & E3D; ROM Technik GmbH'
# author = 'David Jansen (todo)'

# The full version, including alpha/beta/rc tags
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.ml#general-configuration

extensions = [
    #'m2r2',  # Enable .md files
    'myst_parser',
    'sphinx.ext.autodoc',
    'sphinxcontrib.mermaid',
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']
html_logo = "img/static/b2s_logo.png"
html_favicon = 'img/static/favicon.ico'
html_theme_options = {
    'logo_only': True,
    'display_version': False,
}
