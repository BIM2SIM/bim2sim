import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.types import IFCDomain


def run_example_8():
    """Run a building performance simulation with the EnergyPlus backend.

    This example runs a BPS with the EnergyPlus backend. Specifies project
    directory and location of the IFC file. Then, it creates a bim2sim
    project with the EnergyPlus backend. Simulation settings are specified
    (EnergyPlus location needs to be specified according to your system,
    other settings are set to default if not specified otherwise),
    before the project is executed with the previously specified settings.
    """
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_openfoam10_').name)

    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/FM_ARC_DigitalHub_with_SB89.ifc',
    }

    # Create a project including the folder structure for the project with
    # energyplus as backend
    project = Project.create(project_path, ifc_paths, 'openfoam')
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "customUsagesFM_ARC_DigitalHub_with_SB89.json")
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
    project.sim_settings.select_space_guid = '3GmoJyFk9FvAnea6mogixJ'
    # project.sim_settings.select_space_guid = '2RSCzLOBz4FAK$_wE8VckM'
    # project.sim_settings.simulation_time = 11
    project.sim_settings.run_meshing = False
    project.sim_settings.run_cfd_simulation = False
    project.sim_settings.add_heating = True
    # project.sim_settings.add_floorheating = True
    # project.sim_settings.add_airterminals = True
    project.sim_settings.add_furniture = True
    project.sim_settings.add_people = True
    project.sim_settings.people_amount = 50
    project.sim_settings.furniture_setting = 'Concert'
    project.sim_settings.furniture_orientation = 'long_side'
    project.sim_settings.furniture_amount = 200
    answers = ('Other', *(None,)*12, 2015)
    # project.sim_settings.simulation_type = 'transient'
    # project.sim_settings.inlet_type = 'SimpleStlDiffusor'
    # project.sim_settings.outlet_type = 'SimpleStlDiffusor'
    # project.sim_settings.outlet_type = 'None'
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))


if __name__ == '__main__':
    run_example_8()
