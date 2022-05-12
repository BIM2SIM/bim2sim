# Documentation

## Setup

Install requirements 
```
cd docs
pip install -r requirements.txt
```

### Build
To build the documentation, first update API documentation by:
```
sphinx-apidoc -o source/code/ ../bim2sim
```
THis is only required if something on the project structure changed.

Then build the html files
```
make html
```

Or start the dev server to automatically rebuild documentation on changes
```
cd docs/source
python run_livereload.py
```
The dev server also notifies your browser to reload on changes.

## Writing documentation

Both Markdown (.md) and reStructuredText (.rst) are supported. 