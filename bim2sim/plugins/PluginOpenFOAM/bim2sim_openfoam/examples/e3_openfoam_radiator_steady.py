import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain


def run_example_3():
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
        tempfile.TemporaryDirectory(prefix='bim2sim_openfoam3_').name)

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)
    # download_test_resources(IFCDomain.hydraulic, force_new=False)
    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }

    # Create a project including the folder structure for the project with
    # energyplus as backend
    project = Project.create(project_path, ifc_paths, 'openfoam')

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.epw')
    # Set the install path to your EnergyPlus installation according to your
    # system requirements
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'

    # run annual simulation for EnergyPlus
    # project.sim_settings.run_full_simulation = True

    # Set other simulation settings, otherwise all settings are set to default
    project.sim_settings.cfd_export = True
    project.sim_settings.select_space_guid = '2RSCzLOBz4FAK$_wE8VckM'
    # project.sim_settings.simulation_time = 11
    project.sim_settings.run_meshing = False
    project.sim_settings.run_cfd_simulation = False
    project.sim_settings.add_heating = True
    project.sim_settings.add_floorheating = False
    project.sim_settings.add_airterminals = False
    answers = ('ArchiCAD', 'ArchiCAD', *('Single office',)*4)
    # project.sim_settings.simulation_type = 'transient'
    # project.sim_settings.inlet_type = 'StlDiffusor'
    # project.sim_settings.outlet_type = 'None'
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))


if __name__ == '__main__':
    run_example_3()
