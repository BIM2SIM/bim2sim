import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, ConsoleDecisionHandler, run_project
from bim2sim.elements import bps_elements
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import IFCDomain
from bim2sim.elements.base_elements import Material
from bim2sim.plugins.PluginIFCCheck.bim2sim_ifccheck import PluginIFCCheck


def run_simple_project():
    """Run a bim2sim project with the PluginIFCCheck
    """
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_e1_checkifc_').name)

    # Set the ifc path to use and define which domain the IFC belongs to.
    # This is done via a dictionary, where the key is the domain and the value
    # the path to the IFC file. We are using an architecture domain IFC file
    # here from the FZK-Haus which is a simple IFC provided by KIT.

    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
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
            Path(bim2sim.__file__).parent.parent /
            'test/resources/ids/fail-a_minimal_ids_can_check_a_minimal_ifc_1_2.ids'
    )

    run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_simple_project()
