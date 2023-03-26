"""LCA plugin for bim2sim

Holds logic to export LCA relevant information and quantities based on ifc data
"""
from bim2sim.kernel.element import Material
from bim2sim.kernel.elements import hvac as hvac_elements, bps as bps_elements
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginLCA.bim2sim_lca.task.export_lca import ExportLCA
from bim2sim.task import common, bps
from bim2sim.workflow import LCAExport


class PluginLCA(Plugin):
    name = 'LCA'
    default_workflow = LCAExport
    elements = ({*hvac_elements.items} | {*bps_elements.items} | {Material})
    default_tasks = [
        common.LoadIFC,
        common.CreateElements,
        common.BindStoreys,
        bps.CreateSpaceBoundaries,
        ExportLCA,
        bps.VisualizeThermalZone
        # my task
        ]
