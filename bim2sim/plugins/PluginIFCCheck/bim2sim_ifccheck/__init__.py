"""Template plugin for bim2sim

Holds a plugin with only base tasks mostly for demonstration.
"""
from bim2sim.plugins import Plugin
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import BuildingSimSettings
from bim2sim.plugins.PluginIFCCheck.bim2sim_ifccheck.sim_settings import \
    CheckIFCSimSettings

class PluginIFCCheck(Plugin):
    name = 'IFCCheck'
    sim_settings = CheckIFCSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfcIds,
        # common.CreateElementsOnIfcTypes,
        # bps.CreateSpaceBoundaries,
        # bps.EnrichUseConditions,
        # common.CreateRelations,
        # common.Weather,
    ]
