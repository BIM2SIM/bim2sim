from bim2sim.elements import bps_elements, hvac_elements
from bim2sim.elements.base_elements import Material
from bim2sim.sim_settings import PlantSimSettings
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.sim_settings import \
    EnergyPlusSimSettings


class SpawnOfEnergyPlusSimSettings(EnergyPlusSimSettings, PlantSimSettings):
    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items, *hvac_elements.items,
                                  Material}
        # change defaults
        self.outer_heat_ports = True
