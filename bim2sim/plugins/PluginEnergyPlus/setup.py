from setuptools import setup

setup(
    name='bim2sim_energyplus',
    entry_points={
        'console_scripts': [
            'energyplus = bim2sim_energyplus:main',
        ],
    }
)
