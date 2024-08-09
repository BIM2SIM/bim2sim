"""Template plugin for bim2sim

Holds a plugin with only base tasks mostly for demonstration.
"""
from bim2sim.plugins import Plugin
from bim2sim.tasks import common, bps
from bim2sim.plugins.PluginTEASER.bim2sim_teaser.sim_settings import \
    TEASERSimSettings


class PluginTemplate(Plugin):
    name = 'Template'
    # TODO BuildingSimSetting don't work due to issues with #511 and #583
    sim_settings = TEASERSimSettings
    # sim_settings = BuildingSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElementsOnIfcTypes,
        bps.CreateSpaceBoundaries,
        bps.EnrichUseConditions,
        common.CreateRelations,
        common.Weather,
    ]
