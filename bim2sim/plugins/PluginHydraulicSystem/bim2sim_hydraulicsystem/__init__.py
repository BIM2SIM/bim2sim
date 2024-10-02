﻿"""Hydraulic system plugin for bim2sim

Holds logic to create a hydraulic system based on ifc data
"""
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginHydraulicSystem.bim2sim_hydraulicsystem.task import (GetIFCBuildingGeometry,
                                                                                CreateBuildingAndHeatingGraph,
                                                                                InterfaceToPluginTeaser,
                                                                                CalculateHydraulicSystem)
from bim2sim.tasks import common, bps
from bim2sim.plugins.PluginHydraulicSystem.bim2sim_hydraulicsystem.sim_settings import HydraulicSystemSimSettings


class PluginHydraulicSystem(Plugin):
    name = 'HydraulicSystem'
    sim_settings = HydraulicSystemSimSettings
    default_tasks = [
        common.LoadIFC,
        #common.DeserializeElements,
        common.CreateElementsOnIfcTypes,
        bps.CreateSpaceBoundaries,
        bps.AddSpaceBoundaries2B,
        bps.CorrectSpaceBoundaries,
        common.CreateRelations,
        bps.DisaggregationCreationAndTypeCheck,
        InterfaceToPluginTeaser,
        GetIFCBuildingGeometry,
        CreateBuildingAndHeatingGraph,
        CalculateHydraulicSystem,
    ]
