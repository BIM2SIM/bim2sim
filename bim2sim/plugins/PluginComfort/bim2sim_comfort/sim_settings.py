from pathlib import Path

from bim2sim.sim_settings import PathSetting, BooleanSetting
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.sim_settings import \
    EnergyPlusSimSettings


class ComfortSimSettings(EnergyPlusSimSettings):
    def __init__(self):
        super().__init__()

    prj_use_conditions = PathSetting(
        default=Path(__file__).parent / 'assets/UseConditionsComfort.json',
        description="Path to a custom UseConditions.json for the specific "
                    "comfort application. These use conditions have "
                    "comfort-based use conditions as a default.",
        for_frontend=True
    )
    use_dynamic_clothing = BooleanSetting(
        default=False,
        description='Use dynamic clothing according to ASHRAE 55 standard.',
        for_frontend=True
    )
    rename_plot_keys = BooleanSetting(
        default=False,
        description='Rename room names for plot results',
        for_frontend=True
    )
    rename_plot_keys_path = PathSetting(
        default=Path(__file__).parent / 'assets/rename_plot_keys.json',
        description="Path for renaming the zone keys for plot results. Path "
                    "to a json file with pairs of current keys and new keys. ",
        for_frontend=True
    )
    comfort_occupancy_weighting = BooleanSetting(
        default=False, description='Weight the comfort rating by occupancy '
                                   'schedules.'
    )
