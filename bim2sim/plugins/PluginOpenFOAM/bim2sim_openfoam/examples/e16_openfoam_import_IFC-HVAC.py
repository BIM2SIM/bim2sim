import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain


def run_example_16():
    """
    Prepare an OpenFOAM case with ventilation and a radiator including
    meshing and running the simulation on linux.

    This example runs a BPS with the EnergyPlus backend and a CFD simulation
    with the OpenFOAM backend. It specifies project
    directory and location of the IFC file. Then, it creates a bim2sim
    project with the EnergyPlus backend. Simulation settings are specified
    (EnergyPlus location needs to be specified according to your system,
    other settings are set to default if not specified otherwise),
    before the project is executed with the previously specified settings.

    The EnergyPlus simulation is followed by the setup of the OpenFOAM
    CFD use case, which bases on the same IFC input as the previously set
    up EnergyPlus use case.
    """
    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_openfoam16_').name)

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)
    # download_test_resources(IFCDomain.hydraulic, force_new=False)
    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(r'C:\Users\richter\sciebo\01-Studentenarbeiten\03-MA\05_MA_Bruns\08_Dateien\2024-04-23_3rooms_240317_Heater_AirTerminal_Table.ifc'),
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

    # Set other simulation settings, otherwise all settings are set to default
    project.sim_settings.cfd_export = True
    project.sim_settings.select_space_guid = '2_p5o3S0b78AkDwuwKWtE8'
    project.sim_settings.add_heating = True
    project.sim_settings.add_floorheating = False
    project.sim_settings.add_airterminals = True
    project.sim_settings.add_comfort = True
    project.sim_settings.output_keys = ['output_outdoor_conditions',
                                        'output_zone_temperature',
                                        'output_zone', 'output_infiltration',
                                        'output_meters',
                                        'output_internal_gains']
    # project.sim_settings.level_heat_balance = False

    answers = (*('HVAC-AirTerminal',)*2, None, 'HVAC-SpaceHeater')
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))
    # run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_16()
