"""Template plugin for bim2sim.

Holds a plugin with only base tasks mostly for demonstration.
"""
from bim2sim.plugins import Plugin
from bim2sim.tasks import checks, common
from bim2sim.plugins.PluginIFCCheck.bim2sim_ifccheck.sim_settings import \
    CheckIFCSimSettings


class PluginIFCCheck(Plugin):
    """PluginIFCCheck template."""

    name = 'IFCCheck'
    sim_settings = CheckIFCSimSettings
    default_tasks = [
        common.LoadIFC,
        checks.CheckIfc,
    ]
