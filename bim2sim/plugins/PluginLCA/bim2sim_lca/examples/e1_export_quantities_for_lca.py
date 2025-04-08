import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.utilities.types import IFCDomain, LCACalculationBuilding
from threading import Lock

lock = Lock()


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
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_pluginLCA_example1').name)

    # Get path of the IFC Building model that is used for this example
    # In this case the mainbuilding of EBC at Aachen which has mostly correct
    # implemented materials in IFC
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/'
            'AC20-Institute-Var-2.ifc'
    }
    # Create a project including the folder structure for the project with
    # LCA as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'lca')

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    project.sim_settings.year_of_construction_overwrite = 2015
    project.sim_settings.calculate_lca_building = LCACalculationBuilding.granular
    project.sim_settings.calculate_lca_hydraulic_system = False
    project.sim_settings.calculate_lca_ventilation_system = False
    project.sim_settings.lock = lock
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
