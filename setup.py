from setuptools import setup, find_packages

with open("README.md", 'r') as f:
    long_description = f.read()
with open("requirements.txt", 'r') as f:
    required = f.read().splitlines()
VERSION = "0.1.dev0"


setup(
    name='bim2sim',
    version=VERSION,
    description='Create simulation models from IFC files',
    license="???",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='BIM2SIM',
    author_email='???',
    url="https://github.com/BIM2SIM/bim2sim",
    packages=find_packages(include=['bim2sim.assets']),
    include_package_data=True,
    package_data={'': ['bim2sim/assets/*.*']},
    python_requires='>=3.8.*,<3.10.*',
    install_requires=[required
    ],  # external packages as dependencies TODO 'occ-utils'

    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    extras_require = {
                     'manual_install': ['ifcopenshell>=0.6', '', ],  # TODO occ-core

    },
    entry_points = {
        'console_scripts': [
            'bim2sim = bim2sim:main',
        ],
    }
)
