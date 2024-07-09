"""Hydraulic system plugin for bim2sim

Holds logic to create an hydraulic system based on ifc data
"""
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginHydraulicSystem.bim2sim_HydraulicSystem.task import (GetBuildingGeometry)
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import HydraulicSystemSettings

class PluginHydraulicSystem(Plugin):
    name = 'HydraulicSystem'
    sim_settings = HydraulicSystemSettings

    default_tasks = [
        common.LoadIFC,
        common.CreateElements,
        common.BindStoreys,
        bps.CreateSpaceBoundaries,
        GetBuildingGeometry,
    ]
