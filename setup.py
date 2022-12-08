from setuptools import setup, find_packages

with open("README.md", 'r') as f:
    long_description = f.read()
with open("requirements.txt", 'r') as f:
    required = f.read().splitlines()
VERSION = "0.1.0"


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
    data_files = [('bim2sim/assets/enrichment/hvac', ['bim2sim/assets/enrichment/hvac/TypeBuildingElements.json']),
                  ('bim2sim/assets/enrichment/material', ['bim2sim/assets/enrichment/material/MaterialTemplates.json',
                                                             'bim2sim/assets/enrichment/material/TypeBuildingElements.json']),
                  ('bim2sim/assets/enrichment/usage', ['bim2sim/assets/enrichment/usage/commonUsages.json',
                                                          'bim2sim/assets/enrichment/usage/customUsages.json',
                                                          'bim2sim/assets/enrichment/usage/customUsagesAC20-FZK-Haus_with_SB55.json',
                                                          'bim2sim/assets/enrichment/usage/customUsagesAC20-Institute-Var-2_with_SB-1-0.json',
                                                          'bim2sim/assets/enrichment/usage/customUsagesFM_ARC_DigitalHub_fixed002.json',
                                                          'bim2sim/assets/enrichment/usage/customUsagesFM_ARC_DigitalHub_with_SB_neu.json',
                                                          'bim2sim/assets/enrichment/usage/customUsagesAC20-Institute-Var-2_with_SB-1-0.json',
                                                          'bim2sim/assets/enrichment/usage/customUsagesFM_ARC_DigitalHub_fixed002.json',
                                                          'bim2sim/assets/enrichment/usage/customUsagesFM_ARC_DigitalHub_with_SB_neu.json',
                                                          'bim2sim/assets/enrichment/usage/customUsagesFM_ARC_DigitalHub_with_SB88.json',
                                                          'bim2sim/assets/enrichment/usage/customUsagesFM_ARC_DigitalHub_with_SB89.json',
                                                          'bim2sim/assets/enrichment/usage/customUsagesKIT-EDC_with_SB.json',
                                                          'bim2sim/assets/enrichment/usage/UseConditions.json',
                                                          'bim2sim/assets/enrichment/usage/UseConditionsFM_ARC_DigitalHub_fixed002.json',
                                                          'bim2sim/assets/enrichment/usage/UseConditionsFM_ARC_DigitalHub_with_SB_neu.json',
                                                          'bim2sim/assets/enrichment/usage/UseConditionsFM_ARC_DigitalHub_with_SB89.json']),
                  ('bim2sim/assets/finder', ['bim2sim/assets/finder/template_ArchiCAD.json',
                                               'bim2sim/assets/finder/template_Autodesk Revit.json',
                                               'bim2sim/assets/finder/template_LuArtX_Carf.json',
                                               'bim2sim/assets/finder/template_TRICAD-MS.json']),


                  ('bim2sim/assets/templates/check_ifc', ['bim2sim/assets/templates/check_ifc/inst_template',
                                                             'bim2sim/assets/templates/check_ifc/prop_template',
                                                             'bim2sim/assets/templates/check_ifc/summary_template']),
                  ('bim2sim/assets/templates/modelica', ['bim2sim/assets/templates/modelica/tmplModel.txt']),
                  ('bim2sim/assets/weatherfiles', ['bim2sim/assets/weatherfiles/DEU_NW_Aachen.105010_TMYx.epw',
                                                     'bim2sim/assets/weatherfiles/DEU_NW_Aachen.105010_TMYx.mos']),
                  ('bim2sim/assets/ifc_example_files', ['bim2sim/assets/ifc_example_files/AC20-FZK-Haus.ifc',
                                                          'bim2sim/assets/ifc_example_files/ERC_EBC_mainbuilding.ifc',
                                                          'bim2sim/assets/ifc_example_files/hvac_heating.ifc'  ])

                  ],

    package_data={'': ['bim2sim/assets/*.*']},
    python_requires='>=3.8.*,<3.10.*',
    install_requires=[required
    ],

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
