import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.types import IFCDomain


def run_example_simple_hvac_aixlib():
    """Run an HVAC simulation with the AixLib backend.

    This example runs an HVAC with the aixlib backend. Specifies project
    directory and location of the HVAC IFC file. Then, it creates a bim2sim
    project with the aixlib backend. Simulation settings are specified (here,
    the aggregations are specified), before the project is executed with the
    previously specified settings."""

    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example4').name)

    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.hydraulic:
            Path(bim2sim.__file__).parent /
            'assets/ifc_example_files/hvac_heating.ifc',
    }
    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'aixlib')

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

# IfcBuildingElementProxy: skip
# Rücklaufverschraubung: 'HVAC-PipeFitting',
# Apparate (M_606) 'HVAC-Distributor',
# 3-Wege-Regelventil PN16: 'HVAC-ThreeWayValve',
# True * 6
# efficiency: 0.95
# flow_temperature: 70
# nominal_power_consumption: 200
# return_temperature: 50
# heat_capacity: 10 * 7


if __name__ == '__main__':
    run_example_simple_hvac_aixlib()