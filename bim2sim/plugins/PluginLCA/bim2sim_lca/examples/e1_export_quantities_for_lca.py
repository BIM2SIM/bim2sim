import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
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
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        "D:\dja-jho\Testing\Ventilation+Hydraulic")

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
    project.sim_settings.weather_file_path = Path(
        r"D:\02_Git\Dissertation_Coding\outer_optimization\clustering\DEU_NW_Aachen.105010_TMYx.mos")

    project.sim_settings.update_emission_parameter_from_oekobdauat = False
    project.sim_settings.calculate_lca_building = False
    project.sim_settings.calculate_lca_hydraulic_system = False
    project.sim_settings.calculate_lca_ventilation_system = True
    project.sim_settings.pipe_type = "Stahlrohr"

    project.sim_settings.heat_delivery_type = "UFH"
    project.sim_settings.ufh_pipe_type = "PEX"

    #project.sim_settings.hydraulic_system_material_xlsx = project_path / "export" / "hydraulic system" / "material_quantities_hydraulic_system.xlsx"

    project.sim_settings.ventilation_supply_system_material_xlsx = project_path / "export" / "ventilation system" / "supply air" / "dataframe_supply_air.xlsx"
    project.sim_settings.ventilation_exhaust_system_material_xlsx = project_path / "export" / "ventilation system" / "exhaust air" / "dataframe_exhaust_air.xlsx"

    answers = (2015,)
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())

    # Run the project with the ConsoleDecisionHandler. No questions for this
    # example will be prompted.
    # run_project(project, ConsoleDecisionHandler())

    # Go to the export folder and have a look at the two .csv files.
    # <Material_quantities_ERC_Mainbuilding_Arch.csv> will offer you information
    # about the amount (mass) of each material used in the building
    # Quantities_overview_ERC_Mainbuilding_Arch.csv will give you an overview
    # about all elements separately and their materials


if __name__ == '__main__':
    run_example_complex_building_lca()
