"""TEASER plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""


def get_teaser():
    from .teaser import PluginTEASER
    return PluginTEASER


CONTEND = {'teaser':get_teaser}
