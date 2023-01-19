from setuptools import setup, find_packages
import os
with open("README.md", 'r') as f:
    long_description = f.read()
with open("requirements.txt", 'r') as f:
    required = f.read().splitlines()
VERSION = "0.1.0"

def copy_non_code_file(non_code_dir, not_include):
    path_file_dict = []
    for subdir, dirs, files in os.walk(non_code_dir):
        file_list = []
        for file in files:
            filepath = subdir + os.sep + file
            print(filepath)
            file_list.append(filepath)
            for end in not_include:
                if filepath.endswith(end):
                    file_list.remove(filepath)
        if len(file_list) > 0:
            path_file_dict.append((subdir, file_list))
        continue
    return path_file_dict

setup(
    name='bim2sim',
    version=VERSION,
    description='Create simulation models from IFC files',
    license="LICENSE",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='BIM2SIM',
    author_email='david.jansen@eonerc.rwth-aachen.de',
    url="https://github.com/BIM2SIM/bim2sim",
    packages=find_packages(include=['bim2sim*']),
    include_package_data=True,
    data_files = copy_non_code_file(non_code_dir=f'bim2sim{os.sep}{os.sep}', not_include=[".py", ".Dockerfile"]),
    package_data={'': ['bim2sim/assets/*.*']},
    python_requires='>=3.8.*,<3.10.*',
    install_requires=[required],
    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    extras_require = {
                     'manual_install': ['ifcopenshell>=0.6', 'pythonocc-core==7.6.2'],
    },
    entry_points = {
        'console_scripts': [
            'bim2sim = bim2sim:main',
        ],
    }
)
