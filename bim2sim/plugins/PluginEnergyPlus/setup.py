from setuptools import setup, find_packages

setup(
    name='bim2sim_energyplus',
    packages=find_packages(include=['bim2sim_energyplus', 'bim2sim_energyplus.*']),
    entry_points={
        'console_scripts': [
            'energyplus = bim2sim_energyplus:main',
        ],
    }
)

