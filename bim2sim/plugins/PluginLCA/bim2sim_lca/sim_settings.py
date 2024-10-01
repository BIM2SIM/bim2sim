from bim2sim.elements import bps_elements as bps_elements, \
    hvac_elements as hvac_elements
from bim2sim.elements.base_elements import Material
from bim2sim.sim_settings import BuildingSimSettings


class LCAExportSettings(BuildingSimSettings):
    """Life Cycle Assessment analysis with CSV Export of the selected BIM Model
     """
    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items, *hvac_elements.items,
                                  Material}
