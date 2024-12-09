"""LCA plugin for bim2sim

Holds logic to export LCA relevant information and quantities based on ifc data
"""
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginLCA.bim2sim_lca.task import (CalculateEmissionBuilding, LoadMaterialEmissionParameter,
                                                        CalculateEmissionHydraulicSystem, CalculateEmissionVentilationSystem,
                                                        PlotHydraulicVentilationGraphs)
from bim2sim.tasks import common, bps
from bim2sim.plugins.PluginLCA.bim2sim_lca.sim_settings import \
    LCAExportSettings


class PluginLCA(Plugin):
    name = 'LCA'
    sim_settings = LCAExportSettings

    default_tasks = [
        common.LoadIFC,
        common.CreateElementsOnIfcTypes,
        common.CreateRelations,
        bps.EnrichMaterial,
        #PlotHydraulicVentilationGraphs,
        LoadMaterialEmissionParameter,
        CalculateEmissionBuilding,
        CalculateEmissionHydraulicSystem,
        CalculateEmissionVentilationSystem
    ]
