import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria


def run_example_complex_building_openfoam():
    """Run a building performance simulation with the energyplus backend.

    ...
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
    project = Project.create(project_path, ifc_paths, 'openfoam')
    project.sim_settings.prj_use_conditions = \
        (Path(bim2sim.plugins.PluginComfort.bim2sim_comfort.__file__).parent /
         "assets/UseConditionsComfort_FM_ARC_DigitalHub_with_SB89.json")
    # specify simulation settings (please have a look at the documentation of
    # all under concepts/sim_settings

    # Set the install path to your EnergyPlus installation according to your
    # system requirements
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'

    # combine spaces to thermal zones based on their usage
    # use cooling
    project.sim_settings.cooling = True
    project.sim_settings.setpoints_from_template = True

    # overwrite existing layer structures and materials based on templates
    project.sim_settings.layers_and_materials = LOD.low
    # specify templates for the layer and material overwrite
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.epw')
    # Run a simulation directly with dymola after model creation

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
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "customUsagesFM_ARC_DigitalHub_with_SB89.json")
    # create plots based on the results after simulation
    project.sim_settings.cfd_export = True
    # project.sim_settings.identify_critical_zones = True
    project.sim_settings.set_run_period = True
    project.sim_settings.run_period_start_month = 2
    project.sim_settings.run_period_start_day = 2
    project.sim_settings.run_period_end_month = 2
    project.sim_settings.run_period_end_day = 8
    project.sim_settings.select_space_guid = '3hiy47ppf5B8MyZqbpTfpc'
    project.sim_settings.simulation_time = 15
    project.sim_settings.simulation_date = '02/05'
    project.sim_settings.run_meshing = False
    project.sim_settings.run_cfd_simulation = False
    project.sim_settings.add_heating = False
    project.sim_settings.add_floorheating = False
    project.sim_settings.add_airterminals = False
    project.sim_settings.add_people = False

    # # Run the project with pre configured answers for decisions
    space_boundary_genenerator = 'Other'
    handle_proxies = (*(None,) * 12,)
    construction_year = 2015
    answers = (space_boundary_genenerator,
               *handle_proxies,
               construction_year)
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())

if __name__ == '__main__':
    run_example_complex_building_openfoam()
