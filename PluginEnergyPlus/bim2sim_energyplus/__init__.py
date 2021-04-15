'''EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
'''

def get_energyplus():
    from .energyplus import EnergyPlus
    return EnergyPlus

CONTEND = {'energyplus':get_energyplus}
