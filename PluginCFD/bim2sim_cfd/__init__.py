'''CFD plugin for bim2sim

Prepares ifc files for CFD simulation
'''

def get_cfd():
    from .cfd import PluginCFD
    return PluginCFD

CONTEND = {'cfd':get_cfd}
