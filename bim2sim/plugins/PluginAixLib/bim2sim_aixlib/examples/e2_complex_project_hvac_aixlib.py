import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.utilities.types import IFCDomain
from bim2sim.elements.base_elements import Material
from bim2sim.elements import bps_elements as bps_elements, \
    hvac_elements as hvac_elements


def run_example_complex_hvac_aixlib():
    """Run an HVAC simulation with the AixLib backend with a complex IFC.

    First the project directory and location of the HVAC IFC file are specified.
    Then, we create a bim2sim project with the AixLib backend. Simulation type
    settings are set, in this case we set threshold of fuzzy search a bit lower,
    to reduce the amount of decisions. Afterwards the project is
    executed via the ConsoleDecisionHandler which takes answers for upcoming
    decisions via command line input.
    """

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(r"D:\02_Daten\Testing\PluginAixLib\Test")

    # Set path of ifc for hydraulic domain with the fresh downloaded test models
    ifc_paths = {
        IFCDomain.hydraulic:
            Path(
                r"D:\03_Cloud\Sciebo\BIM2Praxis\IFC-Modelle\EDGE\ueberarbeitet_2025-10\BIM2PRAXIS_RLT-2025-09-11_cleaned_jho.ifc")
    }
    # Create a project including the folder structure for the project with
    project = Project.create(project_path, ifc_paths, 'aixlib')

    # set weather file data
    project.sim_settings.weather_file_path_modelica = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    project.sim_settings.relevant_elements = {*hvac_elements.ventilation_items, Material}

    # Set fuzzy threshold to 0.5 to reduce the number of decisions (this is
    # IFC-file specific and needs to be evaluated by the user
    project.sim_settings.fuzzy_threshold = 0.5

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())

# Following the answers for the decisions are listed for documentation:
# 'HVAC-ThreeWayValve',
# 'HVAC-Pipe',
# 'HVAC-HeatPump',
# 'HVAC-Valve',
# True *13,
# TODO: following are not up2date
# True * 4
# efficiency: 0.95
# flow_temperature: 70
# nominal_power_consumption: 200
# return_temperature: 50
# following multiple
# return_temperature: 50
# (body_mass: 15, heat_capacity: 10) * 7


if __name__ == '__main__':
    run_example_complex_hvac_aixlib()
