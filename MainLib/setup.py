from setuptools import setup

setup(
    name='bim2sim',
    entry_points={
        'console_scripts': [
            'bim2sim = bim2sim:main',
        ],
    }
)
