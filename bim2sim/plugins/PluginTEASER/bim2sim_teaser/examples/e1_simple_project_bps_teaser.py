import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria


def run_example_simple_building_teaser():
    """Run a building performance simulation with the TEASER backend.

    This example runs a BPS with the TEASER backend. Specifies project
    directory and location of the IFC file. Then, it creates a bim2sim
    project with the TEASER backend. Sim settings are specified before the
    project is executed with the previously specified settings.
    """
    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_teaser_example_e1_').name)

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)
    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }

    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'teaser')

    # specify simulation settings (please have a look at the documentation of
    # all under concepts/sim_settings
    # combine spaces to thermal zones based on their usage
    project.sim_settings.zoning_setup = LOD.full
    project.sim_settings.zoning_criteria = ZoningCriteria.usage
    # use cooling
    project.sim_settings.cooling = True
    # use set points for heating and cooling from templates
    project.sim_settings.setpoints_from_template = True
    # overwrite existing layer structures and materials based on templates
    project.sim_settings.layers_and_materials = LOD.low
    # specify templates for the layer and material overwrite
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'

    # set weather file data
    project.sim_settings.weather_file_path_modelica = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    project.sim_settings.dymola_simulation = False
    # Select results to output:
    project.sim_settings.sim_results = [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out",
        "infiltration_rooms"
    ]
    # FZK Haus has correct IFC typings but faulty SB internal/external
    # information
    project.sim_settings.fix_type_mismatches_with_sb = True

    # run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming decisions during the model creation process
    run_project(project, ConsoleDecisionHandler())
    # have a look at the elements/elements that were created
    elements = project.playground.state['elements']
    # we can filter the elements only for outer walls
    outer_walls = []
    from bim2sim.elements.bps_elements import OuterWall
    for ele in elements.values():
        if isinstance(ele, OuterWall):
            outer_walls.append(ele)
    # let's see what outer walls are found
    print(f"Found {len(outer_walls)}: {outer_walls}")
    # let's have a look at the layers and which were overwritten and enriched
    # due to project.sim_settings.layers_and_materials = LOD.low
    layer_set = outer_walls[0].layerset
    layer_0 = layer_set.layers[0]
    material = layer_0.material
    density = material.density
    spec_heat_capacity = material.spec_heat_capacity
    print(f"Density is: {density}")
    print(f"Specific heat capacity is {spec_heat_capacity}")
    # let's also get the final teaser project which can be manipulated further
    teaser_prj = project.playground.state['teaser_prj']
    return project


if __name__ == '__main__':
    run_example_simple_building_teaser()
