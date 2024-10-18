from bim2sim.elements import bps_elements as bps_elements, hvac_elements as hvac_elements
from bim2sim.elements.base_elements import Material
from bim2sim.sim_settings import BuildingSimSettings, BooleanSetting, ChoiceSetting, PathSetting, NumberSetting, StringSetting
from pathlib import Path


class HydraulicSystemSimSettings(BuildingSimSettings):
    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items, *hvac_elements.items,
                                  Material}

    generate_new_building_data = BooleanSetting(
        default=True,
        description="True: Generate new building data out of ifc file"
                    "Else: Load existing building data out of json file"
    )
    generate_new_building_graph = BooleanSetting(
        default=True,
        description="True: Generate new building graph out of ifc file"
                    "Else: Load existing building graph out of json file"
    )
    generate_new_heating_graph = BooleanSetting(
        default=True,
        description="True: Generate new heating graph out of ifc file"
                    "Else: Load existing heating graph out of json file"
    )
    disaggregate_heat_demand_thermal_zones = BooleanSetting(
    default=False,
        description="Disaggregates heat demand for thermal zones based on thermal zone floor area"
                    "Needs to consistent with PluginTeaser Simulation"
    )
    startpoint_heating_graph_x_axis = NumberSetting(
        default=None,
        min_value=-200,
        max_value=200,
        description="Start point of heating network graph on the x axis",
        for_frontend=True,
    )
    startpoint_heating_graph_y_axis = NumberSetting(
        default=None,
        min_value=-200,
        max_value=200,
        description="Start point of heating network graph on the y axis",
        for_frontend=True,
    )
    startpoint_heating_graph_z_axis = NumberSetting(
        default=None,
        min_value=-200,
        max_value=200,
        description="Start point of heating network graph on the z axis",
        for_frontend=True,
    )
    heat_demand_mat_file_path = PathSetting(
        default=None,
        description='Path to the dymola mat file which was generated by '
                    'bim2sim plugin teaser',
        for_frontend=True,
        mandatory=True
    )

    # TODO convert xlsx into json and translate to english
    hydraulic_components_data_file_path = PathSetting(
        default=Path(__file__).parent /
                'assets/hydraulic_components.xlsx',
        description='Path to the data file which holds information'
                    'about possible hydraulic system components',
        for_frontend=True,
        mandatory=False
    )
    hydraulic_components_data_file_radiator_sheet = StringSetting(
        default="Stahlrohre",
        description='Name of sheet in hydraulic components data file'
                    'which holds data about the desired radiators',
        for_frontend=True
    )
    hydraulic_components_data_file_pipe_sheet = StringSetting(
        default="Profilierte Flachheizkörper",
        description='Name of sheet in hydraulic components data file'
                    'which holds data about the desired hydraulic pipes',
        for_frontend=True
    )
    one_pump_flag = BooleanSetting(
        default=True,
        description="Flags if only one pump is used"
    )
    heat_delivery_type = ChoiceSetting(
        default=['Radiator'],
        choices={
            'Radiator': 'Radiator',
            'UFH': 'UFH',
            'UFH+Radiator': 'UFH+Radiator',
        },
        description='Choose type of heat delivery',
        multiple_choice=True,
        for_frontend=True
    )
    ufh_heat_flow_laying_distance_changeover = NumberSetting(
        default=70,
        min_value=0,
        max_value=150,
        description="Heat flow per area of under floor heating at which"
                    "laying distance of ufh changes from 100mm to 200mm",
        for_frontend=True
    )
    ufh_max_heat_flow_per_area = NumberSetting(
        default=100,
        min_value=0,
        max_value=150,
        description="Max heat flow per area of under floor heating"
                    "Further heat flow needs to be delivered e.g. by air or radiator",
        for_frontend=True
    )

    # Material parameter
    g = NumberSetting(
        default=9.81,
        min_value=0,
        max_value=5000,
        description="Gravity in m/s^2",
        for_frontend=True,
    )
    density_fluid = NumberSetting(
        default=1000,
        min_value=0,
        max_value=5000,
        description="Density of heating fluid in kg/m^3",
        for_frontend=True,
    )
    kinematic_velocity_fluid = NumberSetting(
        default=1.002,
        min_value=0,
        max_value=5000,
        description="Kinematic velocity of heating fluid in mm^2/s",
        for_frontend=True,
    )
    c_p_fluid = NumberSetting(
        default=4.18,
        min_value=0,
        max_value=5000,
        description="Heat capacity of heating fluid in kJ/kg/K",
        for_frontend=True,
    )
    v_mean = NumberSetting(
        default=1,
        min_value=0,
        max_value=10,
        description="Mean fluid velocity in m/s",
        for_frontend=True,
    )
    v_max = NumberSetting(
        default=2,
        min_value=0,
        max_value=10,
        description="Max fluid velocity in m/s",
        for_frontend=True,
    )
    p_max = NumberSetting(
        default=10,
        min_value=0,
        max_value=5000,
        description="Max pressure in hydraulic system in bar",
        for_frontend=True,
    )
    f = NumberSetting(
        default=0.02,
        min_value=0,
        max_value=5000,
        description="f value of radiator",
        for_frontend=True,
    )
    t_forward = NumberSetting(
        default=40,
        min_value=0,
        max_value=200,
        description="Forward heating temperature in °C",
        for_frontend=True,
    )
    t_backward = NumberSetting(
        default=30,
        min_value=0,
        max_value=200,
        description="Backward heating temperature in °C",
        for_frontend=True,
    )
    t_room = NumberSetting(
        default=20,
        min_value=0,
        max_value=100,
        description="Room temperature in °C",
        for_frontend=True,
    )
    density_pipe = NumberSetting(
        default=7850,
        min_value=0,
        max_value=100000,
        description="Density of pipe in kg/m^3",
        for_frontend=True,
    )
    absolute_roughness_pipe = NumberSetting(
        default=0.045,
        min_value=0,
        max_value=1,
        description="Absolute roughness of pipe",
        for_frontend=True,
    )
