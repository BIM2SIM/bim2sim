from setuptools import setup, find_packages
import glob


data_files = []
directories = glob.glob('bim2sim\\assets\\')
for directory in directories:
    files = glob.glob(directory + '*')
    data_files.append((directory, files))

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name='bim2sim',
    version='0.1.dev0',
    description='Create simulation models from IFC files',
    license="???",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='BIM2SIM',
    author_email='???',
    url="???",
    packages=find_packages() + ['bim2sim.assets'],
    include_package_data=True,
    data_files=data_files,
    # package_data={'': ['assets/*.*']},
    python_requires='>=3.9.0',
    install_requires=[
        'docopt', 'numpy', 'python-dateutil',
        'mako', 'networkx>=2.2', 'pint', 'pandas',
        'deep_translator', 'matplotlib'
    ],  # external packages as dependencies
    extras_require={
        'manual_install': ['ifcopenshell>=0.6'],
        'plotting': ['matplotlib'],
        'communication': ['rpyc'],
    },
    entry_points={
        'console_scripts': [
            'bim2sim = bim2sim:main',
        ],
    }
)
