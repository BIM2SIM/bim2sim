from bim2sim.plugin import Plugin
from bim2sim.workflow import CFDWorkflowDummy
from bim2sim_cfd.task import ifc2cfd


class PluginCFD(Plugin):
    name = 'CFD'

    default_workflow = CFDWorkflowDummy
    elements = {}

    default_tasks = [
        ifc2cfd,
    ]

