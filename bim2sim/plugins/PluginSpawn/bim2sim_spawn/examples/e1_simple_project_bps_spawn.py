import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.types import IFCDomain


def run_example_spawn_1():
    """Export a SpawnOfEnergyPlus simulation model.


    This example exports a SpawnOfEnergyPlus Co-Simulation model. The HVAC
    model is generated via the PluginAixLib using the AixLib Modelica library.
    The building model is generated using PluginEnergyPlus. The used IFC file
    holds both, HVAC and building in one file.
    """
    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example_spawn').name)

    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.mixed:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/mixed/ifc/'
            'b03_heating_with_building_blenderBIM.ifc'
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
    project.sim_settings.weather_file_path_modelica = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Generate outer heat ports for spawn HVAC sub model
    project.sim_settings.outer_heat_ports = True

    # Set other simulation settings, otherwise all settings are set to default
    project.sim_settings.aggregations = [
        'PipeStrand',
        'ParallelPump',
        'GeneratorOneFluid'
    ]

    project.sim_settings.group_unidentified = 'name'

    # Run the project with the DebugDecisionHandler with pre-filled answers.
    answers = (
        'HVAC-PipeFitting',  # Identify PipeFitting
        'HVAC-Distributor',  # Identify Distributor
        'HVAC-ThreeWayValve',  # Identify ThreeWayValve
        2010,  # year of construction of building
        *(True,) * 7,  # 7 real dead ends found
        *(0.001,)*13,  # volume of junctions
        2000, 175,  # rated_pressure_difference + rated_volume_flow pump of 1st storey (big)
        4000, 200,  # rated_pressure_difference + rated_volume_flow for 2nd storey
        *(70, 50,)*7,  # flow and return temp for 7 space heaters
        0.056,  # nominal_mass_flow_rate 2nd storey TRV (kg/s),
        20,  # dT water of boiler
        70,  # nominal flow temperature of boiler
        0.3,  # minimal part load range of boiler
        8.5,  # nominal power of boiler (in kW)
        50,  # nominal return temperature of boiler
    )
    # handler = ConsoleDecisionHandler()
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())


if __name__ == '__main__':
    run_example_spawn_1()
