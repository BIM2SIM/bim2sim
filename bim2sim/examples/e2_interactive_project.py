import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, ConsoleDecisionHandler
from bim2sim.elements import bps_elements
from bim2sim.utilities.types import IFCDomain
from bim2sim.elements.base_elements import Material


# TODO #548 Implement two examples which don't use any "third party" plugins
#  This currently uses TEASER plugin but will be changed in the feature
def run_interactive_example():
    """Run the building simulation with teaser as backend in interactive mode.
    
    Interactive mode means that we use open_conf=True to open up the config.toml
    during the process to change settings and use an interactive PlayGround 
    which allows us to select which tasks we want to proceed with after a tasks
    is finished and don't use the predefined order of default_tasks for the 
    selected Plugin. 
    """
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example1').name)

    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }
    # With open_conf the default created config file will be opened and can be
    # adjusted by the user and saved afterwards.
    # todo open_conf is currently only tested under windows

    project = Project.create(
        project_path, ifc_paths, 'template', open_conf=True)

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    # set relevant elements

    project.sim_settings.relevant_elements = {*bps_elements.items, Material}

    # create a handler (use interactive console handler)
    handler = ConsoleDecisionHandler()

    # pass the project to the handler and run it in interactive mode
    ConsoleDecisionHandler().handle(project.run(interactive=True))

    b2s_elements = project.playground.state['elements']

    # From this point the console will guide you through the process.
    # You have to select which tasks you want to perform and might have to
    # answer decisions about how to deal with unclear information in the IFC.


if __name__ == '__main__':
    run_interactive_example()
