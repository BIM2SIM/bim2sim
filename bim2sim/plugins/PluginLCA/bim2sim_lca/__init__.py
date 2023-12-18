"""LCA plugin for bim2sim

Holds logic to export LCA relevant information and quantities based on ifc data
"""
from bim2sim.plugins import Plugin
import bim2sim.plugins.PluginLCA.bim2sim_lca.task as lca
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import LCAExportSettings


class PluginLCA(Plugin):
    name = 'LCA'
    sim_settings = LCAExportSettings

    default_tasks = [
        common.LoadIFC,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.FilterTZ,
        bps.ProcessSlabsRoofs,
        common.BindStoreys,
        #bps.VerifyLayersMaterials,
        #bps.EnrichMaterial,
        # bps.EnrichUseConditions, # TODO use when starting to use zone grouping
        #lca.ExportLCABuilding,
<<<<<<< HEAD
        bps.VerifyLayersMaterials,
        bps.EnrichMaterial,
        #bps.DisaggregationCreation,
        #bps.CombineThermalZones,
        lca.CreateBuildingGraph,
        #lca.CreateHeatingTreeBase,
        #lca.CreateHeatingTreeElements,
=======
        # bps.DisaggregationCreation, # TODO use when starting to use zone grouping
        # bps.CombineThermalZones, # TODO use when starting to use zone grouping
        # lca.CreateBuildingGraph,
        # lca.CreateHeatingTreeBase,
        # lca.CreateHeatingTreeElements,
>>>>>>> 82d84d4e58d970b8b07dd5cfc726188c01bdd303
        #lca.CalcHeatingQuantities,
        #

        #lca.ExportLCAHeating,

    ]
