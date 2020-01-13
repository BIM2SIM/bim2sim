'''CFD plugin for bim2sim

Prepares ifc files for CFD simulation
'''

def get_cfd():
    from .cfd import CFDManager
    return CFDManager

CONTEND = {'cfd':get_cfd}
