import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
from bim2sim.utilities.common_functions import download_test_resources, \
    download_library


def run_example_complex_building_teaser(project_path, heating_bool, cooling_bool, ahu_bool, building_standard,
                                        window_standard):
    """Run a building performance simulation with the TEASER backend.
    
    ...
    """

    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    #project_path = r"D:\dja-jho\Testing\SystemTest"

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)
    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-Institute-Var-2.ifc',
    }

    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'teaser')

    # specify simulation settings (please have a look at the documentation of
    # all under concepts/sim_settings
    # combine spaces to thermal zones based on their usage
    project.sim_settings.zoning_setup = LOD.medium
    project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
    project.sim_settings.setpoints_from_template = True

    # overwrite existing layer structures and materials based on templates
    project.sim_settings.layers_and_materials = LOD.low

    # specify templates for the layer and material overwrite
    project.sim_settings.construction_class_walls = building_standard
    project.sim_settings.construction_class_windows = window_standard
    project.sim_settings.construction_class_doors = building_standard


    # Activate Cooling and AHU
    project.sim_settings.heating = heating_bool
    project.sim_settings.cooling = cooling_bool

    project.sim_settings.overwrite_ahu_by_settings = True
    project.sim_settings.ahu_heating = ahu_bool
    project.sim_settings.ahu_cooling = ahu_bool
    project.sim_settings.ahu_dehumidification = ahu_bool
    project.sim_settings.ahu_humidification = ahu_bool
    project.sim_settings.ahu_heat_recovery = ahu_bool
    project.sim_settings.ahu_heat_recovery_efficiency = 0.8


    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    project.sim_settings.dymola_simulation = True
    project.sim_settings.edit_mat_result_file_flag = True
    # Make sure that AixLib modelica library exist on machine by cloning it and
    #  setting the path of it as a sim_setting
    repo_url = "https://github.com/RWTH-EBC/AixLib.git"
    branch_name = "main"
    repo_name = "AixLib"
    path_aixlib = (
            Path(bim2sim.__file__).parent.parent / "local" / f"library_{repo_name}")
    download_library(repo_url, branch_name, path_aixlib)
    project.sim_settings.path_aixlib = path_aixlib / repo_name / 'package.mo'


    project.sim_settings.prj_use_conditions = (Path(
        bim2sim.__file__).parent.parent /
            "bim2sim/assets/enrichment/usage/UseConditions.json")
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "customUsagesAC20-Institute-Var-2_with_SB-1-0.json")


    answers = (2015,)
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())

    elements = project.playground.state['elements']

if __name__ == '__main__':
    run_example_complex_building_teaser(True, True, 'kfw_40', 'Waermeschutzverglasung, dreifach')
