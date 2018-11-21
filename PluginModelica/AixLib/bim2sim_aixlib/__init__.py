'''EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
'''

from .aixlib import EnergyPlus

contend = {'energyplus':EnergyPlus}
