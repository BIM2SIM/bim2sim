

from bim2sim.plugin import Plugin
from bim2sim.workflow import PlantSimulation
from bim2sim.task import hvac, bps


class DummyPlugin(Plugin):
    name = 'dummy'
    default_workflow = PlantSimulation

    def run(self, playground):
        pass


class HVACPlugin(Plugin):
    name = 'hvac'
    elements = {}
    tasks = {hvac.Inspect}
