import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler

def run_example_1():
    """Run a building performance simulation with the EnergyPlus backend.

    This example runs a BPS with the EnergyPlus backend. Specifies project
    directory and location of the IFC file. Then, it creates a bim2sim
    project with the EnergyPlus backend. Simulation settings are specified
    (EnergyPlus location needs to be specified according to your system,
    other settings are set to default if not specified otherwise),
    before the project is executed with the previously specified settings.
    """
    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example_spawn').name)

    download_test_resources(IFCDomain.arch, force_new=False)
    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/ExampleHOM_with_radiator.ifc',
    }

    # Create a project including the folder structure for the project with
    # energyplus as backend
    project = Project.create(project_path, ifc_paths, 'spawn')

    # Set the install path to your EnergyPlus installation according to your
    # system requirements
    project.sim_settings.ep_install_path = Path(
        'C:/EnergyPlusV9-6-0/')
    project.sim_settings.ep_version = "9-6-0"
    project.sim_settings.weather_file_path_ep = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.epw')
    # TODO make sure that a non existing sim_setting assignment raises an error
    project.sim_settings.weather_file_path_modelica = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    # Set other simulation settings, otherwise all settings are set to default

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    answers = ('HVAC-SpaceHeater', *('Living',)*6, 2010)
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())
    # run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_1()
