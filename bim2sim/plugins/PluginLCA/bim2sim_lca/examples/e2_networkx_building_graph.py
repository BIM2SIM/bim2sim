from pathlib import Path
import tempfile

import bim2sim
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain
from bim2sim import Project, run_project, ConsoleDecisionHandler


def run_example_building_graph():
    """Creates a graph network based on an IFC model.


    """
    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example5').name)

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)

    # Get path of the IFC Building model that is used for this example
    # In this case the mainbuilding of EBC at Aachen which has mostly correct
    # implemented materials in IFC
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/'
            'ERC_Mainbuilding_Arch.ifc'
    }
    project = Project.create(project_path, ifc_paths, 'lca')
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

if __name__ == '__main__':
    run_example_building_graph()