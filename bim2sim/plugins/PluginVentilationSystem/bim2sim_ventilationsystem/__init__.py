"""LCA plugin for bim2sim

Holds logic to create an optimal ventilation system based on ifc data
"""
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginVentilationSystem.bim2sim_ventilationsystem.task import (CalcAirFlow, DesignExaustLCA, DesignSupplyLCA,
                                                        DesignVentilationSystem)
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import VentilationSystemSimSettings


class PluginVentilationSystem(Plugin):
    name = 'VentilationSystem'
    sim_settings = VentilationSystemSimSettings

    default_tasks = [
        common.LoadIFC,
        common.CreateElementsOnIfcTypes,
        common.BindStoreys,
        bps.CreateSpaceBoundaries,
        # bps.Prepare,
        bps.EnrichUseConditions,
        # bps.VerifyLayersMaterials,
        # bps.EnrichMaterial,
        CalcAirFlow,
        DesignSupplyLCA,
        DesignExaustLCA,
        DesignVentilationSystem,
    ]
