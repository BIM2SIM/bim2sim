"""Template plugin for bim2sim

Holds a plugin with only base tasks mostly for demonstration.
"""
from bim2sim.plugins import Plugin
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import TEASERSimSettings


class PluginTemplate(Plugin):
    name = 'Template'
    sim_settings = TEASERSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElements,
        bps.FilterTZ,
        bps.ProcessSlabsRoofs,
        bps.CreateSpaceBoundaries,
        bps.EnrichUseConditions,
        common.BindStoreys,
        common.Weather,
    ]
