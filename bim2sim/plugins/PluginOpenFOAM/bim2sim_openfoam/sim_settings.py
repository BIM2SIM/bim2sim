from bim2sim.elements import bps_elements as bps_elements, hvac_elements as hvac_elements
from bim2sim.elements.base_elements import Material
from bim2sim.plugins.PluginComfort.bim2sim_comfort import ComfortSimSettings
from bim2sim.sim_settings import BooleanSetting, ChoiceSetting, NumberSetting


class OpenFOAMSimSettings(ComfortSimSettings):
    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items,
                                  hvac_elements.AirTerminal,
                                  hvac_elements.SpaceHeater,
                                  Material}

    add_heating = BooleanSetting(
        default=True,
        description='Whether to add heating devices or not.',
        for_frontend=True
    )
    add_floorheating = BooleanSetting(
        default=False,
        description='Whether to add floorheating instead of usual radiators.',
        for_frontend=True
    )
    add_airterminals = BooleanSetting(
        default=True,
        description='Whether to add air terminals or not.',
        for_frontend=True
    )
    ignore_heatloss = BooleanSetting(
        default=False,
        description='Ignores heat loss through walls if set to True.',
        for_frontend=True
    )
    inlet_type = ChoiceSetting(
        default='Plate',
        choices={
            'Original': 'Simplified IFC shape for inlet',
            'Plate': 'Simplified plate for inlet',
            'StlDiffusor': 'Inlet diffusor from stl file',
            'SimpleStlDiffusor': 'Simplified inlet diffusor from stl file',
            'IfcDiffusor': 'Inlet diffusor modified from ifc file (if '
                                'available), otherwise stl diffusor from file.',
            'None': 'No inlet plate, only gap in ceiling.'
        },
        description='Choose air terminal inlet type.',
        for_frontend=True
    )
    outlet_type = ChoiceSetting(
        default='Plate',
        choices={
            'Original': 'Simplified IFC shape for outlet',
            'Plate': 'Simplified plate for outlet',
            'StlDiffusor': 'Outlet diffusor from stl file',
            'SimpleStlDiffusor': 'Simplified outlet diffusor from stl file',
            'IfcDiffusor': 'Outlet diffusor modified from ifc file (if '
                                 'available), otherwise stl diffusor from '
                                 'file.',
            'None': 'No outlet plate, only gap in ceiling.'
        },
        description='Choose air terminal outlet type.',
        for_frontend=True
    )
    select_space_guid = ChoiceSetting(
        default='',
        choices={
            '': 'No guid selected, first space will be selected.'
        },
        description='Select space for OpenFOAM simulation by setting the '
                    'space guid.',
        for_frontend=True,
        any_string=True,
    )
    simulation_date = ChoiceSetting(
        default='12/21',
        description='Select date of simulation according to simulated '
                    'timeframe in the PluginEnergyPlus. Insert as string in '
                    'format MM/DD.',
        choices={
            '12/21': 'Winter design day',
            '07/21': 'Summer design day',
        },
        for_frontend=True,
        any_string=True
    )
    simulation_time = NumberSetting(
        default=11,
        description='Select time of simulation according to simulated timeframe '
                    'in the PluginEnergyPlus. Insert as number (time) '
                    'for the full hour ranging 1 to 24.',
        min_value=1,
        max_value=24,
        for_frontend=True,
    )
    simulation_type = ChoiceSetting(
        default='steady',
        choices={
            'steady': 'steady-state simulation',
            'combined': 'preconditioned transient simulation',
            'transient': 'transient simulation'
        },
        description='Select simulation type (steady-state, combined or '
                    'transient).',
        for_frontend=True,
    )
    mesh_size = NumberSetting(
        default=0.1,
        description='Set the mesh size of the blockMesh in [m]. Insert a '
                    'number between 0.001 and 0.2.',
        min_value=0.001,
        max_value=0.2,
        for_frontend=True,
    )
    adjust_refinements = BooleanSetting(
        default=False,
        description='Whether surface and region refinements of airterminals '
                    'and interior elements should be automatically '
                    'recomputed or not.',
        for_frontend=True
    )
    steady_iterations = NumberSetting(
        default=2500,
        min_value=20,
        max_value=15000,
        for_frontend=True,
        description='Select number of steady iterations for preconditioning '
                    'a transient simulation.',
    )
    n_procs = NumberSetting(
        default=12,
        min_value=1,
        description='Set the number of processors for decomposition and '
                    'simulation.',
        for_frontend=True
    )
    run_meshing = BooleanSetting(
        default=False,
        description='Whether to run OpenFOAM meshing or not. Only available for'
                    ' linux systems.',
        for_frontend=True
    )
    run_cfd_simulation = BooleanSetting(
        default=False,
        description='Whether to run the OpenFOAM CFD simulation or not. Only '
                    'available for linux systems.',
        for_frontend=True
    )
    heater_radiation = NumberSetting(
        default=0.3,
        description='Select the radiative portion of the heating heat transfer.'
                    ' Choose between 0 and 1.',
        min_value=0,
        max_value=1,
        for_frontend=True,
    )
    add_comfort = BooleanSetting(
        default=True,
        description='Whether to add thermal comfort settings to OpenFOAM',
        for_frontend=True
    )
    add_furniture = BooleanSetting(
        default=False,
        description='Whether to add furniture to OpenFOAM',
        for_frontend=True
    )
    level_heat_balance = BooleanSetting(
        default=True,
        description='Whether to level heat balance: reduce heating towards '
                    'leveled heat balance considering internal gains.'
    )
    furniture_setting = ChoiceSetting(
        default='Office',
        choices={
            'Office': 'Office setup, chair and desk',
            'Concert': 'Concert setup, chairs in rows',
            'Meeting': 'Meeting setup, large table with chairs',
            'Classroom': 'Classroom setup, individual tables with chairs'
        },
        description='Select the type of furniture to add.',
        for_frontend=True
    )
    furniture_amount = NumberSetting(
        default=1,
        min_value=0,
        max_value=300,
        for_frontend=True,
    )
    add_people = BooleanSetting(
        default=False,
        for_frontend=True,
        description='Choose if people should be added.'
    )
    people_setting = ChoiceSetting(
        default='Seated',
        choices={
            'Seated': 'Seated, furniture needs to be provided in sufficient amount. ',
            'Standing': 'Standing, no furniture required.'
        },
        description='Select type of people positioning to add.',
        for_frontend=True
    )
    people_amount = NumberSetting(
        default=1,
        min_value=0,
        max_value=300,
        for_frontend=True,
    )
    radiation_model = ChoiceSetting(
        default='P1',
        choices={
            'noRadiation': 'No radiation',
            'P1': 'Use P1 Radiation Model',
            'fvDOM': 'Use fvDOM Radiation Model',
            'preconditioned_fvDOM': 'Use P1 to precondition fvDOM Radiation',
        },
        description='Choose the radiation model',
        for_frontend=True
    )
    radiation_precondition_time = NumberSetting(
        default=1000,
        min_value=10,
        max_value=5000,
        description='Choose number of preconditioning iterations using P1 '
                    'radiation for fvDOM radiation',
        for_frontend=True
    )
    add_solar_radiation=BooleanSetting(
        default=True,
        description='Add solar radiation. Requires fvDOM as radiation model.',
        for_frontend=True
    )
