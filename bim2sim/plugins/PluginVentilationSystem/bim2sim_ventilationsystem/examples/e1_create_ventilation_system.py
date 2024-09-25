import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria


def run_example_project_ventilation_system():
    """
    """

    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(r"D:\dja-jho\Testing\Ventilation+Hydraulic")

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)
    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-Institute-Var-2.ifc',
    }

    # Create a project including the folder structure for the project
    project = Project.create(project_path, ifc_paths, 'VentilationSystem')

    # specify simulation settings (please have a look at the documentation of
    # all under concepts/sim_settings

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')


    # Define if exhaust and/or supply air data should be exported
    project.sim_settings.ventilation_lca_airflow = True
    project.sim_settings.ventilation_lca_export_supply = True
    project.sim_settings.ventilation_lca_export_exhaust = True
    project.sim_settings.ventilation_lca_system = True

    project.sim_settings.heating = True
    project.sim_settings.cooling = True
    project.sim_settings.deactivate_ahu = False

    project.sim_settings.prj_use_conditions = (
        r"D:\dja-jho\Git\BIM2SIM\bim2sim\assets\enrichment\usage\UseConditions_New.json")
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
                                              "test/resources/arch/custom_usages/"
                                              "customUsagesFM_ARC_DigitalHub_with_SB89.json")
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    construction_year = 2015
    answers = (construction_year,)
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())


    # Run the project with the ConsoleDecisionHandler. You will be prompted to
    # select the year of construction as this is missing in the IFC and needed
    # for enrichment
    # run_project(project, ConsoleDecisionHandler())

    # Go to the export folder and have a look at the two .csv files.
    # <Material_quantities_ERC_Mainbuilding_Arch.csv> will offer you information
    # about the amount (mass) of each material used in the building
    # Quantities_overview_ERC_Mainbuilding_Arch.csv will give you an overview
    # about all elements separately and their materials


if __name__ == '__main__':
    run_example_project_ventilation_system()
