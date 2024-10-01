from bim2sim.elements import bps_elements as bps_elements, hvac_elements as hvac_elements
from bim2sim.elements.base_elements import Material
from bim2sim.sim_settings import BuildingSimSettings, BooleanSetting, ChoiceSetting, PathSetting


class LCAExportSettings(BuildingSimSettings):
    """Life Cycle Assessment analysis with CSV Export of the selected BIM Model
     """
    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items, *hvac_elements.items,
                                  Material}

    update_emission_parameter_from_oekobdauat = BooleanSetting(
        default=False,
        description='Whether to update material emission parameter from Ökobaudat',
        for_frontend=True
    )
    calculate_lca_building = BooleanSetting(
        default=True,
        description='Whether to calculate lca of building or not',
        for_frontend=True
    )
    calculate_lca_hydraulic_system = BooleanSetting(
        default=True,
        description='Whether to calculate lca of building or not',
        for_frontend=True
    )
    pipe_type = ChoiceSetting(
        default='Stahlrohr',
        choices={
            'Stahlrohr': 'Stahlrohr',
            'Innenverzinne_Kupferrohre_pro_1kg': 'Kupferrohr'
        },
        description='Type of pipe used in hydraulic system'
                    'Should be the same as used in Plugin HydraulicSystem'
    )
    heat_delivery_type = ChoiceSetting(
        default=['Radiator'],
        choices={
            'Radiator': 'Radiator',
            'UFH': 'UFH',
            'UFH+Radiator': 'UFH+Radiator',
            'UFH+Air': 'UFH+Air',
        },
        description='Type of heat delivery'
                    'Should be the same as used in Plugin HydraulicSystem',
        multiple_choice=True,
        for_frontend=True
    )
    ufh_pipe_type = ChoiceSetting(
        default='PP',
        choices={
            'Copper': 'Copper',
            'PEX': 'PEX',
            'PP': 'PP',
        },
        description='Choose pipe material of under floor heating',
        for_frontend=True
    )
    hydraulic_system_material_xlsx = PathSetting(
        default=None,
        description='Path to the excel file which holds information'
                    'about used material in hydraulic system'
                    '(Output of PluginHydraulicSystem)',
        for_frontend=True
    )
