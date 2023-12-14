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
        common.BindStoreys,
        #bps.VerifyLayersMaterials,
        #bps.EnrichMaterial,
        #lca.ExportLCABuilding,
        lca.CreateBuildingGraph,
        #lca.CreateHeatingTreeBase,
        #lca.CreateHeatingTreeElements,
        #lca.CalcHeatingQuantities,
        #

        #lca.ExportLCAHeating,

    ]
