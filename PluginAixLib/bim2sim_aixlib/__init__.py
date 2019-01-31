'''EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
'''

def get_aixlib():
    from .aixlib import AixLib
    return AixLib

CONTEND = {'aixlib':get_aixlib}
