import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.utilities.types import IFCDomain


def run_example_4():
    """Run a building performance simulation with the EnergyPlus backend.

    This example runs a BPS with the EnergyPlus backend. Specifies project
    directory and location of the IFC file. Then, it creates a bim2sim
    project with the EnergyPlus backend. In this example, the building is
    rotated by 180° clockwise.
    """
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)

    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }

    # Create a project including the folder structure for the project with
    # energyplus as backend
    project = Project.create(project_path, ifc_paths, 'energyplus')

    # set weather file data
    project.sim_settings.weather_file_path_ep = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.epw')
    # Set the install path to your EnergyPlus installation according to your
    # system requirements
    # project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'

    # run annual simulation for EnergyPlus
    project.sim_settings.run_full_simulation = True
    project.sim_settings.building_rotation_overwrite = 180

    # Set other simulation settings, otherwise all settings are set to default

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_4()
