"""CFD plugin for bim2sim

Prepares ifc files for CFD simulation
"""
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginCFD.bim2sim_cfd.task.ifc2cfd import RunIFC2CFD
from bim2sim.sim_settings import BaseSimSettings


class PluginCFD(Plugin):
    name = 'CFD'

    sim_settings = BaseSimSettings
    default_tasks = [
        RunIFC2CFD,
    ]
