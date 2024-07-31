import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain
from bim2sim_aixlib import LoadLibrariesAixLib


def run_example_simple_hvac_aixlib():
    """Run an HVAC simulation with the AixLib backend.
    """

    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(
            prefix='bim2sim_example_simple_aixlib_3').name)

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.hydraulic, force_new=False)

    # Set path of ifc for hydraulic domain with the fresh downloaded test models
    ifc_paths = {
        IFCDomain.hydraulic:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/'
            'ExampleHOM_with_radiator_ports_connected.ifc'
    }
    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'aixlib')

    # set weather file data
    project.sim_settings.weather_file_path_modelica = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    # specify simulation settings
    project.sim_settings.aggregations = [
        # 'UnderfloorHeating',
        # 'Consumer',
        # 'PipeStrand',
        # 'ParallelPump',
        # 'ConsumerHeatingDistributorModule',
        # 'GeneratorOneFluid'
    ]
    project.sim_settings.group_unidentified = 'name'
    from bim2sim.tasks import base, common, hvac
    project.plugin_cls.default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElements,
        hvac.ConnectElements,
        hvac.MakeGraph,
        LoadLibrariesAixLib,
        hvac.Export,
    ]

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
