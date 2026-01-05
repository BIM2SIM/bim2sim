from bim2sim.elements import bps_elements as bps_elements
from bim2sim.elements.base_elements import Material
from bim2sim.sim_settings import BuildingSimSettings, BooleanSetting



class VentilationSystemSimSettings(BuildingSimSettings):

    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items,
                                      Material}

    export_graphs = BooleanSetting(
        default=True,
        description="Export the figures of the ventilation graphs")



