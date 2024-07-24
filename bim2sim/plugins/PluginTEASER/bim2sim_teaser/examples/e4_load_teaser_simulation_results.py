from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.tasks import bps, common
import bim2sim.plugins.PluginTEASER.bim2sim_teaser.task as teaser_task
from e1_simple_project_bps_teaser import run_example_simple_building_teaser


def run_example_load_existing_project():
    """Load an existing TEASER simulation project and work with it.

    # TODO
    ...
    """
    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    default_logging_setup()

    # First run the previous example e1: run_example_simple_building_teaser
    project = run_example_simple_building_teaser()

    # If we already ran a simulation and just want to use bim2sim
    # postprocessing, we don't need to run it again. Therefore we get the
    # project path from the previous run
    #
    project_path_existing = project.paths.root

    # Set the project path to the previous executed project
    project_path = project_path_existing

    # Instantiate a fresh project based on the existing project folder
    project = Project.create(project_path, plugin='teaser')

    # TODO those 2 are not used but are needed currently as otherwise the
    #  plotting tasks will be executed and weather file is mandatory
    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    project.sim_settings.dymola_simulation = True
    # Select results to output:
    project.sim_settings.sim_results = [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out"
    ]
    project.sim_settings.create_plots = True
    # Just select the tasks that are needed to load the previous simulation
    # results and create the result plots
    project.plugin_cls.default_tasks = [
        common.LoadIFC,
        common.DeserializeElements,
        teaser_task.LoadModelicaResults,
        teaser_task.CreateResultDF,
        bps.PlotBEPSResults,
    ]
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_load_existing_project()
