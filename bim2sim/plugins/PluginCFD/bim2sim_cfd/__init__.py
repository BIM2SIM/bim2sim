"""CFD plugin for bim2sim

Prepares ifc files for CFD simulation
"""
from bim2sim.plugins import Plugin
from bim2sim.workflow import CFDWorkflow

from bim2sim.plugins.PluginCFD.bim2sim_cfd.task.ifc2cfd import RunIFC2CFD


class PluginCFD(Plugin):
    name = 'CFD'

    default_workflow = CFDWorkflow
    elements = {}
    default_tasks = [
        RunIFC2CFD,
    ]
