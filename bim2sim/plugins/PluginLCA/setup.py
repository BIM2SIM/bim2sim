from setuptools import setup, find_packages
import os
from pathlib import Path
with open(f'README.md', 'r') as f:
    long_description = f.read()
with open(f'requirements.txt', 'r') as f:
    required = f.read().splitlines()
version = "1.0.0"


def copy_non_code_file(non_code_dir, not_include):
    path_file_dict = {}
    _dir = non_code_dir.replace(".", os.sep)
    for subdir, dirs, files in os.walk(_dir):
        file_list = []
        for file in files:
            filepath = Path(subdir, file)
            file_name = Path(filepath.name)
            file_list.append(str(file_name))
            for end in not_include:
                if file_name.suffix == end:
                    file_list.remove(str(file_name))
        if len(file_list) > 0:
            path_file_dict[str(filepath.parent).replace(os.sep, ".")] = file_list
        continue
    return path_file_dict

setup(
    name='bim2sim_lca',
    version=version,
    description='Create simulation models from IFC files',
    license="LICENSE",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='BIM2SIM',
    author_email='david.jansen@eonerc.rwth-aachen.de',
    url="https://github.com/BIM2SIM/bim2sim",
    packages=find_packages(include=['bim2sim_lca*']),
    include_package_data=True,
    package_data=copy_non_code_file(non_code_dir=f'bim2sim_lca',
                                    not_include=[".py", ".Dockerfile", ".pyc"]),
    python_requires='>=3.8.*,<3.10.*',
    install_requires=[required],
    #dependency_links=['https://github.com/NREL/EnergyPlusRegressionTool/archive/refs/tags/v1.9.6.zip'],

    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)