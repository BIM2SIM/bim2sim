import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
from bim2sim.plugins.PluginTEASER.bim2sim_teaser.examples.e2_medium_project_teaser import \
    (run_medium_building_teaser)


def run_example_project_hydraulic_system(lock,
                                         project_path, weather_file_path, export_graphs,
                                         heat_delivery_type, t_forward, t_backward):
    """
    """

    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    default_logging_setup()

    load_existing_project = False

    if load_existing_project:
        project = run_medium_building_teaser()
        project_path = project.paths.root
    else:
        # Create a temp directory for the project, feel free to use a "normal"
        # directory
        #project_path = Path("D:\dja-jho\Testing\SystemTest")
        pass

    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-Institute-Var-2.ifc',
    }

    # Create a project including the folder structure for the project
    project = Project.create(project_path, ifc_paths, plugin='HydraulicSystem')


    # specify simulation settings (please have a look at the documentation of
    # all under concepts/sim_settings

    # Set Lock class
    project.sim_settings.lock = lock

    # set weather file data
    project.sim_settings.weather_file_path = weather_file_path

    project.sim_settings.generate_new_building_data = False
    project.sim_settings.generate_new_building_graph = False
    project.sim_settings.generate_new_heating_graph = True

    project.sim_settings.export_graphs = export_graphs

    project.sim_settings.disaggregate_heat_demand_thermal_zones = True

    project.sim_settings.startpoint_heating_graph_x_axis = 41
    project.sim_settings.startpoint_heating_graph_y_axis = 2.8
    project.sim_settings.startpoint_heating_graph_z_axis = -3

    project.sim_settings.heat_demand_mat_file_path = fr"{project_path}\export\TEASER\SimResults\AC20InstituteVar2\Buerogebaeude\teaser_results_edited.mat"
    project.sim_settings.serialized_elements_path = Path(Path(project_path.parent), "SerializedTEASER", "export", "serialized_elements.pickle")

    project.sim_settings.heat_delivery_type = heat_delivery_type # UFH or Radiator
    project.sim_settings.hydraulic_components_data_file_radiator_sheet = "Profilierte Flachheizkörper"
    project.sim_settings.hydraulic_components_data_file_pipe_sheet = "Stahlrohre"
    project.sim_settings.ufh_heat_flow_laying_distance_changeover = 70
    project.sim_settings.ufh_max_heat_flow_per_area = 300

    project.sim_settings.density_fluid = 1000
    project.sim_settings.kinematic_velocity_fluid = 1.002
    project.sim_settings.c_p_fluid = 4180
    project.sim_settings.density_pipe = 7850
    project.sim_settings.absolute_roughness_pipe = 0.045
    project.sim_settings.v_mean = 0.5
    project.sim_settings.v_max = 1
    project.sim_settings.p_max = 10
    project.sim_settings.f = 0.02

    project.sim_settings.t_forward = t_forward
    project.sim_settings.t_backward = t_backward
    project.sim_settings.t_room = 21

    answers = (2015,)
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    # run_project(project, ConsoleDecisionHandler())
    # Have a look at the instances/elements that were created
    # elements = project.playground.state['elements']


if __name__ == '__main__':
    run_example_project_hydraulic_system()
