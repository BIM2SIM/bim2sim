from bim2sim.elements import bps_elements as bps_elements
from bim2sim.elements.base_elements import Material
from bim2sim.sim_settings import BuildingSimSettings, BooleanSetting



class VentilationSystemSimSettings(BuildingSimSettings):

    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items,
                                      Material}

    ventilation_lca_export_airflow = BooleanSetting(
        default=True,
        description="Export the figures, plans and .csv data from for"
                    " ventilation supply generation"
    )
    ventilation_lca_export_supply = BooleanSetting(
        default=True,
        description="Export the figures, plans and .csv data from for"
                    " ventilation supply generation"
    )
    ventilation_lca_export_exhaust = BooleanSetting(
        default=True,
        description="Export the figures, plans and .csv data from for"
                    " ventilation exhaust generation"
    )
    ventilation_lca_export_system = BooleanSetting(
        default=True,
        description="Export the figures, plans and .csv data from for"
                    " ventilation supply generation"
    )


