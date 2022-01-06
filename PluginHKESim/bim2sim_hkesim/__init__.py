'''HKESim plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
'''


def get_hkesim():
    from .hkesim import PluginHKESim
    return PluginHKESim

CONTEND = {'hkesim':get_hkesim}
