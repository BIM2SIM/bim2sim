import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, ConsoleDecisionHandler, run_project
from bim2sim.elements import bps_elements
from bim2sim.elements.bps_elements import ThermalZone
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain
from bim2sim.elements.base_elements import Material


def run_simple_project():
    """Run the building simulation with teaser as backend in interactive mode.
    
    This example will show how to set up a project based on an IFC file,
    how to create bim2sim elements based on the existing IFC data with all
    relevant elements for building performance simulation and how to review and
    analyze the resulting elements
    """
    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example2').name)

    # Download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)

    # Set the ifc path to use and define which domain the IFC belongs to.
    # This is done via a dictionary, where the key is the domain and the value
    # the path to the IFC file. We are using an architecture domain IFC file
    # here from the FZK-Haus which is a simple IFC provided by KIT.
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }

    # With open_conf the default created config file will be opened and can be
    # adjusted by the user and saved afterwards.
    # todo open_conf is currently only tested under windows

    # Create a new project, based on the created temporary directory, the
    # defined ifc_paths and the template plugin. The template plugin is just
    # for explanation and holds some basic tasks to convert IFC data into
    # bim2sim elements structure without creating any simulation models.
    # By looking into the plugin definition we can find the following:
    # default_tasks = [
    #     common.LoadIFC,
    #     common.CheckIfc,
    #     common.CreateElements,
    #     bps.CreateSpaceBoundaries,
    #     common.BindStoreys,
    #     common.Weather,
    # ]
    # This means that these 7 tasks are performed when not using interactive
    # mode (see e2_interactive_project.py for more information about
    # interactive mode). For detailed information about the different tasks
    # please have a look at their documentation.

    project = Project.create(
        project_path, ifc_paths, 'template')

    # Next to the plugin that should be used we can do further configuration
    # by using the `sim_settings`. `sim_settings` are meant to configure the
    # creation of the simulation model and assign information before starting
    # the process. This can be either weather data files, default simulation
    # time of the created model but also what kind of enrichment should be used
    # or what elements are relevant for the simulation. For more information
    # please review the documentation for `sim_settings`.

    # Let's assign a weather file first. This is currently needed, even if no
    # simulation is performed
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    # Assign relevant elements

    # The template plugin uses the BaseSimSettings which don't have any
    # relevant elements defined. This means without overwriting the
    # `relevant_elements` setting, no bim2sim elements will be created.
    # Let's assign all `bps_elements` and the `Material` element. This way
    # the IFC will be searched for all IFC entities that should be mapped into
    # the classes defined in `bps_elements` and in the class `Material`.
    # For further information about the elements structure and the mapping
    # procedure please read the `elements` documentation
    project.sim_settings.relevant_elements = {*bps_elements.items, Material}

    # Assign the enrichment for use conditions of thermal zones.

    # bim2sim allows to enrich the use conditions, e.g. how many persons are
    # in a room at what times. For this we are using the data and profiles
    # provided by DIN 18599. To assign the correct enrichment to specific
    # rooms/thermal zones, we need to match these to the conditions provided
    # by DIN 18599. bim2sim automatically does some matching based on regular
    # expressions, translations, pre confiugred mappings and the existing room
    # information in the IFC, but this doesn't cover all cases. Especially
    # if rooms are named "room 1" or similar and no further usage information
    # is provided by the IFC. In this case user input decisions will be
    # queried. To reduce these queries, we can set pre-configured .json files
    # to match the room names to usages via `sim_settings`.
    # The `sim_setting` `prj_custom_usages` allows to specify the path to the
    # .json file that holds the mapping.
    # TODO continue 
    # project.sim_settings.prj_custom_usages = (Path(
    #     bim2sim.__file__).parent.parent / "test/resources/arch/custom_usages/"
    #         "customUsagesFM_ARC_DigitalHub_with_SB_neu.json")
    # # The `sim_setting` `prj_use_conditions` allows further changes by
    # # providing an adjusted use conditions file with e.g. varied lighting
    # # schedules for specific zones.
    # project.sim_settings.prj_use_conditions = (Path(
    #     bim2sim.__file__).parent.parent / "test/resources/arch/custom_usages/"
    #         "UseConditionsFM_ARC_DigitalHub_with_SB_neu.json")

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())

    # Get the created bim2sim elements from playground state
    b2s_elements = project.playground.state['elements']

    all_thermal_zones = [
        ele for ele in b2s_elements.values() if isinstance(ele, ThermalZone)]

    # As we use
    print('test')
    # From this point the console will guide you through the process.
    # You have to select which tasks you want to perform and might have to
    # answer decisions about how to deal with unclear information in the IFC.


if __name__ == '__main__':
    run_simple_project()
