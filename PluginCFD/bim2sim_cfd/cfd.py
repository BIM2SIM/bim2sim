from bim2sim.plugin import Plugin
from bim2sim.workflow import CFDWorkflowDummy
from bim2sim_cfd import task


class PluginCFD(Plugin):
    name = 'CFD'

    default_workflow = CFDWorkflowDummy
    elements = {}
    default_tasks = [
        task.RunIFC2CFD,
    ]
