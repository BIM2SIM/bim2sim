from bim2sim.plugin import Plugin
from bim2sim.workflow import CFDWorkflowDummy
from bim2sim_cfd.task.ifc2cfd import RunIFC2CFD


class PluginCFD(Plugin):
    name = 'CFD'

    default_workflow = CFDWorkflowDummy
    elements = {}
    default_tasks = [
        RunIFC2CFD,
    ]
