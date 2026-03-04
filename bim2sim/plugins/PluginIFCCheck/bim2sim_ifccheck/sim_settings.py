from bim2sim.sim_settings import BaseSimSettings, PathSetting
# from bim2sim.utilities.types import LOD, ZoningCriteria


class CheckIFCSimSettings(BaseSimSettings):
    """Defines simulation settings for Check IFC Plugin.

    This class defines the "simulation" settings for the Check IFC Plugin. It
    inherits all choices from the BaseSimSettings settings. Specific settings
    for the IFC Check are added here.

    """

    ids_file_path = PathSetting(
        value=None,
        description='Path to the IDS(Information Delivery Specification) file'
                    'that should be used for the check of the IFC file. '
                    'The file is a xml file, with .ids extension'
                    'An Example can be find in'
                    '/bim2sim/plugins/PluginIFCCheck/bim2sim_ifccheck',
        for_frontend=True,
        mandatory=True
    )
