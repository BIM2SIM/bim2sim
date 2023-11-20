"""Template plugin for bim2sim

Holds a plugin with only base tasks mostly for demonstration.
"""
from bim2sim.plugins import Plugin
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import BaseSimSettings


class PluginTemplate(Plugin):
    name = 'Template'
    sim_settings = BaseSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        common.BindStoreys,
        common.Weather,
    ]
