"""Simple example for PluginIFCCheck with bps focus."""
import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.types import IFCDomain
from bim2sim.plugins.PluginIFCCheck.bim2sim_ifccheck import PluginIFCCheck


def run_simple_project():
    """Run a bim2sim project with the PluginIFCCheck."""
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_e1_checkifc_bps_3rooms_').name)

    # Set the ifc path to use and define which domain the IFC belongs to.
    # This is done via a dictionary, where the key is the domain and the value
    # the path to the IFC file. We are using an architecture domain IFC file
    # here from the FZK-Haus which is a simple IFC provided by KIT.
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/'
            '3rooms_Heater_AirTerminal_Table_with_SB_errors.ifc',
    }
    project = Project.create(
        project_path, ifc_paths, PluginIFCCheck)

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

    # assign an IDS file, which is needed to check the ifc file by ifctester
    project.sim_settings.ids_file_path = (
            Path(bim2sim.__file__).parent /
            'plugins/PluginIFCCheck/bim2sim_ifccheck/ifc_bps.ids'
    )

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

    # Run the project with pre-configured answers for decisions
    answers = ('Other',
               )
    Handler = DebugDecisionHandler(answers)
    Handler.handle(project.run())


if __name__ == '__main__':
    run_simple_project()
