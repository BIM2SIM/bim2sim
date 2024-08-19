from bim2sim.elements import bps_elements, hvac_elements
from bim2sim.elements.base_elements import Material
from bim2sim.sim_settings import BooleanSetting, \
    PlantSimSettings
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.sim_settings import \
    EnergyPlusSimSettings


class SpawnOfEnergyPlusSimSettings(EnergyPlusSimSettings, PlantSimSettings):
    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items, *hvac_elements.items,
                                  Material}

    add_natural_ventilation = BooleanSetting(
        default=True,
        description='Add natural ventilation to the building. Natural '
                    'ventilation is not available when cooling is activated.',
        for_frontend=True
    )
