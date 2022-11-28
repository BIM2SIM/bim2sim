import tempfile
from pathlib import Path

from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.log import default_logging_setup
from bim2sim.workflow import LOD


def run_example_3():
    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal" directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example3').name)

    # Get path of the IFC Building model that is used for this example
    ifc_path = Path(__file__).parent.parent / 'test/TestModels/AC20-FZK-Haus.ifc'

    # Create a project including the folder structure for the project with
    # energyplus as backend and no specified workflow
    # (default workflow is taken)
    project = Project.create(project_path, ifc_path, 'energyplus')

    # specified settings for workflows can be changed later as well
    project.workflow.zoning_setup = LOD.full

    # Run the project with the ConsoleDecisionHandler. This allows interactive input
    # to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_3()
