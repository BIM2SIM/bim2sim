from bim2sim.elements import bps_elements as bps_elements, hvac_elements as hvac_elements
from bim2sim.elements.base_elements import Material
from bim2sim.sim_settings import BuildingSimSettings, BooleanSetting, ChoiceSetting, PathSetting, NumberSetting, StringSetting
from pathlib import Path

class LCAExportSettings(BuildingSimSettings):
    """Life Cycle Assessment analysis with CSV Export of the selected BIM Model
     """
    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items, *hvac_elements.items,
                                  Material}

    update_emission_parameter_from_oekobdauat = BooleanSetting(
        value=False,
        description='Whether to update material emission parameter from Ökobaudat',
        for_frontend=True
    )
    only_cradle_to_gate = BooleanSetting(
        value=False,
        description='Whether to calculate lca only between cradle and gate phase',
        for_frontend=True
    )
    calculate_lca_building = BooleanSetting(
        value=True,
        description='Whether to calculate lca of building or not',
        for_frontend=True
    )
    calculate_lca_hydraulic_system = BooleanSetting(
        value=True,
        description='Whether to calculate lca of hydraulic system or not',
        for_frontend=True
    )
    calculate_lca_ventilation_system = BooleanSetting(
        value=True,
        description='Whether to calculate lca of ventilation system or not',
        for_frontend=True
    )
    calculate_costs_building = BooleanSetting(
        value=True,
        description='Whether to calculate costs of building or not',
        for_frontend=True
    )
    calculate_costs_hydraulic_system = BooleanSetting(
        value=True,
        description='Whether to calculate costs of hydraulic system or not',
        for_frontend=True
    )
    calculate_costs_ventilation_system = BooleanSetting(
        value=True,
        description='Whether to calculate costs of ventilation system or not',
        for_frontend=True
    )
    # Hydraulic Settings
    pipe_type = ChoiceSetting(
        value='Stahlrohr',
        choices={
            'Stahlrohr': 'Stahlrohr',
            'Innenverzinne_Kupferrohre_pro_1kg': 'Kupferrohr'
        },
        description='Type of pipe used in hydraulic system'
                    'Should be the same as used in Plugin HydraulicSystem'
    )
    heat_delivery_type = ChoiceSetting(
        value=['Radiator'],
        choices={
            'Radiator': 'Radiator',
            'UFH': 'UFH',
            'UFH+Radiator': 'UFH+Radiator',
        },
        description='Type of heat delivery'
                    'Should be the same as used in Plugin HydraulicSystem',
        multiple_choice=True,
        for_frontend=True
    )
    ufh_pipe_type = ChoiceSetting(
        value='PP',
        choices={
            'Copper': 'Copper',
            'PEX': 'PEX',
            'PP': 'PP',
        },
        description='Choose pipe material of under floor heating',
        for_frontend=True
    )
    hydraulic_components_data_file_path = PathSetting(
        value=Path(__file__).parent /
                'assets/hydraulic_components.xlsx',
        description='Path to the data file which holds information'
                    'about possible hydraulic system components',
        for_frontend=True,
        mandatory=False
    )
    hydraulic_components_data_file_radiator_sheet = StringSetting(
        value="Profilierte Flachheizkörper",
        description='Name of sheet in hydraulic components data file'
                    'which holds data about the desired radiators',
        for_frontend=True
    )
    hydraulic_system_material_xlsx = PathSetting(
        value=None,
        description='Path to the excel file which holds information'
                    'about used material in hydraulic system'
                    '(Output of PluginHydraulicSystem)',
        for_frontend=True
    )

    # Ventilation Settings
    ventilation_supply_system_material_xlsx = PathSetting(
        value=None,
        description='Path to the excel file which holds information'
                    'about used material in ventilation supply system'
                    '(Output of PluginVentilationSystem)',
        for_frontend=True
    )
    ventilation_exhaust_system_material_xlsx = PathSetting(
        value=None,
        description='Path to the excel file which holds information'
                    'about used material in ventilation exhaust system'
                    '(Output of PluginVentilationSystem)',
        for_frontend=True
    )
    ventilation_rooms_supply_xlsx = PathSetting(
        value=None,
        description='Path to the excel file which holds information'
                    'about room specific information in ventilation supply'
                    ' system (Output of PluginVentilationSystem)',
        for_frontend=True
    )
    ventilation_rooms_exhaust_xlsx = PathSetting(
        value=None,
        description='Path to the excel file which holds information'
                    'about room specific information in ventilation exhaust'
                    ' system (Output of PluginVentilationSystem)',
        for_frontend=True
    )
    ventilation_fire_damper_xlsx = PathSetting(
        value=None,
        description='Path to the excel file which holds information'
                    'about fire damper data in ventilation'
                    ' system (Output of PluginVentilationSystem)',
        for_frontend=True
    )

