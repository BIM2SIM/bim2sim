import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.types import IFCDomain


def run_example_simple_hvac_hkesim():
    """Run an HVAC simulation with the HKESim backend.

    This example runs an HVAC with the HKESim backend. Specifies project
    directory and location of the HVAC IFC file. Then, it creates a bim2sim
    project with the HKESim backend. Simulation settings are specified (here,
    the aggregations are specified), before the project is executed with the
    previously specified settings."""
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example1_hkesim').name)

    # Set path of ifc for hydraulic domain with the fresh downloaded test models
    ifc_paths = {
        IFCDomain.hydraulic:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/hydraulic/ifc/'
            'hvac_heating.ifc'
    }
    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'HKESim')

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    # specify simulation settings
    project.sim_settings.aggregations = [
        'UnderfloorHeating',
        'Consumer',
        'PipeStrand',
        'ParallelPump',
        'ConsumerHeatingDistributorModule',
        'GeneratorOneFluid'
    ]
    project.sim_settings.group_unidentified = 'name'

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    # Correct decision for identification of elements and useful parameters for
    # missing attributes are written below
    run_project(project, ConsoleDecisionHandler())

# Answers to questions:
# IfcBuildingElementProxy: skip
# Rücklaufverschraubung: 15 'HVAC-PipeFitting'
# Apparate (M_606) 6 'HVAC-Distributor',
# 3-Wege-Regelventil PN16: 19 'HVAC-ThreeWayValve',
# Dead end: True * 6
# efficiency: 0.95
# nominal_power_consumption: 200


if __name__ == '__main__':
    run_example_simple_hvac_hkesim()
