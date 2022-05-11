"""CFD plugin for bim2sim

Prepares ifc files for CFD simulation
"""
from bim2sim.plugins import Plugin
from bim2sim.workflow import CFDWorkflowDummy

from task.ifc2cfd import RunIFC2CFD


class PluginCFD(Plugin):
    name = 'CFD'

    default_workflow = CFDWorkflowDummy
    elements = {}
    default_tasks = [
        RunIFC2CFD,
    ]
