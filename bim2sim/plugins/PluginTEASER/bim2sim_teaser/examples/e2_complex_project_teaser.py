import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria


def run_example_complex_building_teaser():
    """Run a building performance simulation with the TEASER backend.

    ...
    """
    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    #project_path = Path(
    #    tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)
    project_path = fr"D:\dja-jho\Git\BIM2SIM_Results\bim2sim_example6"

    # download additional test r20esources for arch domain, you might want to set
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
    project.sim_settings.zoning_setup = LOD.full
    # project.sim_settings.zoning_criteria = ZoningCriteria.usage
    # use cooling

    project.sim_settings.setpoints_from_template = True
    project.sim_settings.cooling = True
    # overwrite existing layer structures and materials based on templates
    project.sim_settings.layers_and_materials = LOD.low
    # specify templates for the layer and material overwrite
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Alu- oder Stahlfenster, Isolierverglasung'

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    project.sim_settings.dymola_simulation = True
    # Select results to output:
    """
    project.sim_settings.sim_results = [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out",
        "internal_gains_machines_rooms", "internal_gains_persons_rooms",
        "internal_gains_lights_rooms",
        # "n_persons_rooms",
        # "infiltration_rooms",
        # "mech_ventilation_rooms",
        "heat_set_rooms",
        "cool_set_rooms"
    ]
    """
    project.sim_settings.sim_results = [
        "heat_energy_total", "cool_energy_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "internal_gains_machines_rooms", "internal_gains_persons_rooms",
        "internal_gains_lights_rooms"
    ]
    project.sim_settings.prj_use_conditions = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "UseConditionsFM_ARC_AC20_Institute_neu.json")
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "customUsagesAC20-Institute-Var-2_with_SB-1-0.json")
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    space_boundary_genenerator = 'Other'
    handle_proxies = (*(None,) * 12,)
    construction_year = 2015
    answers = (space_boundary_genenerator,
               *handle_proxies,
               construction_year)
    handler = DebugDecisionHandler(answers)
    #handler.handle(project.run())


    # input to answer upcoming questions regarding the imported IFC.
    #run_project(project, handler)
    run_project(project, ConsoleDecisionHandler())
    # Have a look at the elements/elements that were created
    elements = project.playground.state['elements']
    # filter the elements only for outer walls
    df_finals = project.playground.state['df_finals']
    return df_finals


if __name__ == '__main__':
    run_example_complex_building_teaser()
