import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.types import IFCDomain


def run_example_complex_building_lca():
    """Generate output for an LCA analysis.

    This example generates output for an LCA analysis. Specifies project
    directory and location of the IFC file. Then, it creates a bim2sim
    project with the lca backend. The project is executed with the
    previously specified settings.

    After execution, go to the export folder and have a look at the two .csv
    files. <Material_quantities_ERC_Mainbuilding_Arch.csv> will offer you
    information about the amount (mass) of each material used in the building.
    <Quantities_overview_ERC_Mainbuilding_Arch.csv> will give you an overview
    about all elements separately and their materials.
    """
    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example5').name)

    # Get path of the IFC Building model that is used for this example
    # In this case the mainbuilding of EBC at Aachen which has mostly correct
    # implemented materials in IFC
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/'
            'ERC_Mainbuilding_Arch.ifc'
    }
    # Create a project including the folder structure for the project with
    # LCA as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'lca')

    # set weather file data
    project.sim_settings.weather_file_path_modelica = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    # Run the project with the ConsoleDecisionHandler. No questions for this
    # example will be prompted.
    run_project(project, ConsoleDecisionHandler())

    # Go to the export folder and have a look at the two .csv files.
    # <Material_quantities_ERC_Mainbuilding_Arch.csv> will offer you information
    # about the amount (mass) of each material used in the building
    # Quantities_overview_ERC_Mainbuilding_Arch.csv will give you an overview
    # about all elements separately and their materials


if __name__ == '__main__':
    run_example_complex_building_lca()
