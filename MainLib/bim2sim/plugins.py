
from bim2sim.plugin import Plugin
from bim2sim.workflow import PlantSimulation


class DummyPlugin(Plugin):
    name = 'dummy'
    default_workflow = PlantSimulation

    def run(self, playground):
        pass
