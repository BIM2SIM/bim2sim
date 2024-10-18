from bim2sim.sim_settings import PlantSimSettings, PathSetting


class AixLibSimSettings(PlantSimSettings):
    """Defines simulation settings for AixLib Plugin.

    This class defines the simulation settings for the AixLib Plugin. It
    inherits all choices from the PlantSimSettings settings. AixLib
    specific settings are added here.
    """

    path_aixlib = PathSetting(
        default=None,
        description='Path to the local AixLib`s repository. This needs to '
                    'point to the root level package.mo file. If not'
                    ' provided, the version for regression testing will be '
                    'used if it was already downloaded using the '
                    'prepare_regression_tests.py script.',
        for_frontend=False,
        mandatory=False
    )