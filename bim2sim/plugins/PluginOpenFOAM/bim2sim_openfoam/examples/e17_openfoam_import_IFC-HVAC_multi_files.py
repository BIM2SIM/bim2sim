import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain


def run_example_17():
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
        tempfile.TemporaryDirectory(prefix='bim2sim_openfoam17_').name)

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)
    # download_test_resources(IFCDomain.hydraulic, force_new=False)
    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/FM_ARC_DigitalHub_with_SB89.ifc',
        IFCDomain.ventilation:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/hydraulic/ifc/DigitalHub_Gebaeudetechnik'
            '-LUEFTUNG_v2.ifc',
        IFCDomain.hydraulic:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/hydraulic/ifc/DigitalHub_Gebaeudetechnik-HEIZUNG_v2'
            '.ifc',
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

    # Set other simulation settings, otherwise all settings are set to default
    project.sim_settings.cfd_export = True
    project.sim_settings.select_space_guid = '2o3MylYZzAnR8q1ofuG3sg'
    # project.sim_settings.select_space_guid = '3hiy47ppf5B8MyZqbpTfpc'

    # VR/AR lab: '2o3MylYZzAnR8q1ofuG3sg'
    # Cafeteria: '3GmoJyFk9FvAnea6mogixJ'
    project.sim_settings.inlet_type = 'Original'
    project.sim_settings.outlet_type = 'Original'
    project.sim_settings.add_heating = True
    project.sim_settings.add_people = True
    project.sim_settings.add_floorheating = False
    project.sim_settings.add_airterminals = True
    project.sim_settings.add_comfort = True
    project.sim_settings.add_furniture = True
    project.sim_settings.add_people = True
    project.sim_settings.add_comfort = True
    project.sim_settings.furniture_setting = 'Office'
    project.sim_settings.furniture_amount = 12
    project.sim_settings.people_amount = 7
    project.sim_settings.people_setting = 'Seated'
    project.sim_settings.output_keys = ['output_outdoor_conditions',
                                        'output_zone_temperature',
                                        'output_zone', 'output_infiltration',
                                        'output_meters',
                                        'output_internal_gains']
    # project.sim_settings.level_heat_balance = False

    answers = ('Autodesk Revit','Autodesk Revit', *(None,)*13,
               *('HVAC-AirTerminal',)*3,
               *(None,)*2, 2015)
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))
    # run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_17()
