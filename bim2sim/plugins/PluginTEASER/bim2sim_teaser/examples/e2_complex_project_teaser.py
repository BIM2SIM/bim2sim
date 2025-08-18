import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
from bim2sim.utilities.common_functions import download_library


def run_example_complex_building_teaser():
    """Run a building performance simulation with PluginTEASER.

    This example creates a BEPS simulation model and performs the simulation
    in Dymola based on the DigitalHub IFC using PluginTEASER.
    """
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)

    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/FM_ARC_DigitalHub_with_SB89.ifc',
    }

    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'teaser')

    # specify simulation settings (please have a look at the documentation of
    # all under concepts/sim_settings
    # combine spaces to thermal zones based on their usage
    project.sim_settings.zoning_criteria = ZoningCriteria.usage
    # use cooling
    project.sim_settings.cooling_tz_overwrite = True
    project.sim_settings.setpoints_from_template = True

    project.sim_settings.ahu_heating_overwrite = True
    project.sim_settings.ahu_cooling_overwrite = True
    project.sim_settings.ahu_heat_recovery_overwrite = True

    # overwrite existing layer structures and materials based on templates
    project.sim_settings.layers_and_materials = LOD.low
    # specify templates for the layer and material overwrite
    project.sim_settings.construction_class_walls = 'iwu_heavy'
    project.sim_settings.construction_class_windows = \
        'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'

    # set weather file data
    project.sim_settings.weather_file_path_modelica = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    project.sim_settings.dymola_simulation = True
    # Make sure that AixLib modelica library exist on machine by cloning it and
    #  setting the path of it as a sim_setting
    repo_url = "https://github.com/RWTH-EBC/AixLib.git"
    branch_name = "main"
    repo_name = "AixLib"
    path_aixlib = (
            Path(bim2sim.__file__).parent.parent / "local" / f"library_{repo_name}")
    download_library(repo_url, branch_name, path_aixlib)
    project.sim_settings.path_aixlib = path_aixlib / repo_name / 'package.mo'
    # Select results to output:
    project.sim_settings.sim_results = [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out",
        "internal_gains_machines_rooms", "internal_gains_persons_rooms",
        "internal_gains_lights_rooms",
        "heat_set_rooms",
        "cool_set_rooms"
    ]
    project.sim_settings.prj_use_conditions = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "UseConditionsFM_ARC_DigitalHub.json")
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "customUsagesFM_ARC_DigitalHub_with_SB89.json")
    # create plots based on the results after simulation
    project.sim_settings.create_plots = True

    # Run the project with pre-configured answers for decisions
    space_boundary_genenerator = 'Other'
    handle_proxies = (*(None,) * 12,)
    construction_year = 2015
    answers = (space_boundary_genenerator,
               *handle_proxies,
               construction_year)
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())


if __name__ == '__main__':
    run_example_complex_building_teaser()
