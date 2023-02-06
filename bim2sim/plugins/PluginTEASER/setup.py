from setuptools import setup, find_packages
import os
with open(f'..{os.sep}..{os.sep}..{os.sep}README.md', 'r') as f:
    long_description = f.read()
with open(f'requirements.txt', 'r') as f:
    required = f.read().splitlines()
with open(f'..{os.sep}..{os.sep}..{os.sep}VERSION', 'r') as f:
    version = f.read()


def copy_non_code_file(non_code_dir, not_include):
    path_file_dict = []
    for subdir, dirs, files in os.walk(non_code_dir):
        file_list = []
        for file in files:
            filepath = subdir + os.sep + file
            file_list.append(filepath)
            for end in not_include:
                if filepath.endswith(end):
                    file_list.remove(filepath)
        if len(file_list) > 0:
            path_file_dict.append((subdir, file_list))
        continue
    return path_file_dict

setup(
    name='bim2sim_teaser',
    version=version,
    description='Create simulation models from IFC files',
    license="LICENSE",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='BIM2SIM',
    author_email='david.jansen@eonerc.rwth-aachen.de',
    url="https://github.com/BIM2SIM/bim2sim",
    packages=find_packages(include=['*']),
    include_package_data=True,
    data_files = copy_non_code_file(non_code_dir=f'{os.sep}{os.sep}', not_include=[".py", ".Dockerfile"]),
    python_requires='>=3.8.*,<3.10.*',
    install_requires=[required],
    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)