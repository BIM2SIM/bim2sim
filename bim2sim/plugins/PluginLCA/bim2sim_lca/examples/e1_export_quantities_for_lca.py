import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain, Temperatures


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
    #project_path = Path()


    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example5').name)

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)

    # Get path of the IFC Building model that is used for this example
    # In this case the mainbuilding of EBC at Aachen which has mostly correct
    # implemented materials in IFC
    """ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/'
            'ERC_Mainbuilding_Arch.ifc'
    }"""
    """ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/'
            'AC20-Institute-Var-2.ifc'
    }"""
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/'
            'AC20-FZK-Haus.ifc'
    }
    # Create a project including the folder structure for the project with
    # LCA as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'lca')

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # set simulation results path (this is the result of a presvious bps simulation)
    project.sim_settings.bps_sim_results_path = (
            Path(bim2sim.__file__).parent.parent /
    # link mat file here
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Mat Datei
    project.sim_settings.simulation_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/simulation_results/AC20FZKHaus.mat')
    """project.sim_settings.simulation_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/simulation_results/2010_heavy_holz_zweifach.mat')"""
    # Excel
    project.sim_settings.distribution_file_path = (
        Path(bim2sim.__file__).parent /
        'assets/distribution/distribution_system.xlsx'
    )

    project.sim_settings.networkx_building_path = (
        Path(bim2sim.__file__).parent.parent /
        'test/resources/arch/building_graph/'
        'AC20-FZK-Haus_building_graph.json'
    )
    project.sim_settings.distribution_networkx_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/building_graph/'
            'AC20-FZK-Haus_distribution_graph.json'
    )
    project.sim_settings.thermalzone_mapping_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/simulation_results/AC20-FZK-Haus_tz_mapping.json')

    """project.sim_settings.thermalzone_mapping_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/simulation_results/AC20-Institute-Var-2_tz_mapping.json')"""


    #project.sim_settings.distribution_system_type = "radiator"
    project.sim_settings.distribution_system_type = "underfloor_heating"
    project.sim_settings.design_distribution_temperatures = [Temperatures.low, Temperatures.mid, Temperatures.high]
    project.sim_settings.distribution_pipe_material = "steel_pipe"
    project.sim_settings.distribution_delivery_nodes = ["IfcWindow"]
    project.sim_settings.distribution_layer_options = "Ifc_Wall"
    #project.sim_settings.distribution_layer_options = "Space_Boundary"
    #todo: Das in die exports folder
    project.sim_settings.networkx_building_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/building_graph/'
            'AC20-FZK-Haus_building_graph.json'
    )
    project.sim_settings.distribution_networkx_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/building_graph/'
            'AC20-FZK-Haus_distribution_graph.json'
    )
    project.sim_settings.one_pump_distribution_system = False
    project.sim_settings.bldg_graph_from_json = True
    project.sim_settings.heating_graph_from_json = True
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
