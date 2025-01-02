import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria


def run_medium_building_teaser():
    """Run a building performance simulation with the TEASER backend.

    ...
    """

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        "D:\dja-jho\Testing\BIM2SIM_HydraulicSystem3")

    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/FM_ARC_DigitalHub_with_SB89.ifc'
    }

    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'teaser')

    # specify simulation settings (please have a look at the documentation of
    # all under concepts/sim_settings
    # combine spaces to thermal zones based on their usage
    project.sim_settings.zoning_criteria = ZoningCriteria.usage
    # use cooling

    project.sim_settings.setpoints_from_template = True
    project.sim_settings.cooling = True
    # overwrite existing layer structures and materials based on templates
    project.sim_settings.layers_and_materials = LOD.low
    # specify templates for the layer and material overwrite
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    project.sim_settings.dymola_simulation = True
    # Select results to output:
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
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    answers = (2015, )
    # handler = DebugDecisionHandler(answers)
    # handler.handle(project.run())

    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())
    # Have a look at the elements/elements that were created
    elements = project.playground.state['elements']
    # filter the elements only for outer walls
    df_finals = project.playground.state['df_finals']
    return project


if __name__ == '__main__':
    run_medium_building_teaser()
