"""LCA plugin for bim2sim

Holds logic to export LCA relevant information and quantities based on ifc data
"""
import bim2sim.tasks.common.create_elements
import bim2sim.tasks.common.load_ifc
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginLCA.bim2sim_lca.task.export_lca import ExportLCA
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import LCAExportSettings


class PluginLCA(Plugin):
    name = 'LCA'
    sim_settings = LCAExportSettings
    default_tasks = [
        bim2sim.tasks.common.load_ifc.LoadIFC,
        bim2sim.tasks.common.create_elements.CreateElements,
        common.BindStoreys,
        bps.CreateSpaceBoundaries,
        ExportLCA,
    ]
