"""Hydraulic system plugin for bim2sim

Holds logic to create a hydraulic system based on ifc data
"""
from bim2sim.plugins import Plugin
from bim2sim_hydraulicsystem.task.get_building_geometry import (
    GetBuildingGeometry)
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import HydraulicSystemSimSettings


class PluginHydraulicSystem(Plugin):
    name = 'HydraulicSystem'
    sim_settings = HydraulicSystemSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CreateElementsOnIfcTypes,
        common.BindStoreys,
        bps.CreateSpaceBoundaries,
        GetBuildingGeometry,
    ]
