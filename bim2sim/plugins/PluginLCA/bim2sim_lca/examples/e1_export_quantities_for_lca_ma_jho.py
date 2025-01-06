import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.types import IFCDomain


def run_example_complex_building_lca(lock,
                                     project_path, weather_file_path,
                                     heat_delivery_type):
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
    with lock:

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

        # Set Lock class
        project.sim_settings.lock = lock

        # set weather file data
        project.sim_settings.weather_file_path = weather_file_path

        project.sim_settings.update_emission_parameter_from_oekobdauat = False

        project.sim_settings.calculate_lca_building = True
        project.sim_settings.calculate_lca_hydraulic_system = True
        project.sim_settings.calculate_lca_ventilation_system = True

        project.sim_settings.calculate_costs_building = True
        project.sim_settings.calculate_costs_hydraulic_system = True
        project.sim_settings.calculate_costs_ventilation_system = True

        project.sim_settings.pipe_type = "Stahlrohr"
        project.sim_settings.hydraulic_components_data_file_radiator_sheet = "Profilierte Flachheizkörper"
        project.sim_settings.heat_delivery_type = heat_delivery_type
        project.sim_settings.ufh_pipe_type = "PEX"

        project.sim_settings.ufh_costs = 130 # €/m²
        project.sim_settings.hydraulic_pipe_costs = 50 # €/m
        project.sim_settings.ventilation_duct_costs = 80 # €/m²
        project.sim_settings.ventilation_isolation_costs = 10 # €/m²

        project.sim_settings.hydraulic_system_material_xlsx = Path(project_path, "export", "hydraulic system", "material_quantities_hydraulic_system.xlsx")
        project.sim_settings.ventilation_supply_system_material_xlsx = Path(project_path / "export" / "ventilation system" / "supply air" / "dataframe_supply_air.xlsx")
        project.sim_settings.ventilation_exhaust_system_material_xlsx = Path(project_path / "export" / "ventilation system" / "exhaust air" / "dataframe_exhaust_air.xlsx")

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

    total_gwp_building = project.playground.state['total_gwp_building']
    total_gwp_hydraulic_pipe = project.playground.state['total_gwp_hydraulic_pipe']
    total_gwp_hydraulic_component = project.playground.state['total_gwp_hydraulic_component']
    total_gwp_ventilation_duct = project.playground.state['total_gwp_ventilation_duct']
    total_gwp_ventilation_component = project.playground.state['total_gwp_ventilation_component']

    return total_gwp_building, total_gwp_hydraulic_pipe, total_gwp_hydraulic_component, total_gwp_ventilation_duct, total_gwp_ventilation_component

if __name__ == '__main__':
    run_example_complex_building_lca()
