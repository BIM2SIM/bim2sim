"""Template plugin for bim2sim

Holds a plugin with only base tasks mostly for demonstration.
"""
from bim2sim.plugins import Plugin
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import BuildingSimSettings


class PluginTemplate(Plugin):
    name = 'Template'
    sim_settings = BuildingSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElementsOnIfcTypes,
        bps.CreateSpaceBoundaries,
        bps.EnrichUseConditions,
        common.CreateRelations,
        common.Weather,
    ]
