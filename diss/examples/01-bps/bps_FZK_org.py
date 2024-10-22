import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain


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
        tempfile.TemporaryDirectory(prefix='diss_bps_FZK_org_').name)

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)
    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'diss/assets/ifc/AC20-FZK-Haus.ifc',
    }

    # Create a project including the folder structure for the project with
    # energyplus as backend
    project = Project.create(project_path, ifc_paths, 'energyplus')

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.epw')

    project.sim_settings.prj_custom_usages = (
        Path(bim2sim.__file__).parent.parent / 'diss/assets/usages/'
                                               'customUsages_AC20-FZK-Haus_diss.json')
    project.sim_settings.prj_use_conditions = (
        Path(bim2sim.__file__).parent.parent / 'diss/assets/usages/'
                                               'UseConditionsComfort_AC20-FZK-Haus_diss.json'
    )
    # Set the install path to your EnergyPlus installation according to your
    # system requirements
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'

    # run annual simulation for EnergyPlus
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'
        # 'Waermeschutzverglasung, dreifach'

    project.sim_settings.setpoints_from_template = True
    project.sim_settings.year_of_construction_overwrite = 1998
    project.sim_settings.run_full_simulation = True
    project.sim_settings.create_plots = True

    # Set other simulation settings, otherwise all settings are set to default

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_1()
