import bim2sim.sim_settings
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
        value=True,
        description='Whether to add heating devices or not.',
        for_frontend=True
    )
    add_floorheating = BooleanSetting(
        value=False,
        description='Whether to add floorheating instead of usual radiators.',
        for_frontend=True
    )
    add_airterminals = BooleanSetting(
        value=True,
        description='Whether to add air terminals or not.',
        for_frontend=True
    )
    ignore_heatloss = BooleanSetting(
        value=False,
        description='Ignores heat loss through walls if set to True.',
        for_frontend=True
    )
    inlet_type = ChoiceSetting(
        value='Plate',
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
        value='Plate',
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
    outflow_direction = ChoiceSetting(
        value='down',
        choices={
            'down': 'Outflow facing downward. Only applicable for original '
                    'shapes.',
            'side': 'Outflow facing sideways. Only applicable for original '
                    'shapes.',
            'angle45down': 'Outflow facing downward with a 45 degrees angle. '
                           'Only applicable for original shapes.'
        },
        description='Choose the outflow direction for original shapes from '
                    'IFC that should be automatically processed. Defaults to '
                    'downward facing flows.'
    )
    select_space_guid = ChoiceSetting(
        value='',
        choices={
            '': 'No guid selected, first space will be selected.'
        },
        description='Select space for OpenFOAM simulation by setting the '
                    'space guid.',
        for_frontend=True,
        any_string=True,
    )
    simulation_date = ChoiceSetting(
        value='12/21',
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
        value=11,
        description='Select time of simulation according to simulated timeframe '
                    'in the PluginEnergyPlus. Insert as number (time) '
                    'for the full hour ranging 1 to 24.',
        min_value=1,
        max_value=24,
        for_frontend=True,
    )
    simulation_type = ChoiceSetting(
        value='steady',
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
        value=0.1,
        description='Set the mesh size of the blockMesh in [m]. Insert a '
                    'number between 0.001 and 0.2.',
        min_value=0.001,
        max_value=0.4,
        for_frontend=True,
    )
    mesh_max_global_cells = NumberSetting(
        value=3000000,
        description='Set the maximum number of global cells for meshing in '
                    'snappyHexMesh.',
        min_value=2000000,
        max_value=50000000,
        for_frontend=True,
    )
    adjust_refinements = BooleanSetting(
        value=False,
        description='Whether surface and region refinements of airterminals '
                    'and interior elements should be automatically '
                    'recomputed or not.',
        for_frontend=True
    )
    total_iterations = NumberSetting(
        value=20000,
        min_value=20,
        max_value=50000,
        description='Total number of iterations for the simulation.',
        for_frontend=True
    )
    steady_iterations = NumberSetting(
        value=2500,
        min_value=20,
        max_value=15000,
        for_frontend=True,
        description='Select number of steady iterations for preconditioning '
                    'a transient simulation.',
    )
    n_procs = NumberSetting(
        value=12,
        min_value=1,
        description='Set the number of processors for decomposition and '
                    'simulation.',
        for_frontend=True
    )
    run_meshing = BooleanSetting(
        value=False,
        description='Whether to run OpenFOAM meshing or not. Only available for'
                    ' linux systems.',
        for_frontend=True
    )
    run_cfd_simulation = BooleanSetting(
        value=False,
        description='Whether to run the OpenFOAM CFD simulation or not. Only '
                    'available for linux systems.',
        for_frontend=True
    )
    heater_radiation = NumberSetting(
        value=0.3,
        description='Select the radiative portion of the heating heat transfer.'
                    ' Choose between 0 and 1.',
        min_value=0,
        max_value=1,
        for_frontend=True,
    )
    add_comfort = BooleanSetting(
        value=True,
        description='Whether to add thermal comfort settings to OpenFOAM',
        for_frontend=True
    )
    add_furniture = BooleanSetting(
        value=False,
        description='Whether to add furniture to OpenFOAM',
        for_frontend=True
    )
    level_heat_balance = BooleanSetting(
        value=True,
        description='Whether to level heat balance: reduce heating towards '
                    'leveled heat balance considering internal gains.'
    )
    furniture_setting = ChoiceSetting(
        value='Office',
        choices={
            'Office': 'Office setup, chair and desk',
            'Concert': 'Concert setup, chairs in rows',
            'Meeting': 'Meeting setup, large table with chairs',
            'TwoSideTable': 'Table with chairs on long side',
            'GroupTable': 'Group table with chairs',
            'Classroom': 'Classroom setup, individual tables with chairs'
        },
        description='Select the type of furniture to add.',
        for_frontend=True
    )
    furniture_amount = NumberSetting(
        value=1,
        min_value=0,
        max_value=300,
        for_frontend=True,
    )
    furniture_orientation = ChoiceSetting(
        value='short_side',
        choices={
            'long_side': 'Long side of a rectangular space',
            'short_side': 'short side of a rectangular space',
            'window': 'window side of a rectangular space',
            'door': 'door side of a rectangular space',
            'north': 'North side',
            'east': 'East side',
            'south': 'South side',
            'west': 'West side',
        }
    )
    add_people = BooleanSetting(
        value=False,
        for_frontend=True,
        description='Choose if people should be added.'
    )
    use_energyplus_people_amount = BooleanSetting(
        value=False, description='Choose if number of people should be '
                                   'assigned as defined in the EnergyPlus '
                                   'simulation. If true, people_amount is not '
                                   'considered but overwritten with the '
                                   'rounded up number of people from the '
                                   'EnergyPlus simulation. '
    )
    people_setting = ChoiceSetting(
        value='Seated',
        choices={
            'Seated': 'Seated, furniture needs to be provided in sufficient amount. ',
            'Standing': 'Standing, no furniture required.'
        },
        description='Select type of people positioning to add.',
        for_frontend=True
    )
    people_amount = NumberSetting(
        value=1,
        min_value=0,
        max_value=300,
        for_frontend=True,
    )
    radiation_model = ChoiceSetting(
        value='P1',
        choices={
            'none': 'No radiation',
            'P1': 'Use P1 Radiation Model',
            'fvDOM': 'Use fvDOM Radiation Model',
            'preconditioned_fvDOM': 'Use P1 to precondition fvDOM Radiation',
        },
        description='Choose the radiation model',
        for_frontend=True
    )
    radiation_precondition_time = NumberSetting(
        value=1000,
        min_value=10,
        max_value=5000,
        description='Choose number of preconditioning iterations using P1 '
                    'radiation for fvDOM radiation',
        for_frontend=True
    )
    add_solar_radiation=BooleanSetting(
        value=True,
        description='Add solar radiation. Requires fvDOM as radiation model.',
        for_frontend=True
    )
    add_air_volume_evaluation = BooleanSetting(
        value=False,
        description='Add an air volume evaluation. Removes voids of all '
                    'people, furniture elements, and heaters, to enhance the '
                    'evaluation of the air volume itself. This is '
                    'computationally expensive.',
        for_frontend=True
    )
    scale_person_for_eval = NumberSetting(
        value=0.05,
        min_value=0.001,
        max_value=0.2,
        description='Scale shape of person for evaluation in paraview.',
        for_frontend=True,
    )
    mesh_feature_snapping = BooleanSetting(
        value=False,
        description='Choose if explicit surface feature snapping should be '
                    'applied in snappyHexMesh. ',
        for_frontend=True
    )
    cluster_jobname = ChoiceSetting(
        value="newJob",
        choices={"fullRun": "Specify content", "Job1234": "Enumerate"},
        description='Jobname that is used when running the simulation via a '
                    'batch script on the RWTH Compute Cluster.',
        for_frontend=True,
        any_string=True
    )
    cluster_compute_account = ChoiceSetting(
        value='',
        choices={
            '': 'Skip defining compute cluster account.',
            "thes1234": "Define thesis account",
            "rwth5678": "Define user account"
        },
        description=r'Specify the compute account that is used for running '
                    r'the simulation on the RWTH Compute Cluster. Specify as '
                    r'"thes1234".',
        for_frontend=True,
        any_string=True
    )
    cluster_max_runtime_simulation = ChoiceSetting(
        value="23:59:00",
        choices={"11:59:00": "12 hours", "06:00:00": "6 hours"},
        description=r'Max runtime for a full simulation in the format of '
                    r'"D:HH:MM:SS".',
        for_frontend=True,
        any_string=True
    )
    cluster_max_runtime_meshing = ChoiceSetting(
        value="00:59:00",
        choices={"00:30:00": "30 minutes", "00:15:00": "15 minutes"},
        description='Max runtime for meshing in the format of '
                    'D:HH:MM:SS .',
        for_frontend=True,
        any_string=True
    )
    cluster_cpu_per_node = NumberSetting(
        value=96,
        min_value=1,
        max_value=1024,
        description='Number of physical cores per node.',
        for_frontend=True
    )
