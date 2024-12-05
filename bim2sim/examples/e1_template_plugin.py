import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, ConsoleDecisionHandler, run_project
from bim2sim.elements import bps_elements
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import IFCDomain
from bim2sim.elements.base_elements import Material


def run_simple_project():
    """Run a bim2sim project with the TemplatePlugin.
    
    This example will show how to set up a project based on an IFC file,
    how to create bim2sim elements based on the existing IFC data with all
    relevant elements for building performance simulation and how to review and
    analyze the resulting elements
    """
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example2').name)

    # Set the ifc path to use and define which domain the IFC belongs to.
    # This is done via a dictionary, where the key is the domain and the value
    # the path to the IFC file. We are using an architecture domain IFC file
    # here from the FZK-Haus which is a simple IFC provided by KIT.
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }

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
        project_path, ifc_paths, 'Template')

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

    # Assign the enrichment for use conditions of thermal zones.

    # bim2sim allows to enrich the use conditions, e.g. how many persons are
    # in a room at what times. For this we are using the data and profiles
    # provided by DIN 18599. To assign the correct enrichment to specific
    # rooms/thermal zones, we need to match these to the conditions provided
    # by DIN 18599. bim2sim automatically does some matching based on regular
    # expressions, translations, pre-configured mappings and the existing room
    # information in the IFC, but this doesn't cover all cases. Especially
    # if rooms are named "room 1" or similar and no further usage information
    # is provided by the IFC. In this case user input decisions will be
    # queried. To reduce these queries, we can set pre-configured .json files
    # to match the room names to usages via `sim_settings`.
    # The `sim_setting` `prj_custom_usages` allows to specify the path to the
    # .json file that holds the mapping.

    # As the IFC we are using has an attic which is identified by its
    # IfcLongName and the commonUsages mapping as Living space. Let's assume
    # this attic is used as a private gym because our residents are quite fit
    # people. We can assign a different usage by simply creating a customUsages
    # file and assign the usage type "Exercise room" to the room type
    # "Galerie". We already stored the .json file under the test resources,
    # have a look at it.
    # In the next step we assign this file to the project by setting:
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent / "test/resources/arch/custom_usages/"
            "customUsagesAC20-FZK-Haus.json")

    # If we don't want to use the standard data for usage conditions, we
    # can change them. We created a project specific UseConditions file for
    # this in the test resources section. In this we assume that our residents
    # like to sleep at quite cold conditions of 16 °C. So we adjusted the
    # "heating_profile" entry. We leave the data for the other usages
    # untouched.

    # Let's assign this use conditions file:
    project.sim_settings.prj_use_conditions = (Path(
        bim2sim.__file__).parent.parent / "test/resources/arch/custom_usages/"
            "UseConditionsAC20-FZK-Haus.json")

    # By default bim2sim tries to calculate the heating profile based on given
    # information from the IFC. As the used IFC has information about the set
    # temperature, we need an additional `sim_setting` to force the overwrite
    # of the existing data in the IFC.
    project.sim_settings.setpoints_from_template = True

    # Before we can run the project, we need to assign a DecisionHandler. To
    # understand this, we need to understand why we need such a handler.
    # Decisions in bim2sim are used to get user input whenever information in
    # the IFC are unclear. E.g. if the usage type of a room can't be
    # identified, we use a decision to query the user what usage the room has.
    # As we don't know at which point a decision comes up, we are using
    # generators and yield to iterate over them. If you want to understand
    # deeper how this works, have a look at the decision documentation.
    # For usage as console tool, we implemented the ConsoleDecisionHandler,
    # which we are going to assign in the next step.
    # There are multiple ways to run a project. One is to use the run_project()
    # function and assign which project to run and which decision handler to
    # use. In our case this is:
    run_project(project, ConsoleDecisionHandler())

    # After the project is finished, we can review the results. As we don't
    # create any simulation model with the template Plugin, our results are
    # mainly the identified bim2sim elements and the enriched data in this
    # elements. Let's get the created bim2sim elements. Everything that is
    # created by the different tasks during the runtime is stored in the
    # playground state. The playground manages the different tasks and their
    # information. To get the bim2sim elements, we can simply get them from the
    # state with the following command:
    b2s_elements = project.playground.state['elements']

    # Let's filter all ThermalZone entities, we can do this by a loop, or use
    # a pre-build function of bim2sim:
    all_thermal_zones = filter_elements(b2s_elements, 'ThermalZone')

    # Let's print some data about our zones and review the enriched data for
    # our zones:
    for tz in all_thermal_zones:
        print('##########')
        print(f"Name of the zone: {tz.name}")
        print(f"Area of the zone: {tz.net_area}")
        print(f"Volume of the zone: {tz.volume}")
        print(f"Daily heating profile of the zone: {tz.heating_profile}")
        print('##########')

    # We can see that our provided heating profiles are correctly taken into
    # account. The enriched thermal zones now hold all information required for
    # a building performance simulation. For complete examples with model
    # creation and simulations please go the examples of the plugins.


if __name__ == '__main__':
    run_simple_project()
