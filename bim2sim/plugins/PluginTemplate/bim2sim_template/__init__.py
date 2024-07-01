"""Template plugin for bim2sim

Holds a plugin with only base tasks mostly for demonstration.
"""
from bim2sim.plugins import Plugin
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import TEASERSimSettings
from bim2sim.sim_settings import BuildingSimSettings


class PluginTemplate(Plugin):
    name = 'Template'
    # TODO BuildingSimSetting don't work due to issues with #511 and #583
    sim_settings = TEASERSimSettings
    # sim_settings = BuildingSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElementsOnIfcTypes,
        # bps.ProcessSlabsRoofs,
        bps.CreateSpaceBoundaries,
        bps.EnrichUseConditions,
        common.BindStoreys,
        common.Weather,
    ]
