import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam import OpenFOAMSimSettings
from bim2sim.project import add_config_section
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.types import IFCDomain

def run_example_19():
    """
    Prepare an OpenFOAM case with a radiator and solar radiation.

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
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_openfoam19_').name)

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }
    project = Project.create(project_path, ifc_paths, 'openfoam')
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.epw')

    # Set the install path to your EnergyPlus installation according to your
    # system requirements
    # project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'

    # Set other simulation settings, otherwise all settings are set to default
    project.sim_settings.run_full_simulation = True
    project.sim_settings.cfd_export = True
    # project.sim_settings.select_space_guid = '3GmoJyFk9FvAnea6mogixJ'
    project.sim_settings.select_space_guid = '2RSCzLOBz4FAK$_wE8VckM'
    project.sim_settings.simulation_time = 12
    project.sim_settings.simulation_date = '01/14'
    project.sim_settings.building_rotation_overwrite = 180
    project.sim_settings.add_heating = True
    project.sim_settings.fixed_faces = []

    project.sim_settings.total_iterations = 6000
    project.sim_settings.n_procs = 48
    project.sim_settings.radiation_model = 'fvDOM'
    project.sim_settings.cluster_max_runtime_simulation = "03:59:00"

    project.sim_settings.add_solar_radiation = False
    project.sim_settings.set_openfoam_source = 'Modified'
    project.sim_settings.cluster_jobname = "solar_radiation"

    answers = ('Autodesk Revit','Autodesk Revit', *(None,)*13,
               *('HVAC-AirTerminal',)*3,
               *(None,)*2, 2015)
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))
    # run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_19()
