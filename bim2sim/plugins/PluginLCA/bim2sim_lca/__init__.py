﻿"""LCA plugin for bim2sim

Holds logic to export LCA relevant information and quantities based on ifc data
"""
from bim2sim.plugins import Plugin
from bim2sim.workflow import LCAExport
from bim2sim.kernel.element import Material
from bim2sim.kernel.elements import hvac as hvac_elements, bps as bps_elements
from bim2sim.task import common, lca, bps


class PluginLCA(Plugin):
    name = 'LCA'
    default_workflow = LCAExport
    elements = ({*hvac_elements.items} | {*bps_elements.items} | {Material})
    default_tasks = [
        common.LoadIFC,
        common.CreateElements,
        common.BindStoreys,
        bps.CreateSpaceBoundaries,
        lca.ExportLCA,
    ]
