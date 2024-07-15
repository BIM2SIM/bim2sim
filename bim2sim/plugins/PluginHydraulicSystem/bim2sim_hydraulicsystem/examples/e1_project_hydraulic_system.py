import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
from bim2sim.plugins.PluginTEASER.bim2sim_teaser.examples.e2_medium_project_teaser import \
    (run_medium_building_teaser)


def run_example_project_hydraulic_system():
    """
    """

    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    # project = run_medium_building_teaser()

    project_path_existing = Path(
        "C:/Users/dja/AppData/Local/Temp/bim2sim_example3ltlymz4v")

    # Set the project path to the previous executed project
    project_path = project_path_existing
    # TODO reset config.toml backend

    # Create a project including the folder structure for the project
    project = Project.create(project_path, plugin='HydraulicSystem')

    # specify simulation settings (please have a look at the documentation of
    # all under concepts/sim_settings

    data_path = r"T:\dja-jho\Testing\HydraulicSystem"

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    project.sim_settings.generate_new_building_data = True
    project.sim_settings.generate_new_building_graph = True
    project.sim_settings.generate_new_heating_graph = True

    project.sim_settings.startpoint_heating_graph_x_axis = 23.9
    project.sim_settings.startpoint_heating_graph_y_axis = 6.7
    project.sim_settings.startpoint_heating_graph_z_axis = -3.0
    # TODO integrate the process of .mat stripping this into the plugin as well
    project.sim_settings.heat_demand_mat_file_path =(
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/sim_results_for_hydraulic_system/'
            'AC20-Institute-Var-2-zoning_full.mat')
    project.sim_settings.thermal_zone_mapping_file_path = Path(data_path,
                                                               "tz_mapping.json")

    project.sim_settings.hydraulic_components_data_file_radiator_sheet = \
        "Profilierte Flachheizkörper"
    project.sim_settings.hydraulic_components_data_file_pipe_sheet = \
        "Stahlrohre"

    project.sim_settings.density_fluid = 1000
    project.sim_settings.kinematic_velocity_fluid = 1.002
    project.sim_settings.c_p_fluid = 4180
    project.sim_settings.density_pipe = 7850
    project.sim_settings.absolute_roughness_pipe = 0.045
    project.sim_settings.v_mean = 0.5
    project.sim_settings.v_max = 1
    project.sim_settings.p_max = 10
    project.sim_settings.f = 0.02

    project.sim_settings.t_forward = 40
    project.sim_settings.t_backward = 30
    project.sim_settings.t_room = 21

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())
    # Have a look at the instances/elements that were created
    # elements = project.playground.state['elements']


if __name__ == '__main__':
    run_example_project_hydraulic_system()
