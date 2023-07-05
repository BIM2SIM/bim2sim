import tempfile
from pathlib import Path

from bim2sim import Project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.types import IFCDomain


# TODO #548 Implement two examples which don't use any "third party" plugins
def run_example_1():
    """Run the building simulation with teaser as backend in interactive mode.
    
    Interactive mode means that we use open_conf=True to open up the config.toml
    during the process to change settings and use an interactive PlayGround 
    which allows us to select which tasks we want to proceed with after a tasks
    is finished and don't use the predefined order of default_tasks for the 
    selected Plugin. 
    """
    # first three commands are the same as in e1
    default_logging_setup()

    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example2').name)
    ifc_paths = {
        IFCDomain.arch: Path(__file__).parent.parent
                        / 'assets/ifc_example_files/AC20-FZK-Haus.ifc',
    }

    # With open_conf the default created config file will be opened and can be
    # adjusted by the user and saved afterwards.
    # todo open_conf is currently only tested under windows
    project = Project.create(project_path, ifc_paths, 'teaser', open_conf=True)

    # create a handler (use interactive console handler)
    handler = ConsoleDecisionHandler()

    # pass the project to the handler and run it in interactive mode
    ConsoleDecisionHandler().handle(project.run(interactive=True))

    # From this point the console will guide you through the process.
    # You have to select which tasks you want to perform and might have to
    # answer decisions about how to deal with unclear information in the IFC.


if __name__ == '__main__':
    run_example_1()
